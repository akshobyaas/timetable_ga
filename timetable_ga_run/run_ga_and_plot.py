# run_ga_and_plot.py
import csv
import matplotlib.pyplot as plt
import random
import os
from datetime import datetime

# ---- Replace this block with calls to your actual GA components when ready ----
# For now this simulates a GA run and returns a best fitness list per generation.
def run_sample_ga(max_generations=500, population_size=100):
    random.seed(42)
    best_fitness_list = []
    best = 15000
    for gen in range(max_generations):
        # simulated improvement behavior:
        if gen < 180:
            best = max(0, int(best * 0.97) + random.randint(-10, 20))
        else:
            best = max(0, int(best * 0.985) + random.randint(-5, 10))
        best_fitness_list.append(best)
    return best_fitness_list
# -------------------------------------------------------------------------------

def save_fitness_csv(best_fitness_list, out_dir="outputs"):
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, "fitness_history.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["generation", "best_fitness"])
        for i, v in enumerate(best_fitness_list):
            writer.writerow([i, v])
    return csv_path

def plot_fitness(best_fitness_list, out_dir="outputs"):
    os.makedirs(out_dir, exist_ok=True)
    png_path = os.path.join(out_dir, "fitness_convergence.png")
    plt.figure(figsize=(10, 5))
    plt.plot(range(len(best_fitness_list)), best_fitness_list)
    plt.xlabel("Generation")
    plt.ylabel("Penalty (Lower is Better)")
    plt.title("Genetic Algorithm Fitness Convergence (Best Individual per Generation)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_path, dpi=300)
    plt.close()
    return png_path

def main():
    start = datetime.now()
    print("Starting GA run at", start.isoformat())
    best_fitness_list = run_sample_ga(max_generations=500, population_size=100)
    csv_path = save_fitness_csv(best_fitness_list)
    png_path = plot_fitness(best_fitness_list)
    end = datetime.now()
    print("Finished GA run at", end.isoformat())
    print("Saved:", csv_path)
    print("Saved:", png_path)

if __name__ == "__main__":
    main()
