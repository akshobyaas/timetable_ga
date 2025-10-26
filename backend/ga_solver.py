# backend/ga_solver.py
"""
Optimized Genetic Algorithm timetable solver (MVP).

Key optimizations:
- Precompute choice arrays (faculty_id, slot_id) to avoid dict lookups in fitness.
- Compute fitness exactly once per individual per generation (no duplicate evaluations).
- Avoid building assignment dicts inside fitness; use integer/index lookups.
- Add early-stop on stagnation (NO_IMPROVE_LIMIT).
- Keep behavior compatible with previous interface.
"""

import random
import math
from collections import defaultdict

# GA parameters (tunable)
POPULATION_SIZE = 80   # reduce for quick tests (e.g., 40)
GENERATIONS = 150      # reduce for quick tests (e.g., 80)
TOURNAMENT_K = 3
CROSSOVER_RATE = 0.9
MUTATION_RATE = 0.08
ELITISM = 1  # keep top N
NO_IMPROVE_LIMIT = 30  # early stop if no improvement for this many generations

# -------------------------
# Domain construction
# -------------------------
def _build_domain(courses_df, faculty_df, slots_df):
    """Build tasks (one per required hourly slot) and choices per task."""
    # Convert frames to lists of dicts for easier use
    slots = slots_df.to_dict(orient="records")
    # standardize slot id and slot_index
    for s in slots:
        if 'id' not in s:
            s['id'] = f"{s.get('day','')}-{s.get('slot_index',0)}"
        s['slot_index'] = int(s.get('slot_index', 0))

    faculties = faculty_df.to_dict(orient="records")
    # normalize can_teach lists
    for f in faculties:
        raw = f.get('can_teach', '')
        if isinstance(raw, str):
            f['_can_teach_list'] = [c.strip() for c in raw.split('|') if c.strip()]
        else:
            f['_can_teach_list'] = []

    # Build task list: one task per required hourly slot of course
    tasks = []  # each task is dict with course_code, course_title
    for _, c in courses_df.iterrows():
        code = str(c['code'])
        title = c.get('title', '')
        hours = int(c.get('weekly_hours', 1))
        for _ in range(hours):
            tasks.append({'code': code, 'title': title})

    # For each task, build choices = list of (slot, faculty) pairs where faculty can teach course
    choices_list = []
    for t in tasks:
        code = t['code']
        choices = []
        for s in slots:
            for f in faculties:
                if code in f['_can_teach_list']:
                    choices.append({
                        'slot_id': s['id'],
                        'day': s.get('day'),
                        'slot_index': int(s.get('slot_index', 0)),
                        'faculty_id': f.get('id'),
                        'faculty_name': f.get('name')
                    })
        # If no faculty can teach this course, allow any faculty (fallback)
        if not choices:
            for s in slots:
                for f in faculties:
                    choices.append({
                        'slot_id': s['id'],
                        'day': s.get('day'),
                        'slot_index': int(s.get('slot_index', 0)),
                        'faculty_id': f.get('id'),
                        'faculty_name': f.get('name')
                    })
        choices_list.append(choices)

    return tasks, choices_list

# -------------------------
# Precompute structures
# -------------------------
def _precompute_choice_arrays(choices_list):
    """
    Convert choices_list (list of list-of-dicts) into two parallel lists:
      - choice_faculty_ids[i] = list of faculty ids for task i (indexable by gene)
      - choice_slot_ids[i] = list of slot ids for task i
    This avoids repeated dict lookups during fitness evaluation.
    """
    choice_faculty_ids = []
    choice_slot_ids = []
    # If choices_list is empty for any task, caller should have handled it
    for choices in choices_list:
        facs = []
        slots = []
        for ch in choices:
            facs.append(ch.get('faculty_id'))
            slots.append(ch.get('slot_id'))
        choice_faculty_ids.append(facs)
        choice_slot_ids.append(slots)
    return choice_faculty_ids, choice_slot_ids

# -------------------------
# Individual ops
# -------------------------
def _random_individual(choices_list):
    """Create a random individual: for each task pick random index into its choices."""
    return [random.randrange(len(choices)) for choices in choices_list]

def _decode_individual(individual, tasks, choices_list):
    """Decode individual into assignments (list of dicts). Kept for output only."""
    assignments = []
    for i, gene in enumerate(individual):
        choice = choices_list[i][gene]
        assignments.append({
            'day': choice['day'],
            'slot_index': int(choice['slot_index']),
            'slot_id': choice['slot_id'],
            'course': tasks[i]['code'],
            'faculty_id': choice['faculty_id'],
            'faculty': choice['faculty_name']
        })
    return assignments

# -------------------------
# Fitness (optimized)
# -------------------------
def _fitness_of_individual(individual, choice_faculty_ids, choice_slot_ids):
    """
    Compute fitness directly from gene indices and precomputed faculty/slot arrays.
    Avoid constructing full assignment dicts — only count collisions.
    """
    # count (faculty_id, slot_id) collisions using a dict
    counter = {}
    for i, gene in enumerate(individual):
        # get faculty and slot directly
        # gene is an index into choice lists for task i
        try:
            faculty_id = choice_faculty_ids[i][gene]
            slot_id = choice_slot_ids[i][gene]
        except Exception:
            # fallback — should not occur if individuals are valid
            continue
        key = (faculty_id, slot_id)
        counter[key] = counter.get(key, 0) + 1

    penalty = 0
    for cnt in counter.values():
        if cnt > 1:
            penalty += (cnt - 1) * 1000

    base = 100000  # base to keep fitness positive
    fitness = base - penalty
    return float(max(0, fitness))

# -------------------------
# Selection / crossover / mutation
# -------------------------


def _crossover(a, b):
    """Single-point crossover"""
    if len(a) < 2:
        return a[:], b[:]
    point = random.randrange(1, len(a))
    child1 = a[:point] + b[point:]
    child2 = b[:point] + a[point:]
    return child1, child2

def _mutate(individual, choices_list, mutation_rate=MUTATION_RATE):
    """Per-gene mutation: replace gene by random choice for that task."""
    for i in range(len(individual)):
        if random.random() < mutation_rate:
            individual[i] = random.randrange(len(choices_list[i]))

# -------------------------
# Evolution (uses cached fitnesses)
# -------------------------
def _evolve_population(population, fitnesses, choices_list):
    """
    Evolve population using provided fitnesses (cached).
    Returns the new population (list of individuals).
    Caller is responsible to compute fitnesses for the returned population.
    """
    n = len(population)
    new_pop = []

    # keep top ELITISM individuals (by fitness)
    sorted_idx = sorted(range(n), key=lambda i: fitnesses[i], reverse=True)
    for i in sorted_idx[:ELITISM]:
        new_pop.append(population[i][:])  # copy

    # tournament selection using cached fitnesses
    def tournament_select():
        best = None
        best_f = None
        for _ in range(TOURNAMENT_K):
            idx = random.randrange(n)
            f = fitnesses[idx]
            if (best is None) or (f > best_f):
                best = population[idx]
                best_f = f
        return best

    while len(new_pop) < n:
        parent1 = tournament_select()
        parent2 = tournament_select()
        if random.random() < CROSSOVER_RATE:
            child1, child2 = _crossover(parent1, parent2)
        else:
            child1, child2 = parent1[:], parent2[:]
        _mutate(child1, choices_list)
        _mutate(child2, choices_list)
        new_pop.append(child1)
        if len(new_pop) < n:
            new_pop.append(child2)

    return new_pop

# -------------------------
# Main GA entry
# -------------------------
def generate_timetable(courses_df, faculty_df, slots_df):
    """
    Main entry called by backend.
    Returns dict: { assignments: [ ... ], best_fitness: float }
    """
    # Build domain
    tasks, choices_list = _build_domain(courses_df, faculty_df, slots_df)
    if not tasks:
        return {"assignments": [], "best_fitness": 0.0, "error": "No tasks found (check courses.csv)"}

    # quick sanity: ensure choices exist for each task
    for i, choices in enumerate(choices_list):
        if not choices:
            return {"assignments": [], "best_fitness": 0.0, "error": f"No choices for task {i}"}

    # Precompute arrays for fast lookups in fitness
    choice_faculty_ids, choice_slot_ids = _precompute_choice_arrays(choices_list)

    # initialize population
    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]

    # compute initial fitnesses (one pass)
    fitnesses = [_fitness_of_individual(ind, choice_faculty_ids, choice_slot_ids) for ind in population]

    best_ind = None
    best_fitness = -math.inf
    no_improve_counter = 0

    # track best from initial population
    for idx, f in enumerate(fitnesses):
        if f > best_fitness:
            best_fitness = f
            best_ind = population[idx][:]
    if best_fitness >= 100000:
        # perfect found already
        pass
    else:
        # main GA loop
        for gen in range(GENERATIONS):
            # evolve using cached fitnesses (avoid double eval)
            population = _evolve_population(population, fitnesses, choices_list)

            # compute fitnesses for the new population (single pass)
            fitnesses = [_fitness_of_individual(ind, choice_faculty_ids, choice_slot_ids) for ind in population]

            # find best in this generation
            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_f = fitnesses[gen_best_idx]
            if gen_best_f > best_fitness:
                best_fitness = gen_best_f
                best_ind = population[gen_best_idx][:]
                no_improve_counter = 0
            else:
                no_improve_counter += 1

            # occasional log
            pass

            # early stop if perfect
            if best_fitness >= 100000:
                pass
                break

            # early stop on stagnation
            if no_improve_counter >= NO_IMPROVE_LIMIT:
                pass
                break

    # decode best individual to assignments for output
    if best_ind is None:
        # fallback to random
        best_ind = _random_individual(choices_list)
        best_fitness = _fitness_of_individual(best_ind, choice_faculty_ids, choice_slot_ids)

    assignments = _decode_individual(best_ind, tasks, choices_list)

    # compress assignments: group by slot/day to match earlier format (no slot_id required)
    out_assignments = []
    for a in assignments:
        out_assignments.append({
            "day": a["day"],
            "slot_index": int(a["slot_index"]),
            "course": a["course"],
            "faculty": a["faculty"]
        })

    return {"assignments": out_assignments, "best_fitness": float(best_fitness)}
