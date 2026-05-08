import os
import json
import requests
import logging
from typing import Dict, Any, List
from nlp_models import NLPResponse

# --- Configuration ---
logger = logging.getLogger(__name__)

CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
CEREBRAS_API_KEY = os.getenv("CEREBRAS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Determine which LLM backend to use
if CEREBRAS_API_KEY:
    NLP_LLM_API_URL = CEREBRAS_API_URL
    NLP_LLM_API_KEY = CEREBRAS_API_KEY
    NLP_LLM_MODEL = "llama-4-scout-17b-16e-instruct"
    logger.info("NLP Processor using Cerebras backend")
elif GEMINI_API_KEY:
    NLP_LLM_API_URL = GEMINI_API_URL
    NLP_LLM_API_KEY = GEMINI_API_KEY
    NLP_LLM_MODEL = "gemini-2.0-flash"
    logger.info("NLP Processor using Gemini backend (fallback)")
else:
    NLP_LLM_API_URL = None
    NLP_LLM_API_KEY = None
    NLP_LLM_MODEL = None
    logger.warning("No LLM API key found for NLP processor")

class TimetableNLPProcessor:
    def __init__(self, current_config: Dict[str, Any]):
        self.config = current_config
        if not NLP_LLM_API_KEY:
            raise EnvironmentError("No LLM API key available. Set CEREBRAS_API_KEY or GEMINI_API_KEY.")
        
        # Pre-extract valid IDs
        self.valid_faculty = {f['name']: f.get('faculty_id', 'Unknown') for f in self.config.get('faculty', [])}
        self.valid_rooms = {r['name']: r.get('room_id', 'Unknown') for r in self.config.get('rooms', [])}
        self.valid_sections = {s['name']: s.get('section_id', 'Unknown') for s in (self.config.get('sections') or [])}
        
        # Helper for subjects (name -> id)
        self.valid_subjects = {s['name']: s.get('subject_id', 'Unknown') for s in self.config.get('subjects', [])}

    def _build_system_prompt(self) -> str:
        return f"""
        You are a Schedule Configuration Assistant. Convert user text into a strict JSON object adhering to the provided schema.

        ### DATA CONTEXT (Use these IDs):
        - Faculty: {json.dumps(self.valid_faculty)}
        - Rooms: {json.dumps(self.valid_rooms)}
        - Sections: {json.dumps(self.valid_sections)}
        - Subjects: {json.dumps(self.valid_subjects)}

        ### 1. CONSTRAINT DIFFERENTIATION (CRITICAL)
        You must distinguish between **HARD** (Rules) and **SOFT** (Preferences).
        
        **HARD CONSTRAINTS (Rules that CANNOT be broken):**
        - Keys: `no_faculty_clash`, `no_room_clash`, `max_classes_per_day_per_section`, `break_periods_fixed`.
        - Values: Booleans (`true`/`false`) or Integers.
        - Example: "Teachers cannot be in two places at once" -> `no_faculty_clash: true`
        - Example: "Max 5 classes a day" -> `max_classes_per_day_per_section: 5`

        **SOFT CONSTRAINTS (Optimization goals/Preferences):**
        - Keys: `balanced_daily_load`, `minimize_faculty_travel`, `morning_heavy_subjects`, `avoid_single_period_gaps`.
        - Values: Objects with a `weight` (0.0 to 1.0).
        - Example: "Try to avoid gaps" -> `avoid_single_period_gaps: {{ "weight": 0.8 }}`
        - Example: "Prefer heavy subjects in morning" -> `morning_heavy_subjects: {{ "weight": 0.6, "subjects": [...] }}`

        ### 2. EVENT TYPES
        - **`faculty_absence`**: Teacher is away. Needs `faculty_id`, `start_day`, `end_day`.
        - **`resource_unavailable`**: Room broken/maintenance. Needs `room_id`.
        - **`section_unavailable`**: (NEW) Class/Section is on a trip/event. No classes allowed. Needs `section_id`.
        - **`force_assignment`**: (NEW) Lock a specific class. E.g., "Dr. X must teach Math to Section A on Mon P1".

        ### OUTPUT SCHEMA STRUCTURE
        {{
            "intent": "update_constraints" | "add_events" | "mixed",
            "constraints": {{
                "hard_constraints": {{ ... }},
                "soft_constraints": {{ ... }}
            }},
            "events": [ ... ]
        }}

        ### EXAMPLES
        
        **User:** "Students in CSE-A are on a field trip Monday. Also, try to balance the daily load."
        **Output:**
        {{
            "intent": "mixed",
            "constraints": {{
                "hard_constraints": {{}},
                "soft_constraints": {{ "balanced_daily_load": {{ "weight": 0.5, "max_deviation": 1 }} }}
            }},
            "events": [
                {{ "type": "section_unavailable", "section_id": "CSE_A", "start_day": "Monday", "end_day": "Monday" }}
            ]
        }}

        **User:** "Strictly no more than 6 classes a day. Dr. Smith must teach AI to CSE-B on Tuesday Period 1."
        **Output:**
        {{
            "intent": "mixed",
            "constraints": {{
                "hard_constraints": {{ "max_classes_per_day_per_section": 6 }},
                "soft_constraints": {{}}
            }},
            "events": [
                {{ "type": "force_assignment", "faculty_id": "F_Smith", "subject_id": "SUB_AI", "section_id": "CSE_B", "day": "Tuesday", "timeslot": 1 }}
            ]
        }}
        """

    def _call_llm(self, system_prompt: str, user_text: str) -> str:
        headers = {"Authorization": f"Bearer {NLP_LLM_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": NLP_LLM_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"USER REQUEST: {user_text}"}
            ],
            "response_format": {"type": "json_object"}
        }
        
        resp = requests.post(NLP_LLM_API_URL, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']

    def parse_request(self, user_text: str) -> Dict[str, Any]:
        try:
            raw_json = self._call_llm(self._build_system_prompt(), user_text)
            # Basic cleanup
            if "```json" in raw_json:
                raw_json = raw_json.split("```json")[1].split("```")[0].strip()
            
            validated = NLPResponse.model_validate_json(raw_json)
            return validated.model_dump(exclude_none=True)
        except Exception as e:
            logger.error(f"NLP Error: {e}")
            return {"error": "Parsing Failed", "details": str(e)}