from collections import defaultdict
import copy
import json
import random
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set, Callable
from copy import deepcopy
from datetime import datetime
import logging
import threading
import time

# Minimal logging - suppress warnings during initialization
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

@dataclass(eq=True, frozen=True)
class TimeSlot:
    day: int
    period: int

    def __str__(self):
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        d = days[self.day] if 0 <= self.day < len(days) else f"D{self.day}"
        return f"{d}-P{self.period}"

@dataclass
class TimetableEntry:
    section_id: str
    subject_id: str
    faculty_id: str
    room_id: str
    time_slot: TimeSlot
    entry_type: str = "Theory"
    batch: str = ""
    lab_session_id: str = ""
    is_lab_second_period: bool = False
    is_elective: bool = False  # Flag for electives
    elective_group_id: Optional[str] = None  # New: Track elective group for multiples

class GenerationProgress:
    """Optimized progress tracker with initialization progress"""
    def __init__(self):
        self.current_generation = 0
        self.total_generations = 0
        self.best_fitness = 0.0
        self.avg_fitness = 0.0
        self.violations = {}
        self.status = "not_started"
        self.start_time = None
        self.end_time = None
        self.lock = threading.Lock()
        # Add initialization tracking
        self.initialization_progress = 0
        self.initialization_total = 0
        # Add early stopping info
        self.stagnation_count = 0
        self.early_stopped = False

    def update(self, generation, total_gens, best_fit, avg_fit, violations, status="running", stagnation_count=0):
        with self.lock:
            self.current_generation = generation
            self.total_generations = total_gens
            self.best_fitness = best_fit
            self.avg_fitness = avg_fit
            self.violations = violations
            self.status = status
            self.stagnation_count = stagnation_count
            if status == "running" and self.start_time is None:
                self.start_time = datetime.now()
            elif status == "completed" or status == "early_stopped":
                self.end_time = datetime.now()
                if status == "early_stopped":
                    self.early_stopped = True

    def update_initialization(self, current, total):
        with self.lock:
            self.initialization_progress = current
            self.initialization_total = total
            self.status = "initializing"

    def get_progress(self):
        with self.lock:
            progress = {
                'generation': self.current_generation,
                'total_generations': self.total_generations,
                'progress_percent': (self.current_generation / max(1, self.total_generations)) * 100,
                'best_fitness': self.best_fitness,
                'avg_fitness': self.avg_fitness,
                'violations': self.violations,
                'status': self.status,
                'initialization_progress': self.initialization_progress,
                'initialization_total': self.initialization_total,
                'stagnation_count': self.stagnation_count,
                'early_stopped': self.early_stopped
            }
            if self.start_time:
                progress['elapsed_time'] = str(datetime.now() - self.start_time)
            return progress

generation_progress = GenerationProgress()

class TimetableData:
    def __init__(self, config_file: str = None, config_dict: Dict = None, dynamic_events: List[Dict] = None):
        if config_dict:
            self.config = config_dict
        else:
            if not config_file:
                raise ValueError("Provide config_file or config_dict")
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except FileNotFoundError:
                raise FileNotFoundError(f"Configuration file {config_file} not found")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in configuration file: {e}")

        self.dynamic_events = dynamic_events or []
        self._validate_config()
        self._process()
        self._apply_dynamic_events()

    def _validate_config(self):
        """Streamlined validation"""
        required_sections = ['time_slots', 'departments', 'subjects', 'faculty', 'rooms']
        for section in required_sections:
            if section not in self.config:
                self.config[section] = self._get_default_section(section)

        ts_check = self.config.get('time_slots') or {}
        if not ts_check.get('periods'):
            self.config['time_slots'] = self._get_default_time_slots()

        # New: Validate elective slots
        if 'elective_slots' not in self.config:
            self.config['elective_slots'] = {}  # Default empty

    def _get_default_section(self, section_name: str) -> Dict:
        defaults = {
            'time_slots': {
                "periods": [
                    {"id": 1, "start_time": "08:30", "end_time": "09:20"},
                    {"id": 2, "start_time": "09:20", "end_time": "10:10"},
                    {"id": 3, "start_time": "10:10", "end_time": "11:00"},
                    {"id": 4, "start_time": "11:00", "end_time": "11:50"},
                    {"id": 5, "start_time": "11:50", "end_time": "12:40"},
                    {"id": 6, "start_time": "12:40", "end_time": "13:30"},
                    {"id": 7, "start_time": "13:30", "end_time": "14:20"},
                    {"id": 8, "start_time": "14:20", "end_time": "15:10"}
                ],
                "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            },
            'departments': [],
            'subjects': [],
            'faculty': [],
            'rooms': []
        }
        return defaults.get(section_name, {})

    def _get_default_time_slots(self) -> Dict:
        return {
            "periods": [
                {"id": 1, "start_time": "08:30", "end_time": "09:20"},
                {"id": 2, "start_time": "09:20", "end_time": "10:10"},
                {"id": 3, "start_time": "10:10", "end_time": "11:00"},
                {"id": 4, "start_time": "11:00", "end_time": "11:50"},
                {"id": 5, "start_time": "11:50", "end_time": "12:40"},
                {"id": 6, "start_time": "12:40", "end_time": "13:30"},
                {"id": 7, "start_time": "13:30", "end_time": "14:20"},
                {"id": 8, "start_time": "14:20", "end_time": "15:10"}
            ],
            "working_days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
        }

    def _apply_dynamic_events(self):
        """Optimized dynamic events processing"""
        if not self.dynamic_events:
            return

        for event in self.dynamic_events:
            event_type = event.get('type')
            if event_type == 'resource_unavailable':
                self._handle_resource_unavailable(event)
            elif event_type == 'faculty_leave':
                self._handle_faculty_leave(event)
            elif event_type == 'room_maintenance':
                self._handle_room_maintenance(event)

    def _handle_resource_unavailable(self, event):
        room_id = event.get('room_id')
        start_day = event.get('start_day')
        end_day = event.get('end_day')
        timeslots = event.get('timeslots', [])

        if room_id in self.rooms:
            if 'unavailable_periods' not in self.rooms[room_id]:
                self.rooms[room_id]['unavailable_periods'] = []
            for day in self._get_day_range(start_day, end_day):
                for period in timeslots:
                    self.rooms[room_id]['unavailable_periods'].append({
                        'day': day, 'period': period, 'reason': event.get('reason', 'maintenance')
                    })

    def _handle_faculty_leave(self, event):
        faculty_id = event.get('faculty_id')
        start_day = event.get('start_day')
        end_day = event.get('end_day')
        timeslots = event.get('timeslots', [])

        if faculty_id in self.faculty:
            if 'unavailable_periods' not in self.faculty[faculty_id]:
                self.faculty[faculty_id]['unavailable_periods'] = []
            for day in self._get_day_range(start_day, end_day):
                for period in timeslots:
                    self.faculty[faculty_id]['unavailable_periods'].append({
                        'day': day, 'period': period, 'reason': event.get('reason', 'leave')
                    })

    def _handle_room_maintenance(self, event):
        self._handle_resource_unavailable(event)

    def _get_day_range(self, start_day: str, end_day: str) -> List[int]:
        day_mapping = {day: idx for idx, day in enumerate(self.working_days)}
        start_idx = day_mapping.get(start_day, 0)
        end_idx = day_mapping.get(end_day, len(self.working_days) - 1)
        return list(range(start_idx, end_idx + 1))

    def _process(self):
        """Optimized data processing"""
        # Time slots processing
        ts = self.config.get('time_slots') or {}
        self.periods = ts.get('periods', []) or []
        self.period_ids = [p['id'] for p in self.periods]
        self.working_days = ts.get('working_days', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'])
        self.num_working_days = len(self.working_days)
        
        # Optimize break periods - reduce to minimum
        self.break_periods = set(ts.get('break_periods') or [])  # Only one break period
        self.lunch_break_periods = set(ts.get('lunch_break_periods') or [])
        self.mentorship_periods = set(ts.get('mentorship_periods') or [])

        # Legacy support
        if ts.get('lunch_period'):
            self.lunch_break_periods.add(ts['lunch_period'])
        if ts.get('mentorship_period'):
            self.mentorship_periods.add(ts['mentorship_period'])

        # Combine break periods but keep minimal
        self.break_periods.update(self.lunch_break_periods)
        self.break_periods.update(self.mentorship_periods)

        self.elective_slots = []
        elective_config = self.config.get("elective_slots", [])

        for slot_info in elective_config:
            try:
                day = self.working_days.index(slot_info["day_name"])
                period = slot_info["period"]
                self.elective_slots.append(TimeSlot(day, period))
            except:
                continue

        # Process data structures
        departments_list = self.config.get('departments') or []
        self.departments = {d['dept_id']: d for d in departments_list}
        self.sections = {}
        for d in departments_list:
            for s in (d.get('sections') or []):
                s.setdefault('student_count', 60)
                s.setdefault('room', None)
                s.setdefault('specialization', '')
                s.setdefault('semester', 1)
                s.setdefault('electives', [])  # New: List of elective subject_ids for this section
                self.sections[s['section_id']] = s

        for s in (self.config.get('sections') or []):
            s.setdefault('student_count', 60)
            s.setdefault('room', None)
            s.setdefault('specialization', '')
            s.setdefault('semester', 1)
            s.setdefault('electives', [])  # New
            self.sections[s['section_id']] = s
        self.subjects = {s['subject_id']: s for s in (self.config.get('subjects') or [])}
        self.labs = {l['lab_id']: l for l in (self.config.get('labs') or [])}
        self.faculty = {f['faculty_id']: f for f in (self.config.get('faculty') or [])}
        self.rooms = {r['room_id']: r for r in (self.config.get('rooms') or [])}

        # Set defaults
        for subject in self.subjects.values():
            subject.setdefault('lectures_per_week', 1)
            subject.setdefault('specialization', '')
            subject.setdefault('semester', None)
            subject.setdefault('departments', [])
            subject.setdefault('is_elective', False)

        for lab in self.labs.values():
            lab.setdefault('sessions_per_week', 2)
            lab.setdefault('specialization', '')
            lab.setdefault('semester', None)
            lab.setdefault('departments', [])
            # By default labs require two consecutive periods
            lab.setdefault('requires_consecutive_periods', 2)
            lab.setdefault('is_elective', False)

        # Build optimized mappings
        self.subject_name_mapping = self.config.get('subject_name_mapping') or {}
        self.subject_lookup = {}
        
        for subject_id, subject in self.subjects.items():
            self.subject_lookup[subject_id] = subject_id
            if subject.get('name'):
                self.subject_lookup[subject.get('name')] = subject_id

        for name, subject_id in self.subject_name_mapping.items():
            if name and subject_id:
                self.subject_lookup[name] = subject_id

        for lab_id, lab in self.labs.items():
            self.subject_lookup[lab_id] = lab_id
            if lab.get('name'):
                self.subject_lookup[lab.get('name')] = lab_id

        # Faculty-subject mapping
        self.faculty_subjects = {}
        for fid, faculty in self.faculty.items():
            subjects = set()
            for subject_ref in faculty.get('subjects', []):
                resolved_id = self._resolve_subject_reference(subject_ref)
                if resolved_id:
                    subjects.add(resolved_id)
                elif subject_ref in self.subjects or subject_ref in self.labs:
                    subjects.add(subject_ref)
            self.faculty_subjects[fid] = subjects

        # Section-department mapping
        self.section_department = {}
        for dept_id, dept in self.departments.items():
            for section in (dept.get('sections') or []):
                self.section_department[section['section_id']] = dept_id

        # Coordinator mapping
        self.coordinator_sections = {}
        self.section_coordinator = {}
        for section_id, section in self.sections.items():
            coordinator = section.get('coordinator')
            if coordinator:
                coordinator_id = None
                for fid, faculty in self.faculty.items():
                    if faculty.get('name') == coordinator:
                        coordinator_id = fid
                        break
                if coordinator_id:
                    if coordinator_id not in self.coordinator_sections:
                        self.coordinator_sections[coordinator_id] = []
                    self.coordinator_sections[coordinator_id].append(section_id)
                    # record reverse mapping for quick lookup
                    self.section_coordinator[section_id] = coordinator_id

        # Constraints and requirements
        constraints = self.config.get('constraints') or {}
        self.hard_constraints = constraints.get('hard_constraints') or {}
        self.soft_constraints = constraints.get('soft_constraints') or {}
        self.special_requirements = self.config.get('special_requirements') or {}
        self.ga_params = self.config.get('genetic_algorithm_params') or {}
        self.faculty_experience=self.config.get('faculty_experience',{})

    def _resolve_subject_reference(self, subject_ref: str) -> Optional[str]:
        if not subject_ref:
            return None
        if subject_ref in self.subject_lookup:
            return self.subject_lookup[subject_ref]
        # Case-insensitive lookup
        for key, value in self.subject_lookup.items():
            if key and key.lower() == subject_ref.lower():
                return value
        return None

    def is_faculty_available(self, faculty_id: str, day: int, period: int) -> bool:
        # Special marker for missing faculty - always available
        if faculty_id == "NO FACULTY FOUND":
            return False
        faculty = self.faculty.get(faculty_id)
        # If faculty is not present in the config, treat as available
        # This avoids blocking assignments when an unknown id appears in events
        if not faculty:
            return False
        unavailable_periods = faculty.get('unavailable_periods', [])
        for unavailable in unavailable_periods:
            if unavailable.get('day') == day and unavailable.get('period') == period:
                return False
        return True

    def is_room_available(self, room_id: str, day: int, period: int) -> bool:
        room = self.rooms.get(room_id)
        if not room:
            return False
        unavailable_periods = room.get('unavailable_periods', [])
        for unavailable in unavailable_periods:
            if unavailable.get('day') == day and unavailable.get('period') == period:
                return False
        return True

class TimetableChromosome:
    def __init__(self, data: TimetableData):
        self.data = data
        self.timetable: List[TimetableEntry] = []
        self.fitness_score: float = 0.0
        self.constraint_violations: Dict[str, int] = {}
        self._occupied_slots: Set[Tuple[str, int, int]] = set()
        self.required_classes_map = self._get_required_classes()
        self.fitness_breakdown = {}
        self.section_subject_faculty_map: Dict[Tuple[str, str], str] = {}
        self.faculty_workload: Dict[str, int] = {}

    def _is_conflict_free(self, section_id: str, faculty_id: str, room_id: str, time_slot: TimeSlot) -> bool:
        if time_slot.period in self.data.break_periods:
            return False
        if faculty_id and not self.data.is_faculty_available(faculty_id, time_slot.day, time_slot.period):
            return False
        if room_id and not self.data.is_room_available(room_id, time_slot.day, time_slot.period):
            return False

        keys = [
            (faculty_id, time_slot.day, time_slot.period),
            (room_id, time_slot.day, time_slot.period),
            (section_id, time_slot.day, time_slot.period)
        ]
        return not any(key in self._occupied_slots for key in keys if key[0])

    def _is_lab_conflict_free(self, section_id: str, faculty_id: str, room_id: str, time_slot1: TimeSlot, time_slot2: TimeSlot) -> bool:
        return (self._is_conflict_free(section_id, faculty_id, room_id, time_slot1) and
                self._is_conflict_free(section_id, faculty_id, room_id, time_slot2))

    def _add_to_occupied(self, entry: TimetableEntry):
        time_slot = entry.time_slot
        if entry.faculty_id:
            self._occupied_slots.add((entry.faculty_id, time_slot.day, time_slot.period))
            self.faculty_workload[entry.faculty_id] = self.faculty_workload.get(entry.faculty_id, 0) + 1
        if entry.room_id:
            self._occupied_slots.add((entry.room_id, time_slot.day, time_slot.period))
        self._occupied_slots.add((entry.section_id, time_slot.day, time_slot.period))

    def _remove_from_occupied(self, entry: TimetableEntry):
        time_slot = entry.time_slot
        if entry.faculty_id:
            self._occupied_slots.discard((entry.faculty_id, time_slot.day, time_slot.period))
            if entry.faculty_id in self.faculty_workload:
                self.faculty_workload[entry.faculty_id] = max(0, self.faculty_workload[entry.faculty_id] - 1)
        if entry.room_id:
            self._occupied_slots.discard((entry.room_id, time_slot.day, time_slot.period))
        self._occupied_slots.discard((entry.section_id, time_slot.day, time_slot.period))

    def _subject_applies_to_section(self, subject: Dict, section: Dict) -> bool:
        subject_depts = subject.get('departments', [])
        if subject_depts:
            section_dept = self.data.section_department.get(section['section_id'])
            if section_dept and section_dept not in subject_depts:
                return False
        return True

    def _get_required_classes(self) -> Dict[str, List[Dict]]:
        """Enhanced: Support multiple electives per section via section['electives'] list."""
        req = {}
        for section_id, section in self.data.sections.items():
            semester = section.get('semester', 1)
            req[section_id] = []
            elective_group_id = f"{section_id}_electives"  # Unique group per section
            
            # Core theory subjects
            for subj in self.data.subjects.values():
                if self._subject_applies_to_section(subj, section) and not subj.get('is_elective', False):
                    classes_per_week = subj.get('min_classes_per_week', subj.get('lectures_per_week', 1))
                    try:
                        classes_per_week = max(1, int(classes_per_week))
                    except Exception:
                        classes_per_week = 1
                    for _ in range(classes_per_week):
                        req[section_id].append({'subject_id': subj['subject_id'], 'type': 'Theory'})

            # Core labs
            for lab in self.data.labs.values():
                if self._subject_applies_to_section(lab, section) and not lab.get('is_elective', False):
                    sessions = lab.get('min_classes_per_week', lab.get('sessions_per_week', 2))
                    try:
                        sessions = int(sessions)
                    except Exception:
                        sessions = int(lab.get('sessions_per_week', 2))
                    req_len = lab.get('requires_consecutive_periods', 2)
                    for session_num in range(sessions):
                        lab_session_id = f"{lab['lab_id']}_S{section_id}_{session_num}"
                        req[section_id].append({
                            'subject_id': lab['lab_id'],
                            'type': 'Lab',
                            'is_lab_session': True,
                            'lab_session_id': lab_session_id,
                            'requires_consecutive_periods': req_len
                        })

            # Electives: From section['electives'] list or auto-pool
            elective_subjects = [s for s in self.data.subjects.values()
                     if s.get('is_elective', False)]
            section_electives = section.get('electives', [])  # e.g., ["AI_ETHICS", "BLOCKCHAIN"]
            num_electives = len(section_electives) or 1  # Default 1 if empty
            elective_pool = {sid: subj for sid, subj in self.data.subjects.items() if subj.get('is_elective', False) and subj.get('semester') == semester}
            
            for i in range(num_electives):
                if section_electives:
                    elective_id = section_electives[i % len(section_electives)]  # Cycle if more than available
                else:
                    elective_id = random.choice(list(elective_pool.keys())) if elective_pool else None
                
                if elective_id and elective_id in elective_pool:
                    req[section_id].append({
                        'subject_id': elective_id,
                        'type': 'Theory',
                        'is_elective': True,
                        'fixed_slot': True,
                        'elective_group_id': elective_group_id
                    })

        return req
    
    def _is_valid_elective_slot(self, entry: TimetableEntry) -> bool:
        """Electives must be placed ONLY in allowed elective slots."""
        if not entry.is_elective:
            return True  # Not elective → always OK

        slot = entry.time_slot
        return any(
            s.day == slot.day and s.period == slot.period
            for s in self.data.elective_slots
        )
    
    def _is_regular_in_elective_slot(self, entry: TimetableEntry) -> bool:
        """Regular subjects must not be placed in elective slots."""
        if entry.is_elective:
            return False
        slot = entry.time_slot
        return any(
            s.day == slot.day and s.period == slot.period
            for s in self.data.elective_slots
        )


    def _get_appropriate_room(self, section_id: str, class_info: Dict) -> Optional[str]:
        """Optimized room assignment with fallbacks"""
        section = self.data.sections.get(section_id, {})
        student_count = section.get('student_count', 60)

        if class_info['type'] == 'Lab':
            # Try to find lab room
            lab = self.data.labs.get(class_info['subject_id'])
            if lab and lab.get('lab_rooms'):
                return lab['lab_rooms'][0]  # Just use first available
            
            # Fallback: any room marked as lab
            for rid, room in self.data.rooms.items():
                if room.get('type', '').lower() in ['lab', 'laboratory']:
                    return rid
            
            # Last resort: use any room for lab
            if self.data.rooms:
                return list(self.data.rooms.keys())[0]

        # Regular classroom
        designated_room = section.get('room')
        if designated_room and designated_room in self.data.rooms:
            return designated_room

        # Find any suitable room
        for rid, room in self.data.rooms.items():
            if room.get('capacity', 100) >= student_count:
                return rid

        # Fallback to any room
        if self.data.rooms:
            return list(self.data.rooms.keys())[0]
        return f"Room-{section_id}"

    def _get_eligible_faculty(self, subject_id: str, section_id: str = None) -> List[str]:
        """Optimized faculty selection with combined workload + experience scoring"""
        eligible = []

        # Quick check for existing assignment
        section_subject_key = (section_id, subject_id) if section_id else None
        if section_subject_key and section_subject_key in self.section_subject_faculty_map:
            return [self.section_subject_faculty_map[section_subject_key]]

        # Direct subject match
        for fid, subjects in self.data.faculty_subjects.items():
            if subject_id in subjects:
                eligible.append(fid)

        # If section has a coordinator who can teach this subject, prefer them
        if section_id:
            coord_id = self.data.section_coordinator.get(section_id)
            if coord_id:
                force = self.data.special_requirements.get('force_coordinator_assignments', True)
                if coord_id in eligible:
                    if force:
                        return [coord_id]
                    # Move coordinator to front
                    eligible = [coord_id] + [f for f in eligible if f != coord_id]

        # ---- NEW EXPERIENCE + WORKLOAD PRIORITY LOGIC ----
        if len(eligible) > 1:

            # List A: sort by workload (ascending)
            workload_sorted = sorted(
                eligible,
                key=lambda fid: self.faculty_workload.get(fid, 0)
            )

            # List B: sort by experience (descending)
            exp_sorted = sorted(
                eligible,
                key=lambda fid: self.data.faculty_experience.get(fid, 0),
                reverse=True
            )

            # Create index lookup dictionaries
            workload_index = {fid: i for i, fid in enumerate(workload_sorted)}
            exp_index = {fid: i for i, fid in enumerate(exp_sorted)}

            # Compute combined priority score
            eligible = sorted(
                eligible,
                key=lambda fid: workload_index[fid] + exp_index[fid]
            )

        # No faculty found
        if not eligible:
            eligible = ["NO FACULTY FOUND"]

        return eligible

    def _get_consecutive_slots(self, day: int) -> List[Tuple[TimeSlot, TimeSlot]]:
        """Find consecutive slot sequences for a given day.

        Returns a list of tuples of TimeSlot objects for consecutive runs of length N.
        Backwards-compatible default remains pairs (length==2).
        """
        consecutive_pairs = []
        available_periods = [p for p in self.data.period_ids if p not in self.data.break_periods]

        # build runs of consecutive periods
        runs = []
        if not available_periods:
            return []

        current_run = [available_periods[0]]
        for p in available_periods[1:]:
            if p == current_run[-1] + 1:
                current_run.append(p)
            else:
                runs.append(current_run)
                current_run = [p]
        runs.append(current_run)

        # By default return pairs (length==2) - caller can filter by desired length
        for run in runs:
            if len(run) >= 2:
                for i in range(len(run) - 1):
                    slot1 = TimeSlot(day, run[i])
                    slot2 = TimeSlot(day, run[i + 1])
                    consecutive_pairs.append((slot1, slot2))

        return consecutive_pairs

    def initialize_random(self, max_attempts_per_class: int = 20):
        """Initialization with elective grouping, labs, theory, and fallback logic."""
        self.timetable = []
        self._occupied_slots = set()
        self.constraint_violations = {}
        self.section_subject_faculty_map = {}
        self.faculty_workload = {}

        slots = [
            TimeSlot(d, p)
            for d in range(self.data.num_working_days)
            for p in self.data.period_ids
            if p not in self.data.break_periods
        ]

        if not slots:
            return

        placement_stats = {
            'placed': 0, 'failed': 0,
            'lab_placed': 0, 'lab_failed': 0,
            'elective_placed': 0, 'elective_failed': 0
        }

        # -----------------------------
        # 1. BUILD ELECTIVE GROUPS FIRST
        # -----------------------------
        elective_groups = defaultdict(list)

        for section_id, classes in self.required_classes_map.items():
            for c in classes:
                if c.get("is_elective"):
                    elective_groups[c["elective_group_id"]].append(
                        (section_id, c)
                    )

        # -----------------------------
        # 2. PLACE EACH ELECTIVE GROUP IN ONE FIXED SLOT
        # -----------------------------
        for group_id, group_items in elective_groups.items():

            placed_group = False

            for slot in self.data.elective_slots:   # VERY IMPORTANT
                group_ok = True
                tentative_entries = []

                for (section_id, c) in group_items:
                    eligible_faculty = self._get_eligible_faculty(c["subject_id"], section_id)
                    faculty_id = eligible_faculty[0]
                    room_id = self._get_appropriate_room(section_id, c)

                    if not self._is_conflict_free(section_id, faculty_id, room_id, slot):
                        group_ok = False
                        break

                    tentative_entries.append(
                        TimetableEntry(
                            section_id=section_id,
                            subject_id=c["subject_id"],
                            faculty_id=faculty_id,
                            room_id=room_id,
                            time_slot=slot,
                            entry_type='Elective',
                            is_elective=True
                        )
                    )

                if group_ok:
                    for e in tentative_entries:
                        self.timetable.append(e)
                        self._add_to_occupied(e)
                    placed_group = True
                    break

            if not placed_group:
                placement_stats["elective_failed"] += 1

        # -----------------------------
        # 3. NORMAL PLACEMENT: LAB + THEORY
        # -----------------------------
        for section_id, classes in self.required_classes_map.items():
            for class_info in classes:

                # Skip electives (already placed)
                if class_info.get("is_elective"):
                    continue

                eligible_faculty = self._get_eligible_faculty(class_info['subject_id'], section_id)
                if not eligible_faculty:
                    placement_stats['failed'] += 1
                    continue

                room_id = self._get_appropriate_room(section_id, class_info)
                if not room_id:
                    placement_stats['failed'] += 1
                    continue

                # -----------------------------
                # LAB PLACEMENT
                # -----------------------------
                if class_info.get('is_lab_session', False):
                    placed = False
                    req_len = int(class_info.get('requires_consecutive_periods', 2))

                    days = list(range(self.data.num_working_days))
                    random.shuffle(days)

                    for day in days:
                        period_list = [
                            p for p in self.data.period_ids
                            if p not in self.data.break_periods
                        ]

                        sequences = []
                        run = [period_list[0]]
                        for p in period_list[1:]:
                            if p == run[-1] + 1:
                                run.append(p)
                            else:
                                if len(run) >= req_len:
                                    for i in range(len(run) - req_len + 1):
                                        seq = run[i:i+req_len]
                                        sequences.append([TimeSlot(day, q) for q in seq])
                                run = [p]

                        if len(run) >= req_len:
                            for i in range(len(run) - req_len + 1):
                                seq = run[i:i+req_len]
                                sequences.append([TimeSlot(day, q) for q in seq])

                        random.shuffle(sequences)

                        for seq in sequences:
                            faculty_id = eligible_faculty[0]

                            if all(self._is_conflict_free(section_id, faculty_id, room_id, s) for s in seq):
                                entries = []
                                for i, sl in enumerate(seq):
                                    entries.append(
                                        TimetableEntry(
                                            section_id=section_id,
                                            subject_id=class_info['subject_id'],
                                            faculty_id=faculty_id,
                                            room_id=room_id,
                                            time_slot=sl,
                                            entry_type="Lab",
                                            lab_session_id=class_info["lab_session_id"],
                                            is_lab_second_period=(i != 0)
                                        )
                                    )
                                for e in entries:
                                    self.timetable.append(e)
                                    self._add_to_occupied(e)

                                placement_stats["lab_placed"] += 1
                                placed = True
                                break
                        if placed:
                            break

                    if not placed:
                        placement_stats["lab_failed"] += 1

                # -----------------------------
                # THEORY PLACEMENT
                # -----------------------------
                else:
                    placed = False
                    for _ in range(max_attempts_per_class):
                        slot = random.choice(slots)
                        faculty_id = eligible_faculty[0]

                        if self._is_conflict_free(section_id, faculty_id, room_id, slot):
                            entry = TimetableEntry(
                                section_id=section_id,
                                subject_id=class_info['subject_id'],
                                faculty_id=faculty_id,
                                room_id=room_id,
                                time_slot=slot,
                                entry_type='Theory'
                            )
                            self.timetable.append(entry)
                            self._add_to_occupied(entry)
                            placement_stats['placed'] += 1
                            placed = True
                            break

                    if not placed:
                        placement_stats['failed'] += 1

        self.calculate_fitness()

    def _section_classes_on_day(self, section_id: str, day: int) -> int:
        """Return number of scheduled periods for a section on a given day."""
        return len([e for e in self.timetable if e.section_id == section_id and e.time_slot.day == day])

    def _subject_classes_on_day(self, section_id: str, subject_id: str, day: int) -> int:
        """Return number of scheduled periods for a given subject in a section on a given day."""
        return len([e for e in self.timetable if e.section_id == section_id and e.subject_id == subject_id and e.time_slot.day == day])

    def _check_hard_constraints(self) -> Dict[str, int]:
        """Optimized constraint checking with lab continuity"""
        violations = {}
        faculty_slots = {}
        room_slots = {}
        section_slots = {}

        # ----------------------------------------------------
        # 1. FACULTY / ROOM / SECTION CLASH CHECKS
        # ----------------------------------------------------
        for entry in self.timetable:
            key = (entry.time_slot.day, entry.time_slot.period)

            # Faculty clash
            if entry.faculty_id:
                if entry.faculty_id not in faculty_slots:
                    faculty_slots[entry.faculty_id] = set()
                if key in faculty_slots[entry.faculty_id]:
                    violations['faculty_clash'] = violations.get('faculty_clash', 0) + 1
                faculty_slots[entry.faculty_id].add(key)

            # Room clash
            if entry.room_id:
                if entry.room_id not in room_slots:
                    room_slots[entry.room_id] = set()
                if key in room_slots[entry.room_id]:
                    violations['room_clash'] = violations.get('room_clash', 0) + 1
                room_slots[entry.room_id].add(key)

            # Section clash
            if entry.section_id not in section_slots:
                section_slots[entry.section_id] = set()
            if key in section_slots[entry.section_id]:
                violations['section_clash'] = violations.get('section_clash', 0) + 1
            section_slots[entry.section_id].add(key)

        for section_id, classes in self.required_classes_map.items():
            lab_sessions = [c for c in classes if c.get('is_lab_session')]

            for lab in lab_sessions:
                lab_id = lab['lab_session_id']
                req_len = lab['requires_consecutive_periods']

                assigned = sorted(
                    [e for e in self.timetable if e.lab_session_id == lab_id],
                    key=lambda x: (x.time_slot.day, x.time_slot.period)
                )

                if len(assigned) != req_len:
                    violations['lab_continuity'] = violations.get('lab_continuity', 0) + 1
                else:
                    is_consecutive = True
                    for i in range(len(assigned)-1):
                        p1 = assigned[i].time_slot
                        p2 = assigned[i+1].time_slot
                        if not (p1.day == p2.day and p2.period == p1.period + 1):
                            is_consecutive = False
                            break

                    if not is_consecutive:
                        violations['lab_continuity'] = violations.get('lab_continuity', 0) + 1

        return violations

    def _check_soft_constraints(self) -> Dict[str, float]:
        """Simplified soft constraint checking"""
        scores = {}

        # Balanced daily load
        balance_score = 0.0
        for section_id in self.data.sections.keys():
            daily_loads = [0] * self.data.num_working_days
            for entry in self.timetable:
                if entry.section_id == section_id:
                    daily_loads[entry.time_slot.day] += 1
            if daily_loads:
                std_dev = float(np.std(daily_loads))
                balance_score += max(0.0, 2.0 - std_dev)
        scores['balanced_daily_load'] = balance_score

        return scores

    
    def calculate_fitness(self) -> float:
        """
        Final merged fitness function (NO balanced load constraint):
        - Normal coverage reward
        - Elective coverage reward
        - Elective slot violations (strict)
        - Lab continuity violations
        - Clash penalties (faculty / room / section)
        """

        # ----------------------------------------------------
        # HARD CONSTRAINT VIOLATIONS (includes lab continuity)
        # ----------------------------------------------------
        self.constraint_violations = self._check_hard_constraints()

        # ----------------------------------------------------
        # ELECTIVE SLOT VIOLATIONS
        # ----------------------------------------------------
        elective_slot_violation = 0
        for e in self.timetable:

            # Elective must be inside an elective slot
            if e.is_elective and not self._is_valid_elective_slot(e):
                elective_slot_violation += 1

            # Regular class must NOT occupy an elective slot
            if not e.is_elective and self._is_regular_in_elective_slot(e):
                elective_slot_violation += 1

        if elective_slot_violation > 0:
            self.constraint_violations['elective_slot_violation'] = elective_slot_violation
        else:
            self.constraint_violations.pop('elective_slot_violation', None)

        # ----------------------------------------------------
        # COVERAGE REWARD
        # ----------------------------------------------------
        total_required = sum(len(classes) for classes in self.required_classes_map.values())
        scheduled = len([e for e in self.timetable if not e.is_lab_second_period])
        coverage_ratio = scheduled / max(1, total_required)

        reward = coverage_ratio * 800.0

        # ----------------------------------------------------
        # ELECTIVE COVERAGE REWARD
        # ----------------------------------------------------
        elective_required = sum(
            1 for classes in self.required_classes_map.values()
            for c in classes if c.get("is_elective")
        )

        elective_scheduled = sum(
            1 for e in self.timetable
            if getattr(e, "is_elective", False)
        )

        elective_ratio = elective_scheduled / max(1, elective_required)
        reward += elective_ratio * 600.0   # Strong elective reward

        # ----------------------------------------------------
        # (Soft constraints removed completely)
        # ----------------------------------------------------

        # ----------------------------------------------------
        # PENALTIES
        # ----------------------------------------------------
        penalty = 0.0

        # Faculty / Room / Section clashes
        penalty += self.constraint_violations.get("faculty_clash", 0) * 1000.0
        penalty += self.constraint_violations.get("room_clash", 0) * 1000.0
        penalty += self.constraint_violations.get("section_clash", 0) * 1000.0

        # Elective slot violation penalty
        penalty += elective_slot_violation * 2000.0

        # Lab continuity penalty
        penalty += self.constraint_violations.get("lab_continuity", 0) * 1500.0

        # ----------------------------------------------------
        # FINAL FITNESS
        # ----------------------------------------------------
        self.fitness_score = max(1.0, reward - penalty)
        return self.fitness_score

    def mutate(self):
        mutation_rate = self.data.ga_params.get('mutation_rate', 0.2)
        if random.random() >= mutation_rate:
            return

        # -------------------------------------------------------
        # 1. FIX BROKEN LABS BEFORE ANY OTHER MUTATION
        # -------------------------------------------------------
        for section_id, classes in self.required_classes_map.items():
            lab_sessions = [c for c in classes if c.get('is_lab_session')]
            
            for lab in lab_sessions:
                lab_id = lab['lab_session_id']
                req_len = lab['requires_consecutive_periods']

                # Get all assigned instances
                assigned = sorted(
                    [e for e in self.timetable if e.lab_session_id == lab_id],
                    key=lambda x: (x.time_slot.day, x.time_slot.period)
                )

                # Check if already valid
                if len(assigned) == req_len:
                    good = True
                    for i in range(len(assigned)-1):
                        p1 = assigned[i].time_slot
                        p2 = assigned[i+1].time_slot
                        if not (p1.day == p2.day and p2.period == p1.period + 1):
                            good = False
                            break
                    if good:
                        continue

                # LAB IS BROKEN → FIX IT

                # Remove old placements
                for e in assigned:
                    self._remove_from_occupied(e)
                    self.timetable.remove(e)

                # Attempt to place lab properly
                faculty_id = self._get_eligible_faculty(lab['subject_id'], section_id)[0]
                room_id = self._get_appropriate_room(section_id, lab)

                # Search for valid sequences
                placed = False
                for day in random.sample(range(self.data.num_working_days), self.data.num_working_days):
                    periods = [p for p in self.data.period_ids if p not in self.data.break_periods]

                    # Build consecutive sequences
                    seqs = []
                    run = [periods[0]]
                    for p in periods[1:]:
                        if p == run[-1] + 1:
                            run.append(p)
                        else:
                            if len(run) >= req_len:
                                for i in range(len(run) - req_len + 1):
                                    seq = run[i:i+req_len]
                                    seqs.append([TimeSlot(day, q) for q in seq])
                            run = [p]

                    if len(run) >= req_len:
                        for i in range(len(run) - req_len + 1):
                            seq = run[i:i+req_len]
                            seqs.append([TimeSlot(day, q) for q in seq])

                    random.shuffle(seqs)

                    for seq in seqs:
                        # Check all consecutive slots are conflict free
                        if all(self._is_conflict_free(section_id, faculty_id, room_id, s) for s in seq):
                            # Place lab properly
                            for j, sl in enumerate(seq):
                                new_entry = TimetableEntry(
                                    section_id=section_id,
                                    subject_id=lab['subject_id'],
                                    faculty_id=faculty_id,
                                    room_id=room_id,
                                    time_slot=sl,
                                    entry_type="Lab",
                                    lab_session_id=lab_id,
                                    is_lab_second_period=(j != 0)
                                )
                                self.timetable.append(new_entry)
                                self._add_to_occupied(new_entry)

                            placed = True
                            break
                    if placed:
                        break

        # -------------------------------------------------------
        # 2. MUTATE NORMAL THEORY ENTRIES (existing behavior)
        # -------------------------------------------------------
        eligible_entries = [
            e for e in self.timetable 
            if not e.is_lab_second_period and not e.is_elective
        ]
        if not eligible_entries:
            return

        entry = random.choice(eligible_entries)
        original_slot = entry.time_slot

        available_slots = [
            TimeSlot(d, p)
            for d in range(self.data.num_working_days)
            for p in self.data.period_ids
            if p not in self.data.break_periods
        ]

        for attempt in range(5):
            new_slot = random.choice(available_slots)

            # Avoid elective slots
            if any(es.day == new_slot.day and es.period == new_slot.period
                    for es in self.data.elective_slots):
                continue

            self._remove_from_occupied(entry)

            if self._is_conflict_free(entry.section_id, entry.faculty_id, entry.room_id, new_slot):
                entry.time_slot = new_slot
                self._add_to_occupied(entry)
                break
            else:
                self._add_to_occupied(entry)

        # -------------------------------------------------------
        # 3. Recalculate fitness
        # -------------------------------------------------------
        self.calculate_fitness()


    def crossover(self, other: 'TimetableChromosome') -> 'TimetableChromosome':
        """Simplified crossover"""
        child = TimetableChromosome(self.data)
        child._occupied_slots = set()
        child.section_subject_faculty_map = {}
        child.faculty_workload = {}

        # Simple approach: take half from each parent
        all_entries = self.timetable + other.timetable
        random.shuffle(all_entries)
        
        for entry in all_entries:

            # ----------------------------------------------
            # Elective must remain inside valid elective slot
            # ----------------------------------------------
            if entry.is_elective and not child._is_valid_elective_slot(entry):
                continue   # Reject inheritance of elective placed outside designated slot

            # --------------------------------------------------------------
            # Regular class cannot be placed inside ANY elective slot
            # --------------------------------------------------------------
            if not entry.is_elective and child._is_regular_in_elective_slot(entry):
                continue   # Reject this entry entirely

            # ----------------------------------------------
            # Existing code continues normally from here
            # ----------------------------------------------

            sec_sub_key = (entry.section_id, entry.subject_id)
            existing_fac = child.section_subject_faculty_map.get(sec_sub_key)

            # prefer existing mapping if present
            chosen_fac = entry.faculty_id
            if existing_fac and existing_fac != entry.faculty_id:
                # try to remap faculty to existing_fac if conflict-free
                if child._is_conflict_free(entry.section_id, existing_fac, entry.room_id, entry.time_slot):
                    chosen_fac = existing_fac
                else:
                    # skip this entry to avoid assigning a different faculty for same subject
                    continue

            if child._is_conflict_free(entry.section_id, chosen_fac, entry.room_id, entry.time_slot):
                # enforce per-subject per-day limit in child (subject-level override, default 2)
                subj_obj = self.data.subjects.get(entry.subject_id) or self.data.labs.get(entry.subject_id)
                if subj_obj and subj_obj.get('max_classes_per_day') is not None:
                    max_subj_per_day = int(subj_obj.get('max_classes_per_day'))
                else:
                    max_subj_per_day = int(self.data.hard_constraints.get('max_classes_per_subject_per_day',
                                                                          self.data.hard_constraints.get('max_classes_per_subject', 2)))
                current_subj_count = len([e for e in child.timetable if e.section_id == entry.section_id and e.subject_id == entry.subject_id and e.time_slot.day == entry.time_slot.day])
                if current_subj_count + 1 > max_subj_per_day:
                    # skip adding this entry to avoid exceeding per-subject daily limit
                    continue
                new_entry = TimetableEntry(
                    section_id=entry.section_id, subject_id=entry.subject_id,
                    faculty_id=chosen_fac, room_id=entry.room_id,
                    time_slot=entry.time_slot, entry_type=entry.entry_type,
                    lab_session_id=entry.lab_session_id,
                    is_lab_second_period=entry.is_lab_second_period
                )
                child.timetable.append(new_entry)
                child._add_to_occupied(new_entry)
                # ensure mapping set
                child.section_subject_faculty_map[sec_sub_key] = chosen_fac

        child.calculate_fitness()
        return child
    
    

class GeneticAlgorithm:
    def __init__(self, data: TimetableData, progress_callback: Callable = None):
        self.data = data
        self.population: List[TimetableChromosome] = []
        self.best_solution: Optional[TimetableChromosome] = None
        self.generation_stats: List[Dict] = []
        self.progress_callback = progress_callback

    def initialize_population(self):
        """Fast population initialization with progress tracking"""
        pop_size = min(30, int(self.data.ga_params.get('population_size', 30)))  # Reduced size
        self.population = []
        
        generation_progress.update_initialization(0, pop_size)
        
        for i in range(pop_size):
            chromosome = TimetableChromosome(self.data)
            chromosome.initialize_random()
            self.population.append(chromosome)
            
            # Update initialization progress
            generation_progress.update_initialization(i + 1, pop_size)
            
            # Small sleep for responsiveness
            if i % 5 == 0:
                time.sleep(0.01)

    def tournament_selection(self, tournament_size: int = 3) -> TimetableChromosome:
        tournament = random.sample(self.population, min(tournament_size, len(self.population)))
        return max(tournament, key=lambda x: x.fitness_score)

    def evolve(self):
        """Optimized evolution loop with stagnation-based early stopping"""
        generations = min(100, int(self.data.ga_params.get('generations', 100)))  # Allow more generations
        elite_size = min(3, int(self.data.ga_params.get('elite_size', 3)))
        crossover_rate = float(self.data.ga_params.get('crossover_rate', 0.8))
        stagnation_limit = 5  # Early stopping after 5 generations without improvement
        
        best_fitness = float('-inf')
        stagnation_count = 0

        generation_progress.update(0, generations, 0, 0, {}, "running", stagnation_count)

        for generation in range(generations):
            # Sort population by fitness
            self.population.sort(key=lambda x: x.fitness_score, reverse=True)
            current_best = self.population[0]

            # Track best solution and stagnation
            if current_best.fitness_score > best_fitness:
                best_fitness = current_best.fitness_score
                self.best_solution = deepcopy(current_best)
                stagnation_count = 0  # Reset stagnation counter
                print(f"Gen {generation}: New best fitness {best_fitness:.2f}")
            else:
                stagnation_count += 1

            # Calculate statistics
            fitness_scores = [c.fitness_score for c in self.population]
            avg_fitness = float(np.mean(fitness_scores))

            # Update progress frequently with stagnation info
            generation_progress.update(
                generation + 1, generations, best_fitness, avg_fitness,
                current_best.constraint_violations, "running", stagnation_count
            )

            # Early stopping check
            if stagnation_count >= stagnation_limit:
                print(f"Early stopping at generation {generation}: No improvement for {stagnation_limit} generations")
                generation_progress.update(
                    generation + 1, generations, best_fitness, avg_fitness,
                    self.best_solution.constraint_violations if self.best_solution else {},
                    "early_stopped", stagnation_count
                )
                break

            # Small sleep for smooth progress
            if generation % 2 == 0:
                time.sleep(0.02)

            # Create next generation
            new_population = []
            
            # Elitism
            new_population.extend([deepcopy(c) for c in self.population[:elite_size]])

            # Generate offspring
            while len(new_population) < len(self.population):
                parent1 = self.tournament_selection()
                parent2 = self.tournament_selection()
                
                if random.random() < crossover_rate:
                    child = parent1.crossover(parent2)
                else:
                    child = deepcopy(parent1)

                child.mutate()
                new_population.append(child)

            self.population = new_population

        # Final update if not early stopped
        if stagnation_count < stagnation_limit:
            generation_progress.update(
                generations, generations, best_fitness, avg_fitness,
                self.best_solution.constraint_violations if self.best_solution else {},
                "completed", stagnation_count
            )
        
        print(f"Evolution finished. Best fitness: {best_fitness:.2f}")
        if generation_progress.early_stopped:
            print(f"Early stopped due to stagnation after {stagnation_count} generations")

    def get_top_solutions(self, n: int = 3):
        # Sort population by real fitness
        sorted_pop = sorted(
            self.population,
            key=lambda ch: ch.fitness_score,
            reverse=True
        )

        top = sorted_pop[:n]

        final_chromosomes: List[TimetableChromosome] = []
        last_real_fitness = None
        last_display_fitness = None

        for ch in top:
            real_f = ch.fitness_score

            # Make a shallow copy so GA is not affected
            new_ch = copy.copy(ch)

            if last_real_fitness is None:
                # first one – show real fitness
                display_f = real_f
            else:
                if real_f == last_real_fitness:
                    # same REAL fitness as previous → decrease by 1 from previous DISPLAY
                    display_f = last_display_fitness - 1
                else:
                    # different fitness → you can just show real_f
                    display_f = real_f

            new_ch.fitness_score = display_f

            last_real_fitness = real_f
            last_display_fitness = display_f
            final_chromosomes.append(new_ch)

        return final_chromosomes

    def get_best_solution(self) -> Optional[TimetableChromosome]:
        return self.get_top_solutions(3)

    def get_progress(self) -> dict:
        return generation_progress.get_progress()

class TimetableExporter:
    def __init__(self, solution: TimetableChromosome, data: TimetableData):
        self.solution = solution
        self.data = data

    def _time_str(self, period: int) -> str:
        period_info = next((p for p in self.data.periods if p['id'] == period), None)
        if period_info:
            return f"{period_info.get('start_time', '')}-{period_info.get('end_time', '')}"
        return f"P{period}"
    
    def _format_faculty_display(self, entry, faculty_name):
        """
        Format faculty display - show 'OE' for electives, faculty name otherwise
        """
        if entry.is_elective or entry.entry_type == 'Elective':
            return "OE"
        return faculty_name

    def get_section_wise_data(self) -> Dict[str, Dict]:
        """Optimized section-wise data export with OE display"""
        section_data = {}
        
        for section_id, section in self.data.sections.items():
            section_entries = [e for e in self.solution.timetable if e.section_id == section_id]
            
            weekly_schedule = {}
            for day in range(self.data.num_working_days):
                day_name = self.data.working_days[day]
                weekly_schedule[day_name] = {}
                
                for period in self.data.period_ids:
                    if period in self.data.lunch_break_periods:
                        weekly_schedule[day_name][period] = "LUNCH BREAK"
                    elif period in self.data.break_periods:
                        weekly_schedule[day_name][period] = "BREAK"
                    else:
                        weekly_schedule[day_name][period] = "FREE"

            for entry in section_entries:
                if 0 <= entry.time_slot.day < len(self.data.working_days):
                    day_name = self.data.working_days[entry.time_slot.day]
                    period = entry.time_slot.period
                    
                    subject = self.data.subjects.get(entry.subject_id)
                    lab = self.data.labs.get(entry.subject_id)
                    subject_name = (subject.get('name') if subject else
                                  lab.get('name') if lab else entry.subject_id)
                    
                    faculty = self.data.faculty.get(entry.faculty_id, {})
                    faculty_name = faculty.get('name', entry.faculty_id or 'TBA')
                    
                    # Use the new formatting method
                    display_faculty = self._format_faculty_display(entry, faculty_name)
                    
                    class_info = {
                        "subject": subject_name,
                        "faculty": display_faculty,  # Changed: Shows "OE" for electives
                        "room": entry.room_id or 'TBA',
                        "type": entry.entry_type
                    }
                    weekly_schedule[day_name][period] = class_info

            section_data[section_id] = {
                "section_id": section_id,
                "section_name": section.get('name', section_id),
                "specialization": section.get('specialization', ''),
                "semester": section.get('semester', ''),
                "coordinator": section.get('coordinator', ''),
                "student_count": section.get('student_count', 0),
                "room": section.get('room', ''),
                "timetable": weekly_schedule,
                "periods": {p: self._time_str(p) for p in self.data.period_ids}
            }

        return section_data

    def get_faculty_wise_data(self) -> Dict[str, Dict]:
        """Faculty-wise data - keeps actual faculty names (no OE here)"""
        faculty_data = {}
        
        for faculty_id, faculty_info in self.data.faculty.items():
            faculty_entries = [e for e in self.solution.timetable if e.faculty_id == faculty_id]
            
            weekly_schedule = {}
            placed_map = {}
            
            for day in range(self.data.num_working_days):
                day_name = self.data.working_days[day]
                weekly_schedule[day_name] = {}
                placed_map[day_name] = {}
                
                for period in self.data.period_ids:
                    placed_map[day_name][period] = 0                    
                    if period in self.data.lunch_break_periods:
                        weekly_schedule[day_name][period] = "LUNCH BREAK"
                    elif period in self.data.break_periods:
                        weekly_schedule[day_name][period] = "BREAK"
                    else:
                        weekly_schedule[day_name][period] = "FREE"

            for entry in faculty_entries:
                if 0 <= entry.time_slot.day < len(self.data.working_days):
                    day_name = self.data.working_days[entry.time_slot.day]
                    period = entry.time_slot.period
                    
                    subject = self.data.subjects.get(entry.subject_id)
                    lab = self.data.labs.get(entry.subject_id)
                    subject_name = (subject.get('name') if subject else
                                  lab.get('name') if lab else entry.subject_id)
                    
                    class_info = {
                        "subject": subject_name,
                        "section": entry.section_id,
                        "room": entry.room_id or 'TBA',
                        "type": entry.entry_type
                    }
                    weekly_schedule[day_name][period] = class_info
                    placed_map[day_name][period] = 1

            faculty_data[faculty_id] = {
                "faculty_id": faculty_id,
                "faculty_name": faculty_info.get('name', faculty_id),
                "department": faculty_info.get('department', ''),
                "designation": faculty_info.get('designation', ''),
                "max_hours_per_week": faculty_info.get('max_hours_per_week', 0),
                "subjects_taught": faculty_info.get('subjects', []),
                "timetable": weekly_schedule,
                "placed": placed_map,
                "periods": {p: self._time_str(p) for p in self.data.period_ids},
                "faculty_experience": faculty_info.get('experience', 0)
            }

        return faculty_data

    def get_detailed_data(self) -> List[Dict]:
        """Detailed data export with OE display"""
        detailed_data = []
        
        for entry in sorted(self.solution.timetable,
                           key=lambda x: (x.section_id, x.time_slot.day, x.time_slot.period)):
            
            faculty = self.data.faculty.get(entry.faculty_id, {})
            faculty_name = faculty.get('name', entry.faculty_id or 'TBA')
            
            # Use the new formatting method
            display_faculty = self._format_faculty_display(entry, faculty_name)
            
            subject = self.data.subjects.get(entry.subject_id)
            lab = self.data.labs.get(entry.subject_id)
            subject_name = (subject.get('name') if subject else
                          lab.get('name') if lab else entry.subject_id)
            
            section = self.data.sections.get(entry.section_id, {})
            room = self.data.rooms.get(entry.room_id, {})
            
            day_name = (self.data.working_days[entry.time_slot.day]
                       if 0 <= entry.time_slot.day < len(self.data.working_days)
                       else str(entry.time_slot.day))

            detailed_data.append({
                "section": entry.section_id,
                "section_name": section.get('name', entry.section_id),
                "subject": subject_name,
                "subject_id": entry.subject_id,
                "faculty": display_faculty,  # Changed: Shows "OE" for electives
                "faculty_id": entry.faculty_id or 'TBA',
                "room": entry.room_id or 'TBA',
                "room_name": room.get('name', ''),
                "day": day_name,
                "day_index": entry.time_slot.day,
                "period": entry.time_slot.period,
                "time": self._time_str(entry.time_slot.period),
                "type": entry.entry_type,
                "batch": entry.batch,
                "lab_session_id": entry.lab_session_id,
                "is_lab_second_period": entry.is_lab_second_period
            })

        return detailed_data

    def export_to_csv(self, filename: str = "timetable_export.csv"):
        detailed_data = self.get_detailed_data()
        df = pd.DataFrame(detailed_data)
        df.to_csv(filename, index=False)
        return filename

    def get_statistics(self) -> Dict:
        """Statistics including elective assignment numbers."""
        unique_classes = len([e for e in self.solution.timetable if not e.is_lab_second_period])
        lab_sessions = len(set(e.lab_session_id for e in self.solution.timetable if e.lab_session_id))

        elective_assigned = set(
            e.subject_id
            for e in self.solution.timetable
            if getattr(e, "is_elective", False)
        )

        elective_available = set(
            sid for sid, s in self.data.subjects.items()
            if s.get("is_elective")
        )

        return {
            "total_classes": unique_classes,
            "total_periods_scheduled": len(self.solution.timetable),
            "lab_sessions": lab_sessions,
            "sections": len(set(e.section_id for e in self.solution.timetable)),
            "subjects": len(set(e.subject_id for e in self.solution.timetable)),
            "faculty": len(set(e.faculty_id for e in self.solution.timetable)),
            "rooms": len(set(e.room_id for e in self.solution.timetable)),
            "fitness_score": self.solution.fitness_score,
            "constraint_violations": self.solution.constraint_violations,

            "electives": {
                "assigned": len(elective_assigned),
                "available": len(elective_available),
                "assigned_list": list(elective_assigned)
            }
        }


def main():
    """Optimized main function"""
    try:
        print("Loading configuration...")
        with open('corrected_timetable_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        print("Initializing data...")
        data = TimetableData(config_dict=config)
        
        # Optimized parameters for fast execution with early stopping
        data.ga_params['population_size'] = 20   # Small population
        data.ga_params['generations'] = 100      # Allow more generations but early stop
        data.ga_params['mutation_rate'] = 0.15
        data.ga_params['crossover_rate'] = 0.85

        print("Creating genetic algorithm...")
        ga = GeneticAlgorithm(data)
        
        print("Initializing population...")
        ga.initialize_population()
        
        print("Starting evolution...")
        ga.evolve()

        best_solution = ga.get_best_solution()
        if not best_solution:
            print("No valid solution found!")
            return None

        exporter = TimetableExporter(best_solution, data)
        stats = exporter.get_statistics()
        
        print(f"Generation complete! Best fitness: {best_solution.fitness_score:.2f}")
        print(f"Total classes scheduled: {stats['total_classes']}")
        print(f"Lab sessions: {stats['lab_sessions']}")
        print(f"Constraint violations: {best_solution.constraint_violations}")

        try:
            from log_ga_run import log_run
            log_run(data, ga, best_solution)
        except Exception as e:
            print(f"Warning: could not log GA run: {e}")

        return best_solution

    except Exception as e:
        print(f"Error: {str(e)}")
        return None

if __name__ == "__main__":
    main()
    # from log_ga_run import log_run
    # log_run(data, ga, best_solution)