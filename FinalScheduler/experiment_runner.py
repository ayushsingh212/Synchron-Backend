#!/usr/bin/env python3
"""
experiment_runner.py

Place this file in the same directory as:
 - timetablegenerator.py
 - log_ga_run.py
 - corrected_timetable_config.json (the base config your main() uses)

Usage:
    python experiment_runner.py --num_runs 200 --start_index 0

What it does:
 - Loads the base JSON config file.
 - For each sample, makes a shallow copy and randomly perturbs a few things:
     * duplicates rooms/faculty/sections to increase counts
     * tweaks section student_count
     * toggles/adjusts a few constraint and GA hyperparameters
 - Creates TimetableData from the sampled config, runs the genetic algorithm
   (initialize_population() + evolve()), and logs the run via log_run().
 - Appends each run to ga_runs.csv and writes a JSON snapshot to ga_runs_json/
"""

import argparse
import json
import random
import time
import copy
import os
from pathlib import Path
from typing import Dict, Any

# make sure current dir is in sys.path
import sys
sys.path.insert(0, os.getcwd())

# imports from your codebase
try:
    import timetable_generator as ttg  # contains TimetableData, GeneticAlgorithm, etc.
    from log_ga_run import log_run
except Exception as e:
    print("Error importing project modules. Make sure this file sits next to timetablegenerator.py and log_ga_run.py")
    raise

SEED = 42
random.seed(SEED)

# Sampling ranges (tweak these as needed)
ROOM_DUPLICATE_RANGE = (0, 5)        # how many extra rooms to add (duplicate existing)
FACULTY_DUPLICATE_RANGE = (0, 5)     # extra faculty
SECTION_DUPLICATE_RANGE = (0, 5)     # extra sections
SECTION_SIZE_JITTER = (-10, 20)      # change section sizes by this amount (additive)
POP_SIZE_CHOICES = [10, 20, 30, 50, 80]  # population sizes to sample
GENS_CHOICES = [30, 50, 80, 100]     # generations
MUTATION_CHOICES = [0.01, 0.05, 0.1, 0.15, 0.2]
CROSSOVER_CHOICES = [0.6, 0.7, 0.8, 0.85, 0.9]
ELITE_SIZE_CHOICES = [0, 1, 2, 3]

# Keep safe limits to ensure runs complete quickly
MAX_TOTAL_ENTRIES = 200  # do not create monstrous configs automatically

# Where base config is expected
BASE_CONFIG_FILE = "corrected_timetable_config.json"


def safe_load_base_config(path: str) -> Dict[str, Any]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Base config file not found at {path}")
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _duplicate_items(container: Dict[str, Dict], how_many: int, id_prefix: str):
    """
    Duplicate random existing entries in container (a mapping id->obj).
    New ids will be created by appending a counter suffix.
    Returns nothing; modifies container in-place.
    """
    if how_many <= 0 or not container:
        return
    keys = list(container.keys())
    max_existing = len(keys)
    # don't exceed some safe upper bound
    for i in range(how_many):
        src = container[random.randrange(0, max_existing)]
        new_id = f"{id_prefix}_dup_{int(time.time()*1000) % 100000}_{i}"
        new_obj = copy.deepcopy(container[src])
        # try to set/overwrite id fields inside object if present
        if isinstance(new_obj, dict):
            # change name/id keys if exist to avoid collisions
            if 'room_id' in new_obj:
                new_obj['room_id'] = new_id
            if 'faculty_id' in new_obj:
                new_obj['faculty_id'] = new_id
            if 'section_id' in new_obj:
                new_obj['section_id'] = new_id
            if 'lab_id' in new_obj:
                new_obj['lab_id'] = new_id
        container[new_id] = new_obj


def _perturb_config_once(base_cfg: Dict[str, Any], index: int) -> Dict[str, Any]:
    """
    Make a single randomized perturbation of the base config and return it.
    Perturbations are small and realistic:
    - duplicate rooms, faculty, sections
    - jitter section sizes
    - change GA params
    - optionally toggle constraints
    """
    cfg = copy.deepcopy(base_cfg)

    # Ensure expected top-level keys exist
    cfg.setdefault('rooms', [])
    cfg.setdefault('faculty', [])
    cfg.setdefault('departments', [])
    cfg.setdefault('sections', [])
    cfg.setdefault('subjects', [])
    cfg.setdefault('labs', [])
    cfg.setdefault('constraints', {})
    cfg.setdefault('genetic_algorithm_params', {})

    # Convert lists to dict maps by id if necessary (your TimetableData accepts lists; keep lists)
    # We'll operate on lists: easier to duplicate items by copying an existing dict and changing its id fields.

    # Duplicate rooms
    base_rooms = cfg.get('rooms', [])
    add_rooms = random.randint(*ROOM_DUPLICATE_RANGE)
    for rdup in range(add_rooms):
        if not base_rooms:
            break
        src = copy.deepcopy(random.choice(base_rooms))
        # create new room id
        src_id = src.get('room_id') or src.get('id') or f"R_base_{rdup}"
        new_id = f"{src_id}_rdup_{index}_{rdup}"
        # update identifiers inside object
        if 'room_id' in src:
            src['room_id'] = new_id
        elif 'id' in src:
            src['id'] = new_id
        # small capacity variation
        try:
            cap = int(src.get('capacity', 60))
            cap += random.randint(-5, 15)
            src['capacity'] = max(10, cap)
        except Exception:
            src['capacity'] = src.get('capacity', 60)
        base_rooms.append(src)
    cfg['rooms'] = base_rooms

    # Duplicate faculty
    base_faculty = cfg.get('faculty', [])
    add_fac = random.randint(*FACULTY_DUPLICATE_RANGE)
    for fdup in range(add_fac):
        if not base_faculty:
            break
        src = copy.deepcopy(random.choice(base_faculty))
        src_id = src.get('faculty_id') or src.get('id') or f"F_base_{fdup}"
        new_id = f"{src_id}_fdup_{index}_{fdup}"
        if 'faculty_id' in src:
            src['faculty_id'] = new_id
        elif 'id' in src:
            src['id'] = new_id
        # tweak max_hours_per_week mildly
        try:
            mh = int(src.get('max_hours_per_week', 10))
            mh += random.randint(-2, 4)
            src['max_hours_per_week'] = max(4, mh)
        except Exception:
            pass
        # subjects list: keep same subjects (faculty can teach same set)
        base_faculty.append(src)
    cfg['faculty'] = base_faculty

    # Duplicate sections (increase timetable load)
    base_sections = cfg.get('sections', [])
    add_secs = random.randint(*SECTION_DUPLICATE_RANGE)
    for sdup in range(add_secs):
        if not base_sections:
            break
        src = copy.deepcopy(random.choice(base_sections))
        src_id = src.get('section_id') or src.get('id') or f"S_base_{sdup}"
        new_id = f"{src_id}_sdup_{index}_{sdup}"
        if 'section_id' in src:
            src['section_id'] = new_id
        elif 'id' in src:
            src['id'] = new_id
        # jitter student_count
        try:
            sc = int(src.get('student_count', 60))
            sc += random.randint(*SECTION_SIZE_JITTER)
            src['student_count'] = max(10, sc)
        except Exception:
            pass
        base_sections.append(src)
    cfg['sections'] = base_sections

    # tweak GA hyperparameters
    gap = cfg.get('genetic_algorithm_params', {})
    gap['population_size'] = random.choice(POP_SIZE_CHOICES)
    gap['generations'] = random.choice(GENS_CHOICES)
    gap['mutation_rate'] = random.choice(MUTATION_CHOICES)
    gap['crossover_rate'] = random.choice(CROSSOVER_CHOICES)
    gap['elite_size'] = random.choice(ELITE_SIZE_CHOICES)
    cfg['genetic_algorithm_params'] = gap

    # Optionally tweak constraints (relax or tighten small chance)
    hc = cfg.get('constraints', {}).get('hard_constraints', {}) or {}
    sc = cfg.get('constraints', {}).get('soft_constraints', {}) or {}

    # small probability to toggle max_classes_per_day
    if random.random() < 0.3:
        # set a reasonable per-day maximum per section
        val = random.randint(3, 6)
        hc['max_classes_per_day_per_section'] = val

    # small chance to add or remove a soft constraint flag
    if random.random() < 0.3:
        # example soft constraint: prefer balanced_daily_load (score-weighted)
        sc['balanced_daily_load_weight'] = random.choice([5, 10, 20])

    # recompute safe limit: avoid creating configs that explode
    est_required = 0
    try:
        est_required = cfg.get('estimated_required_periods', None) or 0
    except Exception:
        est_required = 0

    # guard: if the number of sections, rooms or faculty exceeds safe threshold, trim duplications
    if len(cfg.get('sections', [])) > MAX_TOTAL_ENTRIES:
        cfg['sections'] = cfg['sections'][:MAX_TOTAL_ENTRIES]
    if len(cfg.get('rooms', [])) > MAX_TOTAL_ENTRIES:
        cfg['rooms'] = cfg['rooms'][:MAX_TOTAL_ENTRIES]
    if len(cfg.get('faculty', [])) > MAX_TOTAL_ENTRIES:
        cfg['faculty'] = cfg['faculty'][:MAX_TOTAL_ENTRIES]

    # update constraints structure back
    cfg.setdefault('constraints', {})['hard_constraints'] = hc
    cfg.setdefault('constraints', {})['soft_constraints'] = sc

    # add a metadata tag to config so logs can reference which sample
    cfg.setdefault('meta', {})['sample_index'] = index
    cfg.setdefault('meta', {})['sample_time'] = time.time()
    return cfg


def run_single_sample(cfg: Dict[str, Any], sample_index: int, verbose: bool = True):
    """
    Given a sampled config dict, run the GA and log results.
    Returns the log row dict or None on failure.
    """
    try:
        # Create TimetableData from config dict
        data = ttg.TimetableData(config_dict=cfg)

        # Ensure GA params inside data are set (TimetableData places them into data.ga_params)
        # The runner will override a few defaults to keep runs reasonable if needed
        gap = data.ga_params or {}
        # keep user's selected choices (we already wrote them into cfg), but enforce caps
        gap['population_size'] = int(min(gap.get('population_size', 30), 200))
        gap['generations'] = int(min(gap.get('generations', 100), 200))
        gap['mutation_rate'] = float(gap.get('mutation_rate', 0.05))
        gap['crossover_rate'] = float(gap.get('crossover_rate', 0.8))
        # write back
        data.ga_params = gap

        # Create GA and run
        ga = ttg.GeneticAlgorithm(data)
        ga.initialize_population()
        ga.evolve()

        # get best solution(s)
        best_solutions = ga.get_best_solution()
        best_solution = best_solutions[0] if best_solutions else None

        # log the run (uses your log_ga_run.py)
        log_row = log_run(data, ga, best_solution)

        if verbose:
            idx = cfg.get('meta', {}).get('sample_index', sample_index)
            print(f"[SAMPLE {idx}] logged -> run_id: {log_row.get('run_id') if log_row else 'ERR'}")

        return log_row

    except Exception as e:
        print(f"[ERROR] sample {sample_index} failed: {e}")
        try:
            import traceback
            traceback.print_exc()
        except Exception:
            pass
        return None


def main(num_runs: int = 200, start_index: int = 0, verbose: bool = True):
    base_cfg = safe_load_base_config(BASE_CONFIG_FILE)
    successes = 0
    failures = 0

    for i in range(start_index, start_index + num_runs):
        cfg = _perturb_config_once(base_cfg, i)
        row = run_single_sample(cfg, i, verbose=verbose)
        if row:
            successes += 1
        else:
            failures += 1
        # small sleep to avoid hammering CPU/filesystem too hard in tight loops
        time.sleep(0.05)

    print(f"Experiment run finished. successes: {successes}, failures: {failures}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run many GA experiments and log results")
    parser.add_argument("--num_runs", type=int, default=200, help="Number of sampled runs to execute")
    parser.add_argument("--start_index", type=int, default=0, help="Starting sample index (for resume)")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--quiet", action="store_true", help="Suppress per-sample prints")
    args = parser.parse_args()
    random.seed(args.seed)
    main(num_runs=args.num_runs, start_index=args.start_index, verbose=(not args.quiet))
