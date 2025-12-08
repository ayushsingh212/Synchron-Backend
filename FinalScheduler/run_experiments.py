import os
import json
import random
import sys
from datetime import datetime
from timetable_generator import TimetableData, GeneticAlgorithm
from log_ga_run import log_run

def generate_random_ga_config(base_config: dict):
    """Create a slightly randomized GA config for each experiment."""
    cfg = base_config.copy()

    cfg["population_size"] = random.choice([20, 30, 40, 50, 60])
    cfg["generations"] = random.choice([50, 80, 100, 120, 150])
    cfg["mutation_rate"] = round(random.uniform(0.01, 0.20), 3)
    cfg["crossover_rate"] = round(random.uniform(0.6, 0.9), 2)

    return cfg


def run_single_experiment(base_config_path: str):
    """Runs one GA experiment and logs it."""
    with open(base_config_path, "r") as f:
        base_config = json.load(f)

    random_cfg = generate_random_ga_config(base_config.get("ga_params", {}))
    base_config["ga_params"] = random_cfg

    data = TimetableData(config_dict=base_config)
    ga = GeneticAlgorithm(data)

    ga.initialize_population()
    ga.evolve()

    best_solution = ga.get_best_solution()
    if best_solution is None:
        print("⚠️ Warning: No valid solution found for this experiment.")
        return

    log_run(data, ga, best_solution)
    print("✔ Experiment logged with GA params:", random_cfg)


def main():
    base_config_path = "corrected_timetable_config.json"

    # Allow user to pass experiment count from terminal
    if len(sys.argv) > 1:
        try:
            N = int(sys.argv[1])
        except:
            print("Invalid number. Running with default 100 experiments.")
            N = 100
    else:
        N = 100  # Default runs

    print(f" Starting {N} GA experiments...")
    for i in range(N):
        print(f"\n--- Experiment {i+1}/{N} ---")
        run_single_experiment(base_config_path)

    print("\n🎉 All experiments completed.")
    print("Dataset ready for ML training.")


if __name__ == "__main__":
    main()
