"""
timetable_extractor.py
======================
Production-grade LLM-based timetable extraction using Cerebras Inference API.

Optimizations Applied
---------------------
OPT-1  Chunked extraction   — large docs split into overlapping chunks; results merged
OPT-2  Async parallel calls — httpx + asyncio; all chunks extracted concurrently
OPT-3  Response caching     — SHA-256 keyed shelve cache; skips API on re-extraction
OPT-4  Streaming response   — tokens streamed and assembled; lower perceived latency
OPT-5  json-repair library  — replaces brittle regex cleaning; handles all LLM JSON quirks
OPT-6  Pydantic validation  — typed schema replaces _apply_defaults; fail-fast on bad data
OPT-7  Markdown tables      — PDF tables rendered as markdown; LLMs parse these natively
OPT-8  Two-stage extraction — Stage-1 extracts structure; Stage-2 extracts content with context
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import logging
import re
import shelve
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import fitz          # PyMuPDF
import httpx
import pandas as pd
import pdfplumber
import requests
from json_repair import repair_json
from pydantic import BaseModel, Field, ValidationError

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================================================
# Custom Exceptions
# ===========================================================================

class ExtractionError(RuntimeError):
    """Raised when document extraction fails after all retries."""

class APIConnectionError(RuntimeError):
    """Raised when the Cerebras API cannot be reached."""


# ===========================================================================
# Constants
# ===========================================================================

DEFAULT_ENDPOINT          = "https://api.cerebras.ai/v1/chat/completions"
DEFAULT_MODEL             = "llama3.1-8b"
DEFAULT_MAX_INPUT_CHARS   = 20_000   # ~5 000 tokens; fits 8 192-token context
DEFAULT_MAX_OUTPUT_TOKENS = 2_000
DEFAULT_CHUNK_SIZE        = 18_000
DEFAULT_CHUNK_OVERLAP     = 500
DEFAULT_MAX_RETRIES       = 2
RETRY_BACKOFF_SECS        = 1
CACHE_PATH                = "extraction_cache"

DOCUMENT_PLACEHOLDER = "%%DOCUMENT_TEXT%%"
CONTEXT_PLACEHOLDER  = "%%CONTEXT_JSON%%"

PDF_EXTENSIONS   = (".pdf",)
EXCEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm")
CSV_EXTENSIONS   = (".csv",)


# ===========================================================================
# OPT-6: Pydantic Schema
# ===========================================================================

class Period(BaseModel):
    id:         int
    start_time: str
    end_time:   str

class TimeSlots(BaseModel):
    periods:       List[Period] = Field(default_factory=list)
    working_days:  List[str]   = Field(default=["Monday","Tuesday","Wednesday","Thursday","Friday"])
    break_periods: List[int]   = Field(default=[3, 6])
    lunch_period:  int         = 6

class ElectiveSlot(BaseModel):
    day_name: str
    period:   int

class Section(BaseModel):
    section_id:     str
    name:           str
    semester:       int       = 1
    year:           int       = 1
    room:           str       = ""
    student_count:  int       = 0
    coordinator:    str       = ""
    specialization: str       = ""
    electives:      List[str] = Field(default_factory=list)

class Department(BaseModel):
    dept_id:  str
    name:     str
    sections: List[Section] = Field(default_factory=list)

class Subject(BaseModel):
    subject_id:           str
    name:                 str
    type:                 str       = "Theory"
    credits:              int       = 0
    lectures_per_week:    int       = 0
    semester:             int       = 0
    departments:          List[str] = Field(default_factory=list)
    specialization:       str       = ""
    min_classes_per_week: int       = 0
    max_classes_per_day:  int       = 2
    tutorial_sessions:    int       = 0
    is_elective:          bool      = False

class Lab(BaseModel):
    lab_id:                       str
    name:                         str
    type:                         str       = "Lab"
    credits:                      int       = 0
    sessions_per_week:            int       = 1
    duration_hours:               int       = 2
    semester:                     int       = 0
    departments:                  List[str] = Field(default_factory=list)
    specialization:               str       = ""
    lab_rooms:                    List[str] = Field(default_factory=list)
    requires_consecutive_periods: int       = 2

class Faculty(BaseModel):
    faculty_id:           str
    name:                 str
    department:           str       = ""
    designation:          str       = ""
    subjects:             List[str] = Field(default_factory=list)
    max_hours_per_week:   int       = 20
    avg_leaves_per_month: int       = 2
    preferred_time_slots: List[int] = Field(default_factory=list)
    faculty_experience:   int       = 0

class Room(BaseModel):
    room_id:    str
    name:       str
    type:       str       = "Classroom"
    capacity:   int       = 0
    department: str       = ""
    equipment:  List[str] = Field(default_factory=list)

class HardConstraints(BaseModel):
    no_faculty_clash:                bool = True
    no_room_clash:                   bool = True
    no_section_clash:                bool = True
    max_classes_per_subject_per_day: int  = 2
    max_classes_per_day_per_section: int  = 7
    lab_duration_consecutive:        bool = True

class SoftConstraint(BaseModel):
    weight:        float        = 0.0
    max_deviation: Optional[int] = None

class SoftConstraints(BaseModel):
    balanced_daily_load:      SoftConstraint = Field(default_factory=lambda: SoftConstraint(weight=0.30, max_deviation=2))
    faculty_preference_slots: SoftConstraint = Field(default_factory=lambda: SoftConstraint(weight=0.20))
    minimize_faculty_travel:  SoftConstraint = Field(default_factory=lambda: SoftConstraint(weight=0.15))

class Constraints(BaseModel):
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    soft_constraints: SoftConstraints = Field(default_factory=SoftConstraints)

class GAParams(BaseModel):
    population_size:         int   = 50
    generations:             int   = 50
    mutation_rate:           float = 0.2
    crossover_rate:          float = 0.8
    elite_size:              int   = 5
    early_stopping_patience: int   = 10

class CollegeInfo(BaseModel):
    name:           str = "Extracted College"
    session:        str = "2025-26"
    effective_date: str = "2025-09-15"

class ExtractionInfo(BaseModel):
    extracted_at: str
    source_file:  str
    text_length:  int
    model:        str
    method:       str
    chunks_used:  int  = 1
    cache_hit:    bool = False

class TimetableData(BaseModel):
    """Root validated schema — every field has a safe default."""
    college_info:             CollegeInfo          = Field(default_factory=CollegeInfo)
    time_slots:               TimeSlots            = Field(default_factory=TimeSlots)
    elective_slots:           List[ElectiveSlot]   = Field(default_factory=list)
    departments:              List[Department]      = Field(default_factory=list)
    subjects:                 List[Subject]         = Field(default_factory=list)
    labs:                     List[Lab]             = Field(default_factory=list)
    faculty:                  List[Faculty]         = Field(default_factory=list)
    rooms:                    List[Room]            = Field(default_factory=list)
    subject_name_mapping:     Dict[str, str]        = Field(default_factory=dict)
    constraints:              Constraints           = Field(default_factory=Constraints)
    genetic_algorithm_params: GAParams             = Field(default_factory=GAParams)
    extraction_info:          Optional[ExtractionInfo] = None


# ===========================================================================
# OPT-8: Two-Stage Prompts
# ===========================================================================

STAGE1_PROMPT = f"""\
You are an expert university timetable parser.

TASK: Extract ONLY the structural skeleton from the document below.
Output a single valid JSON object. No markdown, no code fences, no commentary.

Required keys:
{{
  "college_info":   {{"name":"","session":"","effective_date":""}},
  "time_slots":     {{"periods":[],"working_days":[],"break_periods":[],"lunch_period":0}},
  "elective_slots": [],
  "departments":    [],
  "rooms":          []
}}

Rules:
- Extract time periods EXACTLY as written in the document.
- working_days: only days explicitly present.
- break_periods / lunch_period: infer from timetable gaps when not stated.
- departments must include sections; each section lists its electives.
- Output ONLY JSON.

DOCUMENT:
{DOCUMENT_PLACEHOLDER}
"""

STAGE2_PROMPT = f"""\
You are an expert university timetable parser.

TASK: Using the structural context below, extract subjects, labs, faculty, and
subject_name_mapping from the document.
Output a single valid JSON object. No markdown, no code fences, no commentary.

Required keys:
{{
  "subjects":             [],
  "labs":                 [],
  "faculty":              [],
  "subject_name_mapping": {{}}
}}

Rules:
- Every lab must ALSO appear in subjects with type="Lab".
- requires_consecutive_periods defaults to 2 unless stated.
- is_elective: true for elective subjects.
- faculty.subjects contains subject_ids only.
- Output ONLY JSON.

STRUCTURAL CONTEXT (Stage 1 result):
{CONTEXT_PLACEHOLDER}

DOCUMENT:
{DOCUMENT_PLACEHOLDER}
"""


# ===========================================================================
# TimetableExtractor
# ===========================================================================

class TimetableExtractor:
    """
    Production-grade timetable extractor using the Cerebras Inference API.

    Extraction pipeline
    -------------------
    1. File bytes  → raw text          (_extract_text)
    2. Raw text    → overlapping chunks (_chunk_document)         [OPT-1]
    3. Chunks      → async parallel    (_extract_all_chunks)      [OPT-2]
       per chunk:
         a. Stage-1 LLM call (structure)                         [OPT-8]
         b. Stage-2 LLM call (content + context)                 [OPT-8]
         both calls use streaming                                 [OPT-4]
         JSON parsed with json-repair                             [OPT-5]
    4. Chunk dicts → merged dict       (_merge_dicts)             [OPT-1]
    5. Merged dict → Pydantic model    (_validate)                [OPT-6]
    6. Result      → shelve cache      (_cached_extract)          [OPT-3]
    PDF tables rendered as markdown before LLM sees them          [OPT-7]
    """

    def __init__(
        self,
        cerebras_api_key:  str,
        endpoint_url:      str  = DEFAULT_ENDPOINT,
        model:             str  = DEFAULT_MODEL,
        max_input_chars:   int  = DEFAULT_MAX_INPUT_CHARS,
        max_output_tokens: int  = DEFAULT_MAX_OUTPUT_TOKENS,
        chunk_size:        int  = DEFAULT_CHUNK_SIZE,
        chunk_overlap:     int  = DEFAULT_CHUNK_OVERLAP,
        max_retries:       int  = DEFAULT_MAX_RETRIES,
        enable_cache:      bool = True,
        cache_path:        str  = CACHE_PATH,
        enable_streaming:  bool = True,
    ) -> None:
        self.cerebras_api_key  = cerebras_api_key
        self.endpoint_url      = endpoint_url
        self.model             = model
        self.max_input_chars   = max_input_chars
        self.max_output_tokens = max_output_tokens
        self.chunk_size        = chunk_size
        self.chunk_overlap     = chunk_overlap
        self.max_retries       = max_retries
        self.enable_cache      = enable_cache
        self.cache_path        = cache_path
        self.enable_streaming  = enable_streaming
        self.is_connected:     bool = False

        self._test_connection()
        logger.info(
            "TimetableExtractor ready | model=%s connected=%s cache=%s streaming=%s",
            self.model, self.is_connected, self.enable_cache, self.enable_streaming,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _build_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type":  "application/json",
        }

    def _build_payload(self, prompt: str, stream: bool = False) -> Dict[str, Any]:
        return {
            "model":       self.model,
            "messages":    [{"role": "user", "content": prompt}],
            "max_tokens":  self.max_output_tokens,
            "temperature": 0.0,
            "top_p":       1.0,
            "stream":      stream,
        }

    def _cache_key(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()

    # ------------------------------------------------------------------ #
    # Connection test                                                      #
    # ------------------------------------------------------------------ #

    def _test_connection(self) -> None:
        try:
            r = requests.post(
                self.endpoint_url,
                headers=self._build_headers(),
                json={**self._build_payload("ping"), "max_tokens": 5},
                timeout=10,
            )
            self.is_connected = r.status_code == 200
            logger.log(
                logging.INFO if self.is_connected else logging.WARNING,
                "Cerebras API: %s (HTTP %s)",
                "OK" if self.is_connected else "FAILED", r.status_code,
            )
        except requests.exceptions.RequestException as exc:
            logger.warning("Cerebras connection test failed: %s", exc)
            self.is_connected = False

    # ------------------------------------------------------------------ #
    # OPT-5: JSON parsing with json-repair                                 #
    # ------------------------------------------------------------------ #

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        """
        Strip markdown fences, isolate the JSON object, repair and parse.
        json-repair handles: trailing commas, single quotes, unquoted keys,
        missing brackets, Python True/False, and truncated JSON.
        """
        text  = re.sub(r"```json|```", "", raw).strip()
        start = text.find("{")
        end   = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found (first 200 chars): {raw[:200]}")
        repaired = repair_json(text[start : end + 1])
        return json.loads(repaired)

    # ------------------------------------------------------------------ #
    # OPT-6: Pydantic validation                                           #
    # ------------------------------------------------------------------ #

    def _validate(self, data: Dict[str, Any]) -> TimetableData:
        """Validate and coerce extracted data. Recovers partial data on failure."""
        try:
            return TimetableData(**data)
        except ValidationError as exc:
            logger.warning("Validation issues (recovering partial data): %s", exc)
            safe = {k: data.get(k) for k in TimetableData.model_fields if data.get(k) is not None}
            return TimetableData(**safe)

    # ------------------------------------------------------------------ #
    # OPT-1: Chunking                                                      #
    # ------------------------------------------------------------------ #

    def _chunk_document(self, text: str) -> List[str]:
        """Split text into overlapping chunks to avoid hard truncation."""
        if len(text) <= self.chunk_size:
            return [text]
        chunks: List[str] = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = end - self.chunk_overlap
        logger.info(
            "Document split into %d chunks (size=%d overlap=%d)",
            len(chunks), self.chunk_size, self.chunk_overlap,
        )
        return chunks

    # ------------------------------------------------------------------ #
    # OPT-1: Merge chunk results                                           #
    # ------------------------------------------------------------------ #

    def _id_of(self, item: Any) -> Any:
        """Return the primary ID of a dict for deduplication."""
        if not isinstance(item, dict):
            return item
        for key in ("subject_id","lab_id","faculty_id","room_id","dept_id","section_id"):
            if key in item:
                return item[key]
        return json.dumps(item, sort_keys=True)

    def _merge_dicts(self, dicts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple partial extraction dicts.
        - Lists  : de-duplicated by primary ID field
        - Dicts  : shallow merged (later values win for scalars)
        - Scalars: first non-empty value wins
        """
        if not dicts:
            return {}
        if len(dicts) == 1:
            return dicts[0]

        merged: Dict[str, Any] = {}
        for d in dicts:
            if not isinstance(d, dict):
                continue
            for k, v in d.items():
                if k not in merged:
                    merged[k] = v
                elif isinstance(v, list) and isinstance(merged[k], list):
                    seen = {self._id_of(x) for x in merged[k]}
                    for item in v:
                        item_id = self._id_of(item)
                        if item_id not in seen:
                            merged[k].append(item)
                            seen.add(item_id)
                elif isinstance(v, dict) and isinstance(merged[k], dict):
                    merged[k] = {**merged[k], **v}
                elif not merged[k] and v:
                    merged[k] = v
        return merged

    # ------------------------------------------------------------------ #
    # OPT-2 + OPT-4: Async streaming LLM call                             #
    # ------------------------------------------------------------------ #

    async def _call_llm_async(
        self, client: httpx.AsyncClient, prompt: str
    ) -> Tuple[str, float]:
        """
        Single async LLM call with retry.
        Uses streaming when enabled (OPT-4), plain POST otherwise.
        Returns (response_text, latency_seconds).
        """
        response_text: str = ""          # always defined; safe to log in except block
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            response_text = ""
            t0 = time.time()
            try:
                if self.enable_streaming:
                    collected: List[str] = []
                    async with client.stream(
                        "POST",
                        self.endpoint_url,
                        headers=self._build_headers(),
                        json=self._build_payload(prompt, stream=True),
                        timeout=90,
                    ) as resp:
                        if resp.status_code != 200:
                            body = await resp.aread()
                            raise APIConnectionError(f"HTTP {resp.status_code}: {body[:200]}")
                        async for line in resp.aiter_lines():
                            line = line.strip()
                            if not line or not line.startswith("data: "):
                                continue
                            payload = line[6:]
                            if payload == "[DONE]":
                                break
                            try:
                                delta = (
                                    json.loads(payload)["choices"][0]
                                    .get("delta", {})
                                    .get("content", "")
                                )
                                collected.append(delta)
                            except (json.JSONDecodeError, KeyError):
                                continue
                    response_text = "".join(collected)
                else:
                    resp = await client.post(
                        self.endpoint_url,
                        headers=self._build_headers(),
                        json=self._build_payload(prompt, stream=False),
                        timeout=90,
                    )
                    if resp.status_code != 200:
                        raise APIConnectionError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                    response_text = resp.json()["choices"][0]["message"]["content"]

                latency = time.time() - t0
                logger.debug("LLM call done in %.2fs (%d chars)", latency, len(response_text))
                return response_text, latency

            except Exception as exc:
                last_exc = exc
                logger.warning("LLM attempt %d/%d failed: %s", attempt, self.max_retries, exc)
                if attempt < self.max_retries:
                    await asyncio.sleep(RETRY_BACKOFF_SECS)

        raise APIConnectionError(
            f"All {self.max_retries} LLM attempts failed. Last: {last_exc}"
        ) from last_exc

    # ------------------------------------------------------------------ #
    # OPT-8: Two-stage extraction per chunk                                #
    # ------------------------------------------------------------------ #

    async def _extract_chunk(
        self, client: httpx.AsyncClient, chunk: str, idx: int
    ) -> Dict[str, Any]:
        """
        Stage-1: extract structure (college, time_slots, departments, rooms).
        Stage-2: extract content  (subjects, labs, faculty) using Stage-1 context.
        Merge both stage outputs and return.
        """
        logger.info("Chunk %d | Stage-1 start", idx)

        # Stage-1 ──────────────────────────────────────────────────────
        s1_prompt = STAGE1_PROMPT.replace(DOCUMENT_PLACEHOLDER, chunk)
        raw1, lat1 = await self._call_llm_async(client, s1_prompt)
        try:
            s1_data = self._parse_json(raw1)
        except ValueError as exc:
            logger.warning("Chunk %d Stage-1 parse failed: %s", idx, exc)
            s1_data = {}

        logger.info("Chunk %d | Stage-1 done (%.2fs) → Stage-2 start", idx, lat1)

        # Stage-2 ──────────────────────────────────────────────────────
        s2_prompt = (
            STAGE2_PROMPT
            .replace(CONTEXT_PLACEHOLDER,  json.dumps(s1_data, indent=2))
            .replace(DOCUMENT_PLACEHOLDER, chunk)
        )
        raw2, lat2 = await self._call_llm_async(client, s2_prompt)
        try:
            s2_data = self._parse_json(raw2)
        except ValueError as exc:
            logger.warning("Chunk %d Stage-2 parse failed: %s", idx, exc)
            s2_data = {}

        logger.info("Chunk %d | Stage-2 done (%.2fs)", idx, lat2)
        return self._merge_dicts([s1_data, s2_data])

    # ------------------------------------------------------------------ #
    # OPT-2: Parallel extraction across all chunks                         #
    # ------------------------------------------------------------------ #

    async def _extract_all_chunks(self, chunks: List[str]) -> Dict[str, Any]:
        """Fire all chunk extractions concurrently and merge."""
        async with httpx.AsyncClient() as client:
            tasks   = [self._extract_chunk(client, c, i) for i, c in enumerate(chunks, 1)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        successful: List[Dict[str, Any]] = []
        for idx, r in enumerate(results, 1):
            if isinstance(r, Exception):
                logger.error("Chunk %d failed: %s", idx, r)
            else:
                successful.append(r)

        if not successful:
            raise ExtractionError("All chunk extractions failed")

        logger.info("%d/%d chunks succeeded", len(successful), len(chunks))
        return self._merge_dicts(successful)

    # ------------------------------------------------------------------ #
    # OPT-3: Cache layer                                                   #
    # ------------------------------------------------------------------ #

    def _cached_extract(self, document_text: str) -> Tuple[Dict[str, Any], bool]:
        """
        Return (result_dict, cache_hit).
        On cache miss: run full extraction pipeline and store result.
        """
        key = self._cache_key(document_text)

        if self.enable_cache:
            try:
                with shelve.open(self.cache_path) as cache:
                    if key in cache:
                        logger.info("Cache HIT (key=%s…)", key[:12])
                        return cache[key], True
            except Exception as exc:
                logger.warning("Cache read failed: %s", exc)

        chunks = self._chunk_document(document_text)
        result = asyncio.run(self._extract_all_chunks(chunks))

        if self.enable_cache:
            try:
                with shelve.open(self.cache_path) as cache:
                    cache[key] = result
                logger.info("Cache WRITE (key=%s…)", key[:12])
            except Exception as exc:
                logger.warning("Cache write failed: %s", exc)

        return result, False

    # ------------------------------------------------------------------ #
    # OPT-7: PDF table → markdown                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _table_to_markdown(table: List[List[Any]]) -> str:
        """Convert a pdfplumber table (list of rows) to a markdown table."""
        if not table:
            return ""
        rows      = [[str(c).strip() if c else "" for c in row] for row in table]
        header    = "| " + " | ".join(rows[0])   + " |"
        separator = "| " + " | ".join("---" for _ in rows[0]) + " |"
        body      = "\n".join("| " + " | ".join(r) + " |" for r in rows[1:])
        return "\n".join(filter(None, [header, separator, body]))

    # ------------------------------------------------------------------ #
    # File text extraction                                                 #
    # ------------------------------------------------------------------ #

    def _extract_text_from_pdf(self, file_content: bytes) -> str:
        parts: List[str] = []
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    text = page.extract_text() or ""
                    if text:
                        parts.append(f"\n=== PAGE {page_num} ===\n{text}")
                    tables = page.extract_tables() or []
                    if tables:
                        parts.append(f"\n=== TABLES PAGE {page_num} ===")
                        for t_idx, table in enumerate(tables, 1):
                            md = self._table_to_markdown(table)
                            if md:
                                parts.append(f"\nTable {t_idx}:\n{md}")
            result = "\n".join(parts).strip()
            if result:
                return result
            logger.warning("pdfplumber returned empty; trying PyMuPDF")
        except Exception as exc:
            logger.warning("pdfplumber failed (%s); trying PyMuPDF", exc)

        # PyMuPDF fallback
        try:
            doc   = fitz.open(stream=file_content, filetype="pdf")
            parts = [f"\n=== PAGE {i+1} (PyMuPDF) ===\n{doc[i].get_text()}" for i in range(len(doc))]
            doc.close()
            return "\n".join(parts).strip()
        except Exception as exc:
            raise ExtractionError(f"PDF extraction failed with both libraries: {exc}") from exc

    def _extract_text_from_excel(self, file_content: bytes, filename: str) -> str:
        lower   = filename.lower()
        engines = (
            ["openpyxl"]           if lower.endswith((".xlsx", ".xlsm"))
            else ["xlrd", "openpyxl"]   # .xls: try legacy engine first
        )
        last_exc: Optional[Exception] = None
        for engine in engines:
            parts: List[str] = []
            try:
                ef = pd.ExcelFile(io.BytesIO(file_content), engine=engine)
                for sheet in ef.sheet_names:
                    parts.append(f"\n=== SHEET: {sheet} ===")
                    df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet,
                                       engine=engine, header=None)
                    for idx, row in df.iterrows():
                        cells    = [str(v).strip() if pd.notna(v) else "" for v in row]
                        row_text = " | ".join(cells)
                        if row_text.strip():
                            parts.append(f"  Row {idx+1}: {row_text}")
                logger.info("Excel extracted with engine=%s", engine)
                return "\n".join(parts).strip()
            except Exception as exc:
                logger.warning("Excel engine '%s' failed: %s", engine, exc)
                last_exc = exc
        raise ExtractionError(
            f"Excel extraction failed for '{filename}': {last_exc}"
        ) from last_exc

    def _extract_text_from_csv(self, file_content: bytes) -> str:
        parts = ["\n=== CSV FILE ==="]
        try:
            df = pd.read_csv(io.BytesIO(file_content), header=None)
            for idx, row in df.iterrows():
                cells    = [str(v).strip() if pd.notna(v) else "" for v in row]
                row_text = " | ".join(cells)
                if row_text.strip():
                    parts.append(f"  Row {idx+1}: {row_text}")
        except Exception as exc:
            raise ExtractionError(f"CSV extraction failed: {exc}") from exc
        return "\n".join(parts).strip()

    def _extract_text(self, file_content: bytes, filename: str) -> str:
        lower = filename.lower()
        if lower.endswith(PDF_EXTENSIONS):
            return self._extract_text_from_pdf(file_content)
        if lower.endswith(EXCEL_EXTENSIONS):
            return self._extract_text_from_excel(file_content, filename)
        if lower.endswith(CSV_EXTENSIONS):
            return self._extract_text_from_csv(file_content)
        supported = PDF_EXTENSIONS + EXCEL_EXTENSIONS + CSV_EXTENSIONS
        raise ValueError(f"Unsupported format '{filename}'. Supported: {supported}")

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def extract_timetable_data(
        self,
        file_content:  bytes,
        filename:      str,
        college_name:  Optional[str] = None,
        session:       Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Extract structured timetable data from a file.

        Parameters
        ----------
        file_content : bytes   Raw file bytes.
        filename     : str     Original filename (determines parsing strategy).
        college_name : str     Optional override for detected college name.
        session      : str     Optional override for detected academic session.

        Returns
        -------
        dict  Fully validated timetable data conforming to TimetableData schema.

        Raises
        ------
        ValueError        Unsupported file format.
        ExtractionError   Text or LLM extraction failed after all retries.
        """
        logger.info("=== Extraction start: '%s' ===", filename)
        t_start = time.time()

        # Step 1 — raw text
        document_text = self._extract_text(file_content, filename)
        if not document_text.strip():
            raise ExtractionError(f"No text could be extracted from '{filename}'")
        logger.info("Raw text: %d chars", len(document_text))

        # Step 2 — LLM extraction (cached + chunked + async + two-stage)
        raw_data, cache_hit = self._cached_extract(document_text)

        # Step 3 — Pydantic validation
        timetable = self._validate(raw_data)

        # Step 4 — caller overrides
        if college_name:
            timetable.college_info.name = college_name
        if session:
            timetable.college_info.session = session

        # Step 5 — extraction metadata
        timetable.extraction_info = ExtractionInfo(
            extracted_at = datetime.now().isoformat(),
            source_file  = filename,
            text_length  = len(document_text),
            model        = self.model,
            method       = "cerebras_two_stage_async",
            chunks_used  = len(self._chunk_document(document_text)),
            cache_hit    = cache_hit,
        )

        logger.info(
            "=== Extraction complete: %.2fs | cache=%s chunks=%d ===",
            time.time() - t_start, cache_hit, timetable.extraction_info.chunks_used,
        )
        return timetable.model_dump()
