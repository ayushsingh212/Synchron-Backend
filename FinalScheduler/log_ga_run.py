"""
log_ga_run.py

Place this file next to timetablegenerator.py.

Usage:
    In timetablegenerator.py, after you compute `best_solution` (the TimetableChromosome)
    and `ga` (GeneticAlgorithm) and `data` (TimetableData), call:

    from log_ga_run import log_run
    log_run(data, ga, best_solution)

This will append a row to `ga_runs.csv` and write a JSON copy under `ga_runs_json/`.
"""

import os
import csv
import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

import numpy as np

OUT_CSV = "ga_runs.csv"
OUT_JSON_DIR = "ga_runs_json"
Path(OUT_JSON_DIR).mkdir(exist_ok=True)


def _safe_get(d: dict, k, default=0):
    return d.get(k, default) if isinstance(d, dict) else default


def _mean_or_zero(lst):
    try:
        import numpy as _np
        return float(_np.mean(lst)) if lst else 0.0
    except Exception:
        return float(sum(lst) / len(lst)) if lst else 0.0


def _sum_violation_dict(vdict):
    if not vdict:
        return 0
    return int(sum(int(v) for v in vdict.values()))


def _collect_room_capacity(data):
    caps = []
    for rid, r in getattr(data, "rooms", {}).items():
        try:
            caps.append(float(r.get("capacity", 0)))
        except Exception:
            try:
                caps.append(float(r.get("cap", 0)))
            except Exception:
                caps.append(0.0)
    return caps


def _collect_lab_room_capacities(data):
    # prefer explicit lab_rooms referenced in labs; fallback to rooms of type 'lab'
    caps = []
    labs = getattr(data, "labs", {}) or {}
    rooms = getattr(data, "rooms", {}) or {}
    # lab_rooms listed per lab
    for lab in labs.values():
        lab_rooms = lab.get("lab_rooms") or []
        for rid in lab_rooms:
            r = rooms.get(rid)
            if r:
                try:
                    caps.append(float(r.get("capacity", 0)))
                except Exception:
                    caps.append(0.0)
    # fallback: rooms with type lab
    if not caps:
        for rid, r in rooms.items():
            if str(r.get("type", "")).lower() in ("lab", "laboratory"):
                try:
                    caps.append(float(r.get("capacity", 0)))
                except Exception:
                    caps.append(0.0)
    return caps


def _estimate_required_periods(data):
    # Uses TimetableChromosome._get_required_classes logic equivalent:
    total = 0
    for section_id, section in getattr(data, "sections", {}).items():
        # count theory subjects & labs that apply (best-effort)
        # We will look into subjects and labs; if no restrictions, assume 1 lecture per subject
        # Use subject.get('lectures_per_week',1) or lab.get('sessions_per_week',2)
        for subj in (getattr(data, "subjects", {}) or {}).values():
            # best-effort: check departments mapping if exists
            applies = True
            sub_depts = subj.get("departments", [])
            if sub_depts:
                sec_dept = getattr(data, "section_department", {}).get(section_id)
                if sec_dept and sec_dept not in sub_depts:
                    applies = False
            if applies:
                try:
                    classes = int(subj.get("min_classes_per_week", subj.get("lectures_per_week", 1)))
                except Exception:
                    classes = 1
                total += max(1, classes)
        for lab in (getattr(data, "labs", {}) or {}).values():
            applies = True
            lab_depts = lab.get("departments", [])
            if lab_depts:
                sec_dept = getattr(data, "section_department", {}).get(section_id)
                if sec_dept and sec_dept not in lab_depts:
                    applies = False
            if applies:
                try:
                    sessions = int(lab.get("min_classes_per_week", lab.get("sessions_per_week", 2)))
                except Exception:
                    sessions = 2
                total += max(0, sessions)
    return int(total)


def _population_constraint_stats(population):
    # population: list of TimetableChromosome
    if not population:
        return 0.0, 0.0
    fitnesses = []
    violation_sums = []
    for ch in population:
        try:
            fitnesses.append(float(getattr(ch, "fitness_score", 0.0)))
        except Exception:
            fitnesses.append(0.0)
        try:
            v = getattr(ch, "constraint_violations", {}) or {}
            violation_sums.append(sum(int(x) for x in v.values()) if isinstance(v, dict) else 0)
        except Exception:
            violation_sums.append(0)
    # diversity = stddev of fitness
    try:
        diversity = float(np.std(fitnesses)) if fitnesses else 0.0
    except Exception:
        diversity = 0.0
    avg_viol = float(np.mean(violation_sums)) if violation_sums else 0.0
    return float(diversity), float(avg_viol)


def log_run(data, ga, best_solution, out_csv: str = OUT_CSV):
    """
    Extract features from objects and append to CSV + JSON.
    - data: TimetableData instance
    - ga: GeneticAlgorithm instance
    - best_solution: TimetableChromosome instance (the chosen/best solution)
    """
    try:
        # Basic ids & timestamp
        run_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat() + "Z"

        # ---- INPUT FEATURES ----
        sections = getattr(data, "sections", {}) or {}
        subjects = getattr(data, "subjects", {}) or {}
        faculty = getattr(data, "faculty", {}) or {}
        rooms = getattr(data, "rooms", {}) or {}
        labs = getattr(data, "labs", {}) or {}

        num_sections = len(sections)
        num_subjects = len(subjects)
        num_faculty = len(faculty)
        num_rooms = len(rooms)
        num_labs = len(labs)
        num_working_days = int(getattr(data, "num_working_days", 5) or 5)
        num_periods_per_day = len(getattr(data, "period_ids", []) or [])

        # avg section size (student_count fallback)
        section_sizes = [float(s.get("student_count", s.get("size", 60))) for s in sections.values()] if sections else []
        avg_section_size = _mean_or_zero(section_sizes)

        # subjects per section & classes required
        # We derive from required_classes_map if present (TimetableChromosome sets this in __init__)
        # fallback: mean of subject lists if present
        required_map = None
        try:
            required_map = getattr(best_solution, "required_classes_map", None)
            if not required_map:
                # attempt to access from a fresh chromosome instance if possible
                # fallback to data-derived approx
                required_map = {}
                for sec_id in sections.keys():
                    # count subjects that apply (best-effort)
                    count = 0
                    for subj in subjects.values():
                        applies = True
                        sub_depts = subj.get("departments", [])
                        if sub_depts:
                            sec_dept = getattr(data, "section_department", {}).get(sec_id)
                            if sec_dept and sec_dept not in sub_depts:
                                applies = False
                        if applies:
                            count += 1
                    required_map[sec_id] = [{"subject_id": s} for s in range(count)]
        except Exception:
            required_map = required_map or {}

        per_section_required_counts = [len(required_map.get(sid, [])) for sid in sections.keys()] if sections else []
        avg_classes_required_per_section = float(_mean_or_zero(per_section_required_counts))
        avg_subjects_per_section = float(_mean_or_zero([len(set([c.get("subject_id") for c in required_map.get(sid,[])])) for sid in required_map.keys()])) if required_map else 0.0

        # faculty load features
        faculty_max_hours = [float(f.get("max_hours_per_week", 0)) for f in faculty.values()] if faculty else []
        avg_faculty_max_hours = _mean_or_zero(faculty_max_hours)
        subjects_taught_counts = [len(f.get("subjects", [])) for f in faculty.values()] if faculty else []
        avg_subjects_taught_per_faculty = _mean_or_zero(subjects_taught_counts)

        # rooms
        room_caps = _collect_room_capacity(data)
        avg_room_capacity = _mean_or_zero(room_caps)
        num_large_rooms = int(sum(1 for c in room_caps if c >= 60))

        # labs
        total_lab_subjects = len(labs)
        lab_caps = _collect_lab_room_capacities(data)
        avg_lab_capacity = _mean_or_zero(lab_caps)

        # constraints booleans / indicators
        has_lab_pairing = any(int(l.get("requires_consecutive_periods", 0)) > 1 for l in labs.values()) if labs else False
        enforce_room_capacity = True
        enforce_faculty_clash = True
        enforce_section_clash = True

        # GA hyperparams (from data.ga_params or ga attributes)
        ga_params = getattr(data, "ga_params", {}) or {}
        population_size = int(ga_params.get("population_size", getattr(ga, "population", []) and len(getattr(ga, "population", [])) or 30))
        generations = int(ga_params.get("generations", 100))
        mutation_rate = float(ga_params.get("mutation_rate", 0.15))
        crossover_rate = float(ga_params.get("crossover_rate", 0.85))
        elitism_rate = float(ga_params.get("elitism_rate", ga_params.get("elite_size", 0)) or 0.0)

        # estimated total required periods
        estimated_total_required_periods = _estimate_required_periods(data)

        # population-derived stats
        pop = getattr(ga, "population", []) or []
        initial_population_diversity, avg_constraint_violations_population = _population_constraint_stats(pop)

        # ---- OUTPUT TARGETS ----
        final_fitness = float(getattr(best_solution, "fitness_score", getattr(best_solution, "final_fitness", 0.0))) if best_solution else 0.0
        constraint_violations = getattr(best_solution, "constraint_violations", {}) if best_solution else {}
        total_classes = int(len([e for e in getattr(best_solution, "timetable", []) if not getattr(e, "is_lab_second_period", False)])) if best_solution else 0
        lab_sessions = int(len(set([getattr(e, "lab_session_id", "") for e in getattr(best_solution, "timetable", []) if getattr(e, "lab_session_id", "")]))) if best_solution else 0

        # runtime and convergence info from generation_progress if available
        # generation_progress in timetablegenerator.py is module-level; try to import it
        runtime_seconds = None
        convergence_generation = None
        try:
            # Many users will call log_run from timetablegenerator.py so generation_progress is in module scope
            import timetablegenerator as ttg
            gp = getattr(ttg, "generation_progress", None)
            if gp:
                # compute elapsed if start and end present
                start = getattr(gp, "start_time", None)
                end = getattr(gp, "end_time", None)
                if start and end:
                    runtime_seconds = (end - start).total_seconds()
                elif start and not end:
                    runtime_seconds = (datetime.utcnow() - start).total_seconds()
                convergence_generation = int(getattr(gp, "current_generation", 0))
        except Exception:
            runtime_seconds = None
            convergence_generation = None

        # If runtime still None, try ga timed members (not present by default)
        if runtime_seconds is None:
            runtime_seconds = float(getattr(ga, "runtime_seconds", 0.0) or 0.0)

        # compose the row (schema as agreed)
        row: Dict[str, Any] = {
            "run_id": run_id,
            "timestamp": timestamp,
            # size features
            "num_sections": int(num_sections),
            "num_subjects": int(num_subjects),
            "num_faculty": int(num_faculty),
            "num_rooms": int(num_rooms),
            "num_labs": int(num_labs),
            "num_working_days": int(num_working_days),
            "num_periods_per_day": int(num_periods_per_day),
            # curriculum
            "avg_section_size": float(avg_section_size),
            "avg_subjects_per_section": float(avg_subjects_per_section),
            "avg_classes_required_per_section": float(avg_classes_required_per_section),
            # faculty
            "avg_faculty_max_hours": float(avg_faculty_max_hours),
            "avg_subjects_taught_per_faculty": float(avg_subjects_taught_per_faculty),
            # rooms & labs
            "avg_room_capacity": float(avg_room_capacity),
            "num_large_rooms": int(num_large_rooms),
            "total_lab_subjects": int(total_lab_subjects),
            "avg_lab_capacity": float(avg_lab_capacity),
            # GA hyperparams
            "population_size": int(population_size),
            "generations": int(generations),
            "mutation_rate": float(mutation_rate),
            "crossover_rate": float(crossover_rate),
            "elitism_rate": float(elitism_rate),
            # extra difficulty/diversity signals
            "initial_population_diversity": float(initial_population_diversity),
            "estimated_total_required_periods": int(estimated_total_required_periods),
            "avg_constraint_violations_population": float(avg_constraint_violations_population),
            # binary indicators
            "has_lab_pairing": int(bool(has_lab_pairing)),
            "enforce_room_capacity": int(bool(enforce_room_capacity)),
            "enforce_faculty_clash": int(bool(enforce_faculty_clash)),
            "enforce_section_clash": int(bool(enforce_section_clash)),
            # outputs/targets
            "final_fitness": float(final_fitness),
            "constraint_violations_total": int(_sum_violation_dict(constraint_violations)),
            "constraint_violations_detail": json.dumps(constraint_violations),
            "lab_sessions": int(lab_sessions),
            "total_classes": int(total_classes),
            "runtime_seconds": float(runtime_seconds or 0.0),
            "convergence_generation": int(convergence_generation or 0)
        }

        # Write CSV (append header if first time)
        file_exists = os.path.isfile(out_csv)
        with open(out_csv, "a", newline="", encoding="utf-8") as cf:
            writer = csv.DictWriter(cf, fieldnames=list(row.keys()))
            if not file_exists:
                writer.writeheader()
            writer.writerow(row)

        # Write JSON copy
        json_path = os.path.join(OUT_JSON_DIR, f"run_{run_id}.json")
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(row, jf, indent=2, default=str)

        print(f"[LOG] GA run logged to {out_csv} and {json_path}")

        return row

    except Exception as e:
        print(f"[LOG ERROR] Failed to log GA run: {e}")
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        return None
