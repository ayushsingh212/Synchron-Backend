import json
import copy
import random
import os
from typing import List, Dict, Tuple, Any, Optional, Union
from collections import Counter, defaultdict
from timetable_generator import TimetableData, TimetableChromosome, GeneticAlgorithm, TimetableEntry, TimeSlot, TimetableExporter
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

SUBSTITUTION_LOAD_FILE = "substitution_load.json"

def export_timetable_to_pdf(exporter_data: dict, filename: str):
    styles = getSampleStyleSheet()
    page_width, page_height = landscape(letter)
    left_margin = right_margin = 30
    usable_width = page_width - left_margin - right_margin
    doc = SimpleDocTemplate(
        filename,
        pagesize=landscape(letter),
        leftMargin=left_margin,
        rightMargin=right_margin
    )
    elements = []
    for section_id, sec_data in exporter_data.items():
        section_name = sec_data.get('section_name') or sec_data.get('name', '')
        header_text = f"Section: {section_id}"
        if section_name:
            header_text += f" - {section_name}"
        elements.append(Paragraph(header_text, styles['Heading2']))
        weekly = sec_data.get('timetable') or sec_data.get('weekly') or {}
        if not weekly:
            elements.append(Paragraph("No timetable data available for this section.", styles['Normal']))
            elements.append(Spacer(1, 12))
            continue
        period_keys = set()
        for day_map in weekly.values():
            if isinstance(day_map, dict):
                period_keys.update(day_map.keys())
        try:
            periods = sorted({int(p) for p in period_keys})
        except Exception:
            periods = sorted(list(period_keys), key=lambda x: str(x))
        header = ["Day"] + [f"P{p}" for p in periods]
        table_data = [header]
        for day_name, day_map in weekly.items():
            row = [day_name]
            for p in periods:
                cell = None
                if isinstance(day_map, dict):
                    cell = day_map.get(p) or day_map.get(str(p))
                if isinstance(cell, dict):
                    subj = cell.get('subject') or cell.get('subject_id') or ""
                    fac = cell.get('faculty') or cell.get('faculty_id') or ""
                    room = cell.get('room') or cell.get('room_id') or ""
                    parts = [str(x) for x in (subj, fac, room) if x]
                    cell_text = "\n".join(parts)
                elif cell is None:
                    cell_text = ""
                else:
                    cell_text = str(cell)
                row.append(cell_text)
            table_data.append(row)
        col_width = usable_width / max(1, len(header))
        col_widths = [col_width] * len(header)
        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('GRID', (0,0), (-1,-1), 0.5, colors.black),
            ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTSIZE', (0,0), (-1,-1), 7),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 12))
    doc.build(elements)

def day_name_to_index(data: TimetableData, day_name: str) -> Optional[int]:
    try:
        return data.working_days.index(day_name)
    except ValueError:
        for i, wn in enumerate(data.working_days):
            if wn.lower().startswith(day_name[:3].lower()):
                return i
    return None

def load_json_maybe(path_or_obj):
    if isinstance(path_or_obj, (dict, list)):
        return path_or_obj
    with open(path_or_obj, 'r', encoding='utf-8') as f:
        return json.load(f)

class DynamicUpdater:
    def __init__(self, config_path: str, existing_timetable: Optional[Any] = None):
        self.data = TimetableData(config_file=config_path)
        self.existing_timetable_raw = load_json_maybe(existing_timetable) if existing_timetable else None
        self.seed_chromosome: Optional[TimetableChromosome] = None
        self._current_absent_set: set = set()
        self.substitution_load: Dict[str, int] = self._load_substitution_load()
        
        if self.existing_timetable_raw:
            self.seed_chromosome = self._chromosome_from_exporter_json(self.existing_timetable_raw)
        else:
            ga = GeneticAlgorithm(self.data)
            ga.initialize_population()
            ga.evolve()
            self.seed_chromosome = ga.get_best_solution()
        
        if self.seed_chromosome:
            self._populate_special_periods()

    def _populate_special_periods(self):
        mentorship = set()
        lunch = set()
        for e in self.seed_chromosome.timetable:
            subj = (e.subject_id or "").strip().upper()
            room = (e.room_id or "").strip().upper()
            if "MENTOR" in subj:
                mentorship.add(e.time_slot.period)
            elif "LUNCH" in subj or "LUNCH" in room:
                lunch.add(e.time_slot.period)
        if not hasattr(self.data, "mentorship_periods") or not self.data.mentorship_periods:
            self.data.mentorship_periods = sorted(list(mentorship))
        if not hasattr(self.data, "lunch_break_periods") or not self.data.lunch_break_periods:
            self.data.lunch_break_periods = sorted(list(lunch))

    def _load_substitution_load(self) -> Dict[str, int]:
        if os.path.exists(SUBSTITUTION_LOAD_FILE):
            try:
                with open(SUBSTITUTION_LOAD_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_substitution_load(self):
        with open(SUBSTITUTION_LOAD_FILE, "w", encoding="utf-8") as f:
            json.dump(self.substitution_load, f, indent=2)

    def _chromosome_from_exporter_json(self, exporter_json: Union[Dict, List]) -> TimetableChromosome:
        assignments = []
        
        if isinstance(exporter_json, list):
            for item in exporter_json:
                if isinstance(item, dict):
                    section_id = item.get('section') or item.get('section_id')
                    subject_id = item.get('subject_id') or item.get('subject')
                    faculty_id = item.get('faculty_id') or item.get('faculty')
                    room_id = item.get('room_id') or item.get('room')
                    day = item.get('day')
                    period = item.get('period')
                    
                    if all([section_id, day, period is not None]):
                        assignments.append({
                            'section_id': section_id,
                            'subject_id': subject_id or '',
                            'day': day,
                            'period': period,
                            'faculty_id': faculty_id,
                            'room_id': room_id
                        })
                        
        elif isinstance(exporter_json, dict):
            if 'assignments' in exporter_json:
                assignments = exporter_json['assignments']
            else:
                for section_id, section_data in exporter_json.items():
                    if not isinstance(section_data, dict):
                        continue
                    weekly = section_data.get('timetable') or section_data.get('weekly') or {}
                    for day_name, periods_map in weekly.items():
                        if not isinstance(periods_map, dict):
                            continue
                        for period_key, cell in periods_map.items():
                            try:
                                period = int(period_key)
                            except (ValueError, TypeError):
                                continue
                            faculty_id = room_id = subject_id = None
                            if isinstance(cell, dict):
                                faculty_id = cell.get('faculty_id') or cell.get('faculty')
                                room_id = cell.get('room_id') or cell.get('room')
                                subject_id = cell.get('subject_id') or cell.get('subject')
                            elif isinstance(cell, str) and cell not in ["FREE", "BREAK", "LUNCH BREAK", "MENTORSHIP"]:
                                subject_id = cell
                            if subject_id:
                                assignments.append({
                                    'section_id': section_id,
                                    'subject_id': subject_id,
                                    'day': day_name,
                                    'period': period,
                                    'faculty_id': faculty_id,
                                    'room_id': room_id
                                })
        else:
            chrom = TimetableChromosome(self.data)
            chrom.initialize_random()
            return chrom
        
        chrom = TimetableChromosome(self.data)
        chrom.timetable = []
        chrom._occupied_slots = set()
        
        for a in assignments:
            try:
                day_index = day_name_to_index(self.data, a['day'])
                if day_index is None:
                    continue
                period = int(a['period'])
                ts = TimeSlot(day=day_index, period=period)
                entry = TimetableEntry(
                    section_id=a['section_id'],
                    subject_id=a.get('subject_id', ''),
                    faculty_id=a.get('faculty_id'),
                    room_id=a.get('room_id'),
                    time_slot=ts
                )
                chrom.timetable.append(entry)
                chrom._add_to_occupied(entry)
            except Exception:
                continue
        
        chrom.calculate_fitness()
        return chrom

    def _deterministic_shift_if_possible(
        self,
        affected_entries: List[TimetableEntry],
        forbidden_periods: Optional[set] = None
    ) -> List[Dict[str, Any]]:
        if not affected_entries:
            return []
        base = self.seed_chromosome
        shifted_info: List[Dict[str, Any]] = []
        max_period = max((e.time_slot.period for e in base.timetable), default=8)
        occupied = {(e.faculty_id, e.time_slot.day, e.time_slot.period): e
                   for e in base.timetable if e.faculty_id and (e.subject_id or "").strip().upper() != "FREE"}
        section_occupied = {(e.section_id, e.time_slot.day, e.time_slot.period): e
                           for e in base.timetable if (e.subject_id or "").strip().upper() != "FREE"}
        room_occupied = {(e.room_id, e.time_slot.day, e.time_slot.period): e
                        for e in base.timetable if e.room_id and (e.subject_id or "").strip().upper() != "FREE"}
        forbidden_periods = set(forbidden_periods or set())
        
        for entry in affected_entries:
            fac, sec, room = entry.faculty_id, entry.section_id, entry.room_id
            day, period = entry.time_slot.day, entry.time_slot.period
            free_slots = []
            for p in range(1, max_period + 1):
                if p in forbidden_periods:
                    continue
                if ((fac, day, p) not in occupied and
                    (sec, day, p) not in section_occupied and
                    (room, day, p) not in room_occupied):
                    free_slots.append(p)
            if not free_slots:
                continue
            for p in sorted(free_slots):
                if ((fac, day, p) not in occupied and
                    (sec, day, p) not in section_occupied and
                    (room, day, p) not in room_occupied):
                    orig = period
                    entry.time_slot = TimeSlot(day=day, period=p)
                    shifted_info.append({'entry': entry, 'orig_period': orig})
                    occupied[(fac, day, p)] = entry
                    section_occupied[(sec, day, p)] = entry
                    if room:
                        room_occupied[(room, day, p)] = entry
                    break
        return shifted_info

    def _compute_affected_entries(self, events: List[Dict]) -> List[TimetableEntry]:
        affected = []
        for ev in events:
            t = ev.get('type')
            if t == 'faculty_absence':
                fid, start, end = ev['faculty_id'], ev['start_day'], ev.get('end_day', ev['start_day'])
                timeslots = ev.get('timeslots')
                sidx, eidx = day_name_to_index(self.data, start), day_name_to_index(self.data, end)
                if sidx is None or eidx is None: continue
                for entry in self.seed_chromosome.timetable:
                    if entry.faculty_id == fid and sidx <= entry.time_slot.day <= eidx:
                        if timeslots is None or entry.time_slot.period in timeslots:
                            affected.append(entry)
            elif t == 'faculty_partial_absence':
                fid = ev['faculty_id']
                date = ev.get('date') or ev.get('start_day')
                timeslots = ev.get('timeslots')
                day_idx = day_name_to_index(self.data, date)
                if day_idx is None:
                    continue
                for entry in self.seed_chromosome.timetable:
                    if entry.faculty_id == fid and entry.time_slot.day == day_idx:
                        if timeslots is None or entry.time_slot.period in timeslots:
                            affected.append(entry)
            elif t == 'resource_unavailable':
                rid, start, end = ev['room_id'], ev['start_day'], ev.get('end_day', ev['start_day'])
                timeslots = ev.get('timeslots')
                sidx, eidx = day_name_to_index(self.data, start), day_name_to_index(self.data, end)
                if sidx is None or eidx is None: continue
                for entry in self.seed_chromosome.timetable:
                    if entry.room_id == rid and sidx <= entry.time_slot.day <= eidx:
                        if timeslots is None or entry.time_slot.period in timeslots:
                            affected.append(entry)
        return list({id(x): x for x in affected}.values())

    def _build_candidate_pools(self, affected: List[Any], base_chromosome: Optional[TimetableChromosome] = None) -> Dict[int, Dict]:
        base = base_chromosome or self.seed_chromosome
        pools = {}
        id_to_index = {id(e): i for i, e in enumerate(base.timetable)}
        absent_ids = self._current_absent_set
        for entry in affected:
            idx = id_to_index[id(entry)]
            day, period, subject = entry.time_slot.day, entry.time_slot.period, entry.subject_id
            qualified = [fid for fid, subs in self.data.faculty_subjects.items() if subject in subs]
            qualified.sort(key=lambda fid: self.substitution_load.get(fid, 0))
            free_qualified = [
                fid for fid in qualified
                if fid not in absent_ids and all(
                    not (o.faculty_id == fid and o.time_slot.day == day and o.time_slot.period == period)
                    for o in base.timetable
                    if o is not entry and (not o.faculty_id or o.faculty_id not in absent_ids)
                )
            ]
            if not free_qualified:
                free_qualified = [fid for fid in qualified if fid not in absent_ids]
            sec = self.data.sections.get(entry.section_id, {})
            required_capacity = sec.get('student_count', 0)
            room_pool = []
            for rid, rinfo in self.data.rooms.items():
                if rinfo.get('capacity', 0) < required_capacity:
                    continue
                if any(
                    o.room_id == rid and o.time_slot.day == day and o.time_slot.period == period
                    for o in base.timetable if o is not entry
                ):
                    continue
                room_pool.append(rid)
            if entry.room_id and entry.room_id not in room_pool:
                room_pool.append(entry.room_id)
            pools[idx] = {'faculties': free_qualified, 'rooms': room_pool}
        return pools

    def _generate_seed_population(self, pools: Dict[int, Dict], base_chromosome: Optional[TimetableChromosome] = None, pop_size: int = 40) -> List[TimetableChromosome]:
        base = base_chromosome or self.seed_chromosome
        population = []
        affected_indices = list(pools.keys())
        
        def make_variant():
            c = TimetableChromosome(self.data)
            c.timetable = [copy.deepcopy(e) for e in base.timetable]
            for idx in affected_indices:
                entry = c.timetable[idx]
                pool = pools[idx]
                if pool['faculties']:
                    chosen_faculty = random.choice(pool['faculties'])
                    entry.faculty_id = chosen_faculty
                if pool['rooms']:
                    chosen_room = random.choice(pool['rooms'])
                    entry.room_id = chosen_room
            c._occupied_slots = set()
            for e in c.timetable:
                if e.faculty_id:
                    c._occupied_slots.add((e.faculty_id, e.time_slot.day, e.time_slot.period))
                if e.room_id:
                    c._occupied_slots.add((e.room_id, e.time_slot.day, e.time_slot.period))
                c._occupied_slots.add((e.section_id, e.time_slot.day, e.time_slot.period))
            c.calculate_fitness()
            return c
        
        while len(population) < pop_size:
            population.append(make_variant())
        return population

    def apply_events(self, dynamic_events: Any, ga_params: Optional[Dict] = None) -> Dict:
        payload = load_json_maybe(dynamic_events)
        events = payload.get('events', []) if isinstance(payload, dict) else []
        self.data.ga_params.update(ga_params or {})
        
        if not self.seed_chromosome:
            raise RuntimeError("No seed timetable available.")
        
        faculty_prefs = {}
        for ev in events:
            if ev.get('type', '').startswith('faculty'):
                fid = ev.get('faculty_id')
                if fid:
                    faculty_prefs[fid] = ev.get('preferences', {})
        
        affected_entries_original = self._compute_affected_entries(events)
        if not affected_entries_original:
            exporter = TimetableExporter(self.seed_chromosome, self.data)
            return {
                "sections": exporter.get_section_wise_data(),
                "faculty": exporter.get_faculty_wise_data(),
                "detailed": exporter.get_detailed_data(),
                "fitness": self.seed_chromosome.fitness_score
            }
        
        shifted_info_all: List[Dict[str, Any]] = []
        global_forbidden = set()
        if hasattr(self.data, "mentorship_periods"):
            try:
                global_forbidden.update(set(self.data.mentorship_periods))
            except Exception:
                pass
        if hasattr(self.data, "lunch_break_periods"):
            try:
                global_forbidden.update(set(self.data.lunch_break_periods))
            except Exception:
                pass
        
        for ev in events:
            ev_type = ev.get("type", "")
            if ev_type == "faculty_partial_absence" and ev.get("preferences", {}).get("prefer_shift", False):
                fid = ev.get("faculty_id")
                date = ev.get("date") or ev.get("start_day")
                if date is None:
                    continue
                day_idx = day_name_to_index(self.data, date)
                if day_idx is None:
                    continue
                timeslots = ev.get("timeslots") or []
                if not timeslots:
                    continue
                candidates = [e for e in self.seed_chromosome.timetable if e.faculty_id == fid and e.time_slot.day == day_idx and e.time_slot.period in timeslots]
                event_forbidden = set(global_forbidden)
                prefs = ev.get("preferences", {})
                if isinstance(prefs.get("forbidden_periods"), (list, tuple, set)):
                    event_forbidden.update(set(prefs.get("forbidden_periods")))
                if isinstance(prefs.get("avoid_periods"), (list, tuple, set)):
                    event_forbidden.update(set(prefs.get("avoid_periods")))
                shifted_info = self._deterministic_shift_if_possible(candidates, forbidden_periods=event_forbidden)
                shifted_info_all.extend(shifted_info)
        
        shifted_entries_objs = [info['entry'] for info in shifted_info_all]
        affected_entries_original = [e for e in affected_entries_original if e not in shifted_entries_objs]
        
        absent_ids = {ev['faculty_id'] for ev in events if ev['type'].startswith('faculty')}
        self._current_absent_set = absent_ids
        
        slots_to_clear: Dict[Tuple[str, int, int], Dict[str, bool]] = {}
        for ev in events:
            etype = ev['type']
            if etype.startswith('faculty'):
                fid, sidx, eidx = ev['faculty_id'], day_name_to_index(self.data, ev['start_day'] if 'start_day' in ev else ev.get('date')), day_name_to_index(self.data, ev.get('end_day', ev.get('date')))
                timeslots = ev.get('timeslots')
                for orig in self.seed_chromosome.timetable:
                    if orig.faculty_id == fid and sidx <= orig.time_slot.day <= eidx:
                        if timeslots is None or orig.time_slot.period in timeslots:
                            slots_to_clear.setdefault((orig.section_id, orig.time_slot.day, orig.time_slot.period), {})['clear_faculty'] = True
            elif etype == 'resource_unavailable':
                rid, sidx, eidx, timeslots = ev['room_id'], day_name_to_index(self.data, ev['start_day']), day_name_to_index(self.data, ev.get('end_day', ev['start_day'])), ev.get('timeslots')
                for orig in self.seed_chromosome.timetable:
                    if orig.room_id == rid and sidx <= orig.time_slot.day <= eidx:
                        if timeslots is None or orig.time_slot.period in timeslots:
                            slots_to_clear.setdefault((orig.section_id, orig.time_slot.day, orig.time_slot.period), {})['clear_room'] = True
        
        modified_seed = copy.deepcopy(self.seed_chromosome)
        for e in modified_seed.timetable:
            key = (e.section_id, e.time_slot.day, e.time_slot.period)
            if key in slots_to_clear:
                flags = slots_to_clear[key]
                if flags.get('clear_faculty'):
                    e.faculty_id = None
                if flags.get('clear_room'):
                    e.room_id = None
        
        modified_map = {(e.section_id, e.time_slot.day, e.time_slot.period): e for e in modified_seed.timetable}
        affected_entries = [modified_map[(orig.section_id, orig.time_slot.day, orig.time_slot.period)] for orig in affected_entries_original if (orig.section_id, orig.time_slot.day, orig.time_slot.period) in modified_map]
        
        report = {"substitutions": [], "unassigned": [], "shifted": []}
        for info in shifted_info_all:
            e = info['entry']
            report["shifted"].append({
                "section": e.section_id,
                "day": e.time_slot.day,
                "orig_period": info.get('orig_period'),
                "new_period": e.time_slot.period,
                "note": "deterministically shifted from original slot (user requested)"
            })
        
        original_backup = self.seed_chromosome
        try:
            self.seed_chromosome = modified_seed
            pools = self._build_candidate_pools(affected_entries, base_chromosome=modified_seed)
            seed_population = self._generate_seed_population(pools, base_chromosome=modified_seed)
            ga = GeneticAlgorithm(self.data)
            ga.population = seed_population
            ga.evolve()
            best = ga.get_best_solution()
            
            for absent_fid, pref in faculty_prefs.items():
                if pref.get('mode') != 'same_substitute_per_section':
                    continue
                section_to_indices = defaultdict(list)
                for orig in affected_entries_original:
                    if orig.faculty_id != absent_fid:
                        continue
                    k = (orig.section_id, orig.time_slot.day, orig.time_slot.period)
                    if k not in modified_map:
                        continue
                    try:
                        index = next(i for i, e in enumerate(modified_seed.timetable) if e.section_id == orig.section_id and e.time_slot.day == orig.time_slot.day and e.time_slot.period == orig.time_slot.period)
                    except StopIteration:
                        continue
                    if index in pools:
                        section_to_indices[orig.section_id].append(index)
                        
                for sec_id, idx_list in section_to_indices.items():
                    if not idx_list:
                        continue
                    candidate_sets = [set(pools[idx]['faculties']) for idx in idx_list]
                    if not candidate_sets:
                        continue
                    common = set.intersection(*candidate_sets)
                    common = {f for f in common if f not in absent_ids}
                    if not common:
                        continue
                    total_load_base = Counter()
                    for e in modified_seed.timetable:
                        if e.faculty_id:
                            total_load_base[e.faculty_id] += 1
                    chosen = min(common, key=lambda f: (total_load_base.get(f, 0), f))
                    for idx in idx_list:
                        me = best.timetable[idx]
                        conflict = False
                        for o in best.timetable:
                            if o is me:
                                continue
                            if o.faculty_id == chosen and o.time_slot.day == me.time_slot.day and o.time_slot.period == me.time_slot.period:
                                if (o.section_id, o.time_slot.day, o.time_slot.period) not in modified_map:
                                    conflict = True
                                    break
                                else:
                                    cidx = None
                                    for i, e in enumerate(modified_seed.timetable):
                                        if e.section_id == o.section_id and e.time_slot.day == o.time_slot.day and e.time_slot.period == o.time_slot.period:
                                            cidx = i
                                            break
                                    if cidx is None or cidx not in pools:
                                        conflict = True
                                        break
                        if conflict:
                            continue
                        me.faculty_id = chosen
            
            for idx in pools.keys():
                target = modified_seed.timetable[idx]
                chosen_entry = next(
                    (e for e in best.timetable
                     if e.section_id == target.section_id and e.time_slot.day == target.time_slot.day and e.time_slot.period == target.time_slot.period),
                    None
                )
                if chosen_entry and chosen_entry.faculty_id:
                    report["substitutions"].append({
                        "section": chosen_entry.section_id,
                        "day": chosen_entry.time_slot.day,
                        "period": chosen_entry.time_slot.period,
                        "faculty": chosen_entry.faculty_id
                    })
                else:
                    report["unassigned"].append({
                        "section": target.section_id,
                        "day": target.time_slot.day,
                        "period": target.time_slot.period
                    })
            
            for s in report["substitutions"]:
                fid = s.get("faculty")
                if not fid:
                    continue
                self.substitution_load[fid] = self.substitution_load.get(fid, 0) + 1
            
            self._save_substitution_load()
        finally:
            self.seed_chromosome = original_backup
        
        best.calculate_fitness()
        exporter = TimetableExporter(best, self.data)
        self._current_absent_set = set()
        
        try:
            with open("substitution_report.json", "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except Exception:
            pass
        
        return {
            "sections": exporter.get_section_wise_data(),
            "faculty": exporter.get_faculty_wise_data(),
            "detailed": exporter.get_detailed_data(),
            "fitness": best.fitness_score
        }

if __name__ == "__main__":
    import argparse, sys
    parser = argparse.ArgumentParser(description="Dynamic Timetable Updater")
    parser.add_argument("--config", required=True, help="Path to config JSON (used by GA)")
    parser.add_argument("--existing", required=False, help="Path to existing timetable JSON (exporter format)")
    parser.add_argument("--events", required=True, help="Path to events JSON describing changes")
    parser.add_argument("--output", default="updated_timetable.json", help="Where to save updated timetable JSON")
    parser.add_argument("--pdf-before", default="timetable_before_update_section.pdf", help="PDF before update")
    parser.add_argument("--pdf-after", default="timetable_after_update_section.pdf", help="PDF after update")
    args = parser.parse_args()
    try:
        updater = DynamicUpdater(config_path=args.config, existing_timetable=args.existing)
        if updater.seed_chromosome:
            exporter_before = TimetableExporter(updater.seed_chromosome, updater.data)
            export_timetable_to_pdf(exporter_before.get_section_wise_data(), args.pdf_before)
            if isinstance(args.pdf_before, str) and args.pdf_before.lower().endswith('.pdf'):
                faculty_pdf_before = args.pdf_before[:-4] + "_faculty.pdf"
            else:
                faculty_pdf_before = str(args.pdf_before) + "_faculty.pdf"
            try:
                export_timetable_to_pdf(exporter_before.get_faculty_wise_data(), faculty_pdf_before)
            except Exception:
                pass
        with open(args.events, "r", encoding="utf-8") as f:
            events_payload = json.load(f)
        out = updater.apply_events(events_payload)
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        export_timetable_to_pdf(out['sections'], args.pdf_after)
        if isinstance(args.pdf_after, str) and args.pdf_after.lower().endswith('.pdf'):
            faculty_pdf_after = args.pdf_after[:-4] + "_faculty.pdf"
        else:
            faculty_pdf_after = str(args.pdf_after) + "_faculty.pdf"
        try:
            export_timetable_to_pdf(out['faculty'], faculty_pdf_after)
        except Exception:
            pass
    except Exception as e:
        sys.exit(1)