import json
import io
import logging
import re
import requests
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import traceback
import time

# PDF Processing Libraries
import pdfplumber
import PyPDF2
from pypdf import PdfReader
import fitz  # PyMuPDF

# Excel + CSV Processing Libraries
import pandas as pd
import openpyxl
from openpyxl import load_workbook

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimetableExtractor:
    """
    ULTRA-FAST LLM-based timetable extraction system using Cerebras Inference API
    Drop-in replacement for Gemini extractor with 10x faster token generation
    """

    def __init__(self, cerebras_api_key: str, endpoint_url: str = None):
        self.cerebras_api_key = cerebras_api_key
        self.endpoint_url = endpoint_url or "https://api.cerebras.ai/v1/chat/completions"

        self._test_connection()
        self.extraction_prompt = self._get_extraction_prompt()

        logger.info("Cerebras LLM extractor initialized successfully")

    def _test_connection(self):
        """Test Cerebras API connection"""
        try:
            headers = {
                "Authorization": f"Bearer {self.cerebras_api_key}",
                "Content-Type": "application/json"
            }

            test_payload = {
                "model": "gpt-oss-120b",
                "messages": [{"role": "user", "content": "Test"}],
                "max_tokens": 10,
                "temperature": 0.0
            }

            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=test_payload,
                timeout=10
            )

            if response.status_code == 200:
                logger.info("Cerebras API connection successful")
            else:
                logger.warning(f"Cerebras API test failed: {response.status_code}")

        except Exception as e:
            logger.warning(f"Cerebras API connection test failed: {e}")

    def _get_extraction_prompt(self) -> str:
        """Load extraction prompt from file or use default."""
        try:
            with open('prompt.md', 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("prompt.md not found, using built-in prompt")
            return self._get_builtin_prompt()

    def _get_builtin_prompt(self) -> str:
        """Return optimized built-in extraction prompt"""
        return """
# Timetable Data Extractor Prompt

You are an expert university data extractor. Your task is to analyze the provided university data document and extract structured information.

## CRITICAL INSTRUCTIONS:

1. You MUST output ONLY valid JSON - no additional text, explanations, or markdown formatting.
2. The entire response must be a single JSON object.
3. Do NOT use code blocks or markdown syntax like ```json.
4. Extract ALL available information from the document.
5. Create comprehensive mappings for subjects, faculty, and sections.
6. Generate appropriate IDs where missing.
7. Infer reasonable defaults for missing information.

## REQUIRED JSON STRUCTURE:

```json
{{
  "college_info": {{
    "name": "College Name from Document",
    "session": "2025-26",
    "effective_date": "2025-09-15"
  }},
  "time_slots": {{
    "periods": [
      {{"id": 1, "start_time": "08:00", "end_time": "08:50"}},
      {{"id": 2, "start_time": "08:50", "end_time": "09:40"}},
      {{"id": 3, "start_time": "09:40", "end_time": "10:30"}},
      {{"id": 4, "start_time": "10:45", "end_time": "11:35"}},
      {{"id": 5, "start_time": "11:35", "end_time": "12:25"}},
      {{"id": 6, "start_time": "12:25", "end_time": "13:15"}},
      {{"id": 7, "start_time": "14:15", "end_time": "15:05"}},
      {{"id": 8, "start_time": "15:05", "end_time": "15:55"}}
    ],
    "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
    "break_periods": [4, 6],
    "lunch_period": 6,
    "mentorship_period": 4
  }},
  "departments": [
    {{
      "dept_id": "CSE",
      "name": "Computer Science Engineering",
      "sections": [
        {{
          "section_id": "CSE_3_A",
          "name": "CSE-3A",
          "semester": 3,
          "year": 2,
          "room": "CL-301",
          "student_count": 60,
          "coordinator": "HOD CSE",
          "specialization": ""
        }}
      ]
    }}
  ],
  "subjects": [
    {{
      "subject_id": "CS301",
      "name": "Data Structures",
      "type": "Theory",
      "credits": 4,
      "lectures_per_week": 4,
      "semester": 3,
      "departments": ["CSE"],
      "specialization": "",
      "min_classes_per_week": 3,
      "max_classes_per_day": 2,
      "tutorial_sessions": 0
    }}
  ],
  "labs": [
    {{
      "lab_id": "CS301L",
      "name": "Data Structures Lab",
      "type": "Lab",
      "credits": 2,
      "sessions_per_week": 1,
      "duration_hours": 2,
      "semester": 3,
      "departments": ["CSE"],
      "specialization": "",
      "lab_rooms": ["LAB-1", "LAB-2"]
    }}
  ],
  "faculty": [
    {{
      "faculty_id": "F001",
      "name": "Dr. Faculty Name",
      "department": "CSE",
      "designation": "Professor",
      "subjects": ["CS301", "CS301L"],
      "max_hours_per_week": 20,
      "avg_leaves_per_month": 2,
      "preferred_time_slots": [1, 2, 3, 4, 5, 7, 8]
    }}
  ],
  "rooms": [
    {{
      "room_id": "CL-301",
      "name": "Classroom 301",
      "type": "Classroom",
      "capacity": 70,
      "department": "CSE",
      "equipment": ["Projector", "Smart Board"]
    }}
  ],
  "subject_name_mapping": {{
    "DS": "CS301",
    "Data Structures": "CS301"
  }},
  "constraints": {{
    "hard_constraints": {{
      "no_faculty_clash": true,
      "no_room_clash": true,
      "no_section_clash": true,
      "max_classes_per_subject_per_day": 2,
      "max_classes_per_day_per_section": 7,
      "lab_duration_consecutive": true
    }},
    "soft_constraints": {{
      "balanced_daily_load": {{"weight": 0.3, "max_deviation": 2}},
      "faculty_preference_slots": {{"weight": 0.2}},
      "minimize_faculty_travel": {{"weight": 0.15}}
    }}
  }},
  "genetic_algorithm_params": {{
    "population_size": 50,
    "generations": 50,
    "mutation_rate": 0.2,
    "crossover_rate": 0.8,
    "elite_size": 5,
    "early_stopping_patience": 10
    }}
}}
````

## EXTRACTION RULES:

1. Look for time slots (periods) - extract start/end times EXACTLY as shown in the document
2. DO NOT modify, add, or remove time periods
3. DO NOT assume break_periods, lunch_period, or mentorship_period - ONLY include if explicitly shown in the document
4. Find all subjects mentioned - create subject IDs and names
5. DO NOT SKIP Labs. They must be added in both subject and lab fields. LABS MUST BE IN BOTH "subject" and "labs"
6. Identify faculty names - generate faculty IDs (F001, F002, etc.)
7. Extract section names - create section IDs
8. Find room information - create room IDs
9. Map subjects to faculty based on timetable assignments
10. Infer department information from section names
11. Create appropriate constraints based on what's in the document
12. Don't use ... to skip parts, use proper delimiters

## CRITICAL INSTRUCTIONS FOR TIME SLOTS:
- Extract ONLY the periods that are explicitly defined in the document
- Use the EXACT start/end times - do NOT round or enhance
- If break_periods are shown in the document, include them
- If there's a lunch period marked in the document, include lunch_period
- If mentorship/HOD period is explicitly mentioned, include mentorship_period
- If any of these are NOT in the document, omit them from the extracted time_slots
- working_days should be ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"] unless the document shows otherwise

## IMPORTANT:

- Extract REAL data from the document, don't just use template values
- If you find specific time periods, use those instead of the template times
- Map actual faculty names from the document
- Use actual subject names and codes from the document
- Create realistic section names based on what you see
- NEVER auto-assume mentorship or break periods
- MAKE SURE TO PROVIDE VALID JSON

## Document content to analyze:

{document_text}

REMEMBER: Output ONLY the JSON structure with extracted data. No explanations, no code blocks, no markdown formatting.
"""

    def _generate_with_cerebras(self, prompt: str, max_tokens: int = 70000) -> tuple:
        headers = {
            "Authorization": f"Bearer {self.cerebras_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-oss-120b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.0,
            "top_p": 1.0,
            "stream": False
        }

        start_time = time.time()

        try:
            response = requests.post(
                self.endpoint_url,
                headers=headers,
                json=payload,
                timeout=60
            )

            latency = time.time() - start_time

            if response.status_code != 200:
                raise Exception(f"Cerebras API error: {response.status_code} - {response.text}")

            data = response.json()

            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return content, latency
            else:
                raise Exception("Invalid Cerebras response")

        except requests.exceptions.Timeout:
            raise Exception("Cerebras API timeout")
        except Exception as e:
            raise Exception(f"Cerebras API failed: {str(e)}")

    # --------------------------------------------------------
    # PDF TEXT EXTRACTION
    # --------------------------------------------------------
    def extract_text_from_pdf(self, file_content: bytes) -> str:
        text_content = ""
        try:
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text_content += f"\n=== PAGE {page_num+1} ===\n{page_text}\n"

                    tables = page.extract_tables()
                    if tables:
                        text_content += f"\n=== TABLES ON PAGE {page_num + 1} ===\n"
                        for table_num, table in enumerate(tables):
                            text_content += f"\nTable {table_num+1}:\n"
                            for row_num, row in enumerate(table):
                                clean_row = [str(c).strip() if c else "" for c in row]
                                text_content += f"Row {row_num+1}: {' | '.join(clean_row)}\n"

        except Exception as e:
            logger.warning("pdfplumber failed, trying PyMuPDF")
            try:
                doc = fitz.open(stream=file_content, filetype="pdf")
                for page_num in range(len(doc)):
                    text = doc[page_num].get_text()
                    text_content += f"\n=== PAGE {page_num+1} (PyMuPDF) ===\n{text}\n"
                doc.close()
            except Exception:
                raise Exception("PDF extraction failed")

        return text_content.strip()

    # --------------------------------------------------------
    # EXCEL TEXT EXTRACTION
    # --------------------------------------------------------
    def extract_text_from_excel(self, file_content: bytes, filename: str) -> str:
        text_content = ""
        try:
            engine = 'openpyxl' if filename.endswith(".xlsx") else 'xlrd'
            excel_file = pd.ExcelFile(io.BytesIO(file_content), engine=engine)

            for sheet_name in excel_file.sheet_names:
                text_content += f"\n=== SHEET: {sheet_name} ===\n"

                df = pd.read_excel(io.BytesIO(file_content), sheet_name=sheet_name, engine=engine, header=None)

                for idx, row in df.iterrows():
                    row_values = [(str(v).strip() if pd.notna(v) else "") for v in row]
                    row_text = " | ".join(row_values)
                    if row_text.strip():
                        text_content += f"Row {idx+1}: {row_text}\n"

        except Exception as e:
            raise Exception(f"Excel extraction failed: {e}")

        return text_content.strip()

    # --------------------------------------------------------
    # NEW: CSV TEXT EXTRACTION
    # --------------------------------------------------------
    def extract_text_from_csv(self, file_content: bytes) -> str:
        """
        Extract text from CSV using pandas.
        """
        text_content = "\n=== CSV FILE ===\n"

        try:
            df = pd.read_csv(io.BytesIO(file_content), header=None)

            for idx, row in df.iterrows():
                row_values = [(str(v).strip() if pd.notna(v) else "") for v in row]
                row_text = " | ".join(row_values)
                if row_text.strip():
                    text_content += f"Row {idx+1}: {row_text}\n"

        except Exception as e:
            raise Exception(f"CSV extraction failed: {str(e)}")

        return text_content.strip()

    # --------------------------------------------------------
    # JSON CLEANING (unchanged)
    # --------------------------------------------------------
    def clean_and_validate_json(self, response_text: str) -> Dict:
        response_text = response_text.strip()

        response_text = re.sub(r'^```json\s*', '', response_text)
        response_text = re.sub(r'^```\s*', '', response_text)
        response_text = re.sub(r'\s*```$', '', response_text)

        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')

        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON found")

        json_content = response_text[start_idx:end_idx+1]

        cleaning_strategies = [
            lambda x: x,
            lambda x: re.sub(r',\s*([}\]])', r'\1', x),
            lambda x: re.sub(r'\.\.\.+', '', x),
        ]

        for strategy in cleaning_strategies:
            try:
                cleaned = strategy(json_content)
                return json.loads(cleaned)
            except:
                continue

        raise ValueError("Invalid JSON")

    # --------------------------------------------------------
    # Data enhancement (unchanged)
    # --------------------------------------------------------
    def enhance_extracted_data(self, data: Dict) -> Dict:
        if not data:
            data = {}

        data.setdefault("college_info", {
            "name": "Extracted College",
            "session": "2025-26",
            "effective_date": "2025-09-15"
        })

        data.setdefault("time_slots", {
            "periods": [],
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        })

        data.setdefault("departments", [])
        data.setdefault("subjects", [])
        data.setdefault("labs", [])
        data.setdefault("faculty", [])
        data.setdefault("rooms", [])
        data.setdefault("subject_name_mapping", {})

        data.setdefault("constraints", {
            "hard_constraints": {
                "no_faculty_clash": True,
                "no_room_clash": True,
                "no_section_clash": True,
                "max_classes_per_day_per_section": 7,
                "lab_duration_consecutive": True
            }
        })

        data.setdefault("genetic_algorithm_params", {
            "population_size": 50,
            "generations": 50,
            "mutation_rate": 0.2,
            "crossover_rate": 0.8,
            "elite_size": 5,
            "early_stopping_patience": 10
        })

        return data

    # --------------------------------------------------------
    # Extraction from text (unchanged)
    # --------------------------------------------------------
    def extract_from_text(self, document_text: str, max_retries: int = 2) -> Dict:
        last_error = None

        for attempt in range(max_retries):
            try:
                max_text_length = 100000
                if len(document_text) > max_text_length:
                    document_text = document_text[:max_text_length] + "\n[TRUNCATED FOR SPEED]"
                    logger.warning("Document truncated")

                full_prompt = self.extraction_prompt.format(document_text=document_text)
                response_text, latency = self._generate_with_cerebras(full_prompt)

                parsed_data = self.clean_and_validate_json(response_text)
                return self.enhance_extracted_data(parsed_data)

            except Exception as e:
                last_error = e
                time.sleep(1)

        return self.enhance_extracted_data({"college_info": {}})

    # --------------------------------------------------------
    # MAIN ENTRY
    # --------------------------------------------------------
    def extract_timetable_data(self,
                               file_content: bytes,
                               filename: str,
                               college_name: Optional[str] = None,
                               session: Optional[str] = None) -> Dict:

        logger.info(f"Extracting: {filename}")

        # Determine file type
        if filename.lower().endswith(".pdf"):
            document_text = self.extract_text_from_pdf(file_content)

        elif filename.lower().endswith((".xlsx", ".xls", ".xlsm")):
            document_text = self.extract_text_from_excel(file_content, filename)

        elif filename.lower().endswith(".csv"):
            document_text = self.extract_text_from_csv(file_content)

        else:
            raise Exception("Unsupported file format")

        if not document_text.strip():
            raise Exception("No text extracted")

        structured_data = self.extract_from_text(document_text)

        if college_name:
            structured_data["college_info"]["name"] = college_name
        if session:
            structured_data["college_info"]["session"] = session

        structured_data["extraction_info"] = {
            "extracted_at": datetime.now().isoformat(),
            "source_file": filename,
            "text_length": len(document_text),
            "method": "cerebras_ultra_fast"
        }

        return structured_data
