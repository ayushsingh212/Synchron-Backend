from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Union, Literal

# --- Event Models ---

class EventPreferences(BaseModel):
    mode: Optional[Literal["same_substitute_per_section", "distribute_substitute_load", "cancel_if_no_substitute", "merge_with_parallel_batches", "reschedule_to_next_day"]] = None
    prefer_shift: Optional[bool] = None

class BaseEvent(BaseModel):
    type: str
    note: Optional[str] = None
    reason: Optional[str] = None

class FacultyAbsenceEvent(BaseEvent):
    type: Literal["faculty_absence", "faculty_partial_absence"]
    faculty_id: str
    start_day: Optional[str] = None
    end_day: Optional[str] = None
    date: Optional[str] = None
    timeslots: Optional[List[int]] = None
    preferences: Optional[EventPreferences] = None

class ResourceUnavailableEvent(BaseEvent):
    type: Literal["resource_unavailable", "room_maintenance"]
    room_id: str
    start_day: Optional[str] = None
    end_day: Optional[str] = None
    timeslots: Optional[List[int]] = None

class SectionUnavailableEvent(BaseEvent):
    """New: For events like field trips or exams where a section cannot have classes"""
    type: Literal["section_unavailable"]
    section_id: str
    start_day: str
    end_day: str
    timeslots: Optional[List[int]] = None  # None implies full day

class ForceAssignmentEvent(BaseEvent):
    """New: Force a specific faculty/subject to a specific slot (Locking)"""
    type: Literal["force_assignment"]
    faculty_id: str
    subject_id: str
    section_id: str
    day: str
    timeslot: int=1
    room_id: Optional[str] = None

# --- Constraint Models ---

class SoftConstraints(BaseModel):
    balanced_daily_load: Optional[Dict[str, Union[float, int]]] = Field(None, description="Weight and max deviation")
    faculty_preference_slots: Optional[Dict[str, float]] = Field(None, description="Weight for adhering to faculty preferences")
    minimize_faculty_travel: Optional[Dict[str, float]] = Field(None, description="Weight for minimizing room changes")
    morning_heavy_subjects: Optional[Dict[str, Union[float, List[str]]]] = Field(None, description="Weight and list of heavy subjects")
    avoid_single_period_gaps: Optional[Dict[str, float]] = Field(None, description="Weight for avoiding 1-hour gaps")
    distribute_subjects_evenly: Optional[Dict[str, float]] = None

class HardConstraints(BaseModel):
    no_faculty_clash: bool = True
    no_room_clash: bool = True
    no_section_clash: bool = True
    max_classes_per_day_per_section: int = None
    break_periods_fixed: List[int] = None
    lab_duration_consecutive: bool = True

class NLPResponse(BaseModel):
    intent: Literal["update_constraints", "add_events", "mixed"]
    constraints: Optional[Dict[str, Union[HardConstraints, SoftConstraints]]] = None
    events: Optional[List[Union[FacultyAbsenceEvent, ResourceUnavailableEvent, SectionUnavailableEvent, ForceAssignmentEvent]]] = None

    @field_validator('events')
    def validate_events(cls, v):
        return v if v is not None else []