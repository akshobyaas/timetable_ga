# backend/ga_solver.py
"""
Simple Genetic Algorithm timetable solver (educational / MVP quality).

How it works (brief):
- Each required "class-hour" for all courses is a task.
- For each task we make a list of valid choices = (slot, faculty) pairs
  where the faculty can teach that course.
- An individual is a list of integers; gene i is an index selecting one
  choice from choices_list[i].
- Fitness penalizes faculty clashes (same faculty in same slot).
- GA: population init, tournament selection, single-point crossover,
  per-gene mutation.
"""

import random
import math
from collections import defaultdict

# GA parameters (reasonable defaults for MVP)
POPULATION_SIZE = 80
GENERATIONS = 150
TOURNAMENT_K = 3
CROSSOVER_RATE = 0.9
MUTATION_RATE = 0.08
ELITISM = 1  # keep top 1

def _build_domain(courses_df, faculty_df, slots_df):
    """Build tasks and choices per task."""
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

def _random_individual(choices_list):
    """Create a random individual: for each task pick random index into its choices."""
    return [random.randrange(len(choices)) for choices in choices_list]

def _decode_individual(individual, tasks, choices_list):
    """Decode individual into assignments (list of dicts)."""
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

def _fitness_of_individual(individual, tasks, choices_list):
    """
    Compute fitness: high score is better.
    Penalize faculty clashes (same faculty & same slot).
    """
    assignments = _decode_individual(individual, tasks, choices_list)

    penalty = 0
    # count (faculty_id, slot_id) collisions
    counter = defaultdict(int)
    for a in assignments:
        key = (a['faculty_id'], a['slot_id'])
        counter[key] += 1
    for k, cnt in counter.items():
        if cnt > 1:
            # heavy penalty per extra assignment
            penalty += (cnt - 1) * 1000

    # Additional soft penalties could be added (spread, consecutive hours, room capacity)
    base = 100000  # base to keep fitness positive
    fitness = base - penalty
    # ensure non-negative
    return float(max(0, fitness))

def _tournament_select(population, fitnesses, k=TOURNAMENT_K):
    best = None
    best_f = None
    n = len(population)
    for _ in range(k):
        idx = random.randrange(n)
        f = fitnesses[idx]
        if (best is None) or (f > best_f):
            best = population[idx]
            best_f = f
    return best

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

def _evolve_population(population, choices_list, tasks):
    # evaluate fitnesses
    fitnesses = [_fitness_of_individual(ind, tasks, choices_list) for ind in population]
    # keep elitism
    new_pop = []
    # keep top ELITISM individuals
    sorted_idx = sorted(range(len(population)), key=lambda i: fitnesses[i], reverse=True)
    for i in sorted_idx[:ELITISM]:
        new_pop.append(population[i][:])  # copy

    # build rest of new population
    while len(new_pop) < len(population):
        parent1 = _tournament_select(population, fitnesses)
        parent2 = _tournament_select(population, fitnesses)
        if random.random() < CROSSOVER_RATE:
            child1, child2 = _crossover(parent1, parent2)
        else:
            child1, child2 = parent1[:], parent2[:]
        _mutate(child1, choices_list)
        _mutate(child2, choices_list)
        new_pop.append(child1)
        if len(new_pop) < len(population):
            new_pop.append(child2)
    return new_pop

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

    # initialize population
    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]

    best_ind = None
    best_fitness = -math.inf

    # run GA
    for gen in range(GENERATIONS):
        # evaluate and track best
        for ind in population:
            f = _fitness_of_individual(ind, tasks, choices_list)
            if f > best_fitness:
                best_fitness = f
                best_ind = ind[:]

        # early exit: perfect (no penalty) -> fitness == base (100000)
        if best_fitness >= 100000:
            # print progress to server logs
            print(f"[GA] generation {gen}: perfect solution found")
            break

        # evolve
        population = _evolve_population(population, choices_list, tasks)

        # occasional progress log (appears in server terminal)
        if gen % 20 == 0:
            print(f"[GA] gen {gen} best_fitness={best_fitness}")

    # decode best individual to assignments
    if best_ind is None:
        # fallback to random
        best_ind = _random_individual(choices_list)
        best_fitness = _fitness_of_individual(best_ind, tasks, choices_list)

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
