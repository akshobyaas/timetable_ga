# backend/ga_solver.py
"""
Genetic Algorithm timetable solver for engineering colleges.

Key features:
 - Handles Lectures (1-hour) and Labs (2-hour, contiguous).
 - Parses L-T-P input from courses file.
 - Manages constraints for a single student group.
 - Constraints: Faculty clashes, room clashes, room capacity, lab contiguity.
"""

import random
import math
import re
from collections import defaultdict

# GA parameters (tunable)
POPULATION_SIZE = 100
GENERATIONS = 200
TOURNAMENT_K = 5
CROSSOVER_RATE = 0.9
MUTATION_RATE = 0.1
ELITISM = 2
NO_IMPROVE_LIMIT = 40

# Penalty weights (tunable)
PENALTY_FACULTY_CLASH = 5000
PENALTY_ROOM_CLASH = 5000
PENALTY_GROUP_CLASH = 5000
PENALTY_LAB_CONTIGUITY = 10000 # Very high penalty

# -------------------------
# Helpers
# -------------------------
def _pick_col(cols, candidates, default=None):
    """Return first matching column name from candidates present in cols (case-insensitive)."""
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand is None: continue
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]
    return default

# -------------------------
# Domain Construction
# -------------------------
def _build_domain(courses_df, faculty_df, slots_df, rooms_df):
    """
    Builds the problem domain from input dataframes.
    1. Parses L-T-P to create tasks (lectures, labs).
    2. Creates a list of valid choices (faculty, room, slot) for each task.
    """
    # Normalize data
    slots = sorted(slots_df.to_dict(orient="records"), key=lambda s: (s['day'], s['slot_index']))
    rooms = rooms_df.to_dict(orient="records")
    faculty_map = {f['id']: f['name'] for f in faculty_df.to_dict(orient="records")}

    tasks = []
    # Create tasks from courses based on L-T-P
    for _, course in courses_df.iterrows():
        l, t, p = map(int, (course.get('ltp') or '0-0-0').split('-'))
        
        # Add lecture tasks
        for _ in range(l):
            tasks.append({
                'course_code': course['course_code'],
                'type': 'Lecture',
                'duration': 1,
                'student_group': course['student_group'],
                'student_count': course['student_count'],
                'faculty_id': course['faculty_id'],
                'required_room_type': course['required_room_type_lecture']
            })
        
        # Add lab tasks (duration 2)
        for _ in range(p):
            tasks.append({
                'course_code': course['course_code'],
                'type': 'Lab',
                'duration': 2,
                'student_group': course['student_group'],
                'student_count': course['student_count'],
                'faculty_id': course['faculty_id'],
                'required_room_type': course['required_room_type_lab']
            })
        # Tutorials can be added here if needed, assuming duration 1

    # Create choices for each task
    choices_list = []
    for task in tasks:
        choices = []
        # Filter rooms based on type and capacity
        valid_rooms = [r for r in rooms if r['room_type'] == task['required_room_type'] and r['capacity'] >= task['student_count']]
        
        # Iterate through all possible start slots
        for i in range(len(slots)):
            start_slot = slots[i]
            
            # Check for lab contiguity
            if task['duration'] > 1:
                if i + task['duration'] > len(slots): continue # Not enough slots left
                # Check if subsequent slots are on the same day and consecutive
                is_contiguous = True
                for j in range(1, task['duration']):
                    if slots[i+j]['day'] != start_slot['day'] or slots[i+j]['slot_index'] != start_slot['slot_index'] + j:
                        is_contiguous = False
                        break
                if not is_contiguous: continue

            for room in valid_rooms:
                choices.append({
                    'faculty_id': task['faculty_id'],
                    'room_id': room['room_id'],
                    'start_slot_index': start_slot['slot_index'],
                    'day': start_slot['day']
                })
        choices_list.append(choices)

    return tasks, choices_list, slots, faculty_map

# -------------------------
# Fitness Calculation
# -------------------------
def _fitness_of_individual(individual, tasks, choices_list):
    """
    Calculates the fitness of a timetable solution (an individual).
    Fitness starts high and is reduced by penalties for constraint violations.
    """
    penalty = 0
    
    # Keep track of resource usage: (resource_type, resource_id, day, slot_index)
    usage = defaultdict(list)

    for i, gene in enumerate(individual):
        task = tasks[i]
        choice = choices_list[i][gene]
        
        day = choice['day']
        faculty_id = choice['faculty_id']
        room_id = choice['room_id']
        student_group = task['student_group']
        
        # Check for clashes over the duration of the task
        for j in range(task['duration']):
            slot_idx = choice['start_slot_index'] + j
            
            # Faculty clash
            if (faculty_id, day, slot_idx) in usage['faculty']: penalty += PENALTY_FACULTY_CLASH
            usage['faculty'].append((faculty_id, day, slot_idx))
            
            # Room clash
            if (room_id, day, slot_idx) in usage['room']: penalty += PENALTY_ROOM_CLASH
            usage['room'].append((room_id, day, slot_idx))

            # Student group clash
            if (student_group, day, slot_idx) in usage['group']: penalty += PENALTY_GROUP_CLASH
            usage['group'].append((student_group, day, slot_idx))

    # The lab contiguity is a hard constraint handled during choice generation,
    # but we can add a check here for robustness if needed.

    base_fitness = 100000.0
    return max(0.0, base_fitness - penalty)

# -------------------------
# Genetic Algorithm Operations
# -------------------------
def _random_individual(choices_list):
    return [random.randrange(len(choices)) for choices in choices_list]

def _crossover(a, b):
    if len(a) < 2: return a[:], b[:]
    point = random.randrange(1, len(a))
    return a[:point] + b[point:], b[:point] + a[point:]

def _mutate(individual, choices_list, mutation_rate=MUTATION_RATE):
    for i in range(len(individual)):
        if random.random() < mutation_rate and len(choices_list[i]) > 0:
            individual[i] = random.randrange(len(choices_list[i]))

def _evolve_population(population, fitnesses, choices_list):
    n = len(population)
    new_pop = []
    
    # Elitism
    sorted_idx = sorted(range(n), key=lambda i: fitnesses[i], reverse=True)
    for i in sorted_idx[:ELITISM]:
        new_pop.append(population[i][:])

    # Tournament Selection and Crossover
    def tournament_select():
        best = None
        best_f = -1
        for _ in range(TOURNAMENT_K):
            idx = random.randrange(n)
            f = fitnesses[idx]
            if f > best_f:
                best = population[idx]
                best_f = f
        return best

    while len(new_pop) < n:
        p1 = tournament_select()
        p2 = tournament_select()
        c1, c2 = (p1[:], p2[:]) if random.random() >= CROSSOVER_RATE else _crossover(p1, p2)
        _mutate(c1, choices_list)
        _mutate(c2, choices_list)
        new_pop.append(c1)
        if len(new_pop) < n:
            new_pop.append(c2)
            
    return new_pop

# -------------------------
# Main Entry Point
# -------------------------
def generate_timetable(courses_df, faculty_df, slots_df, rooms_df):
    tasks, choices_list, slots, faculty_map = _build_domain(courses_df, faculty_df, slots_df, rooms_df)

    if not tasks:
        return {"assignments": [], "best_fitness": 0.0, "error": "No tasks created from courses. Check L-T-P format and values."}
    
    for i, choices in enumerate(choices_list):
        if not choices:
            return {"assignments": [], "best_fitness": 0.0, "error": f"No valid choices for task {i+1} ('{tasks[i]['course_code']}' {tasks[i]['type']}). Check room availability and capacity."}

    # --- Run GA ---
    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]
    fitnesses = [_fitness_of_individual(ind, tasks, choices_list) for ind in population]

    best_ind = None
    best_fitness = -1
    no_improve_counter = 0

    for gen in range(GENERATIONS):
        population = _evolve_population(population, fitnesses, choices_list)
        fitnesses = [_fitness_of_individual(ind, tasks, choices_list) for ind in population]
        
        gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
        gen_best_f = fitnesses[gen_best_idx]

        if gen_best_f > best_fitness:
            best_fitness = gen_best_f
            best_ind = population[gen_best_idx][:]
            no_improve_counter = 0
        else:
            no_improve_counter += 1
        
        if no_improve_counter >= NO_IMPROVE_LIMIT:
            break

    # --- Decode and return result ---
    if best_ind is None:
        return {"assignments": [], "best_fitness": 0.0, "error": "Failed to find a solution."}

    assignments = []
    for i, gene in enumerate(best_ind):
        task = tasks[i]
        choice = choices_list[i][gene]
        
        for j in range(task['duration']):
            slot_index = choice['start_slot_index'] + j
            # Find the corresponding slot details
            slot_info = next((s for s in slots if s['day'] == choice['day'] and s['slot_index'] == slot_index), None)

            assignments.append({
                "day": choice['day'],
                "slot_index": slot_index,
                "slot_id": slot_info['id'] if slot_info else f"{choice['day']}-{slot_index}",
                "start_time": slot_info.get('start_time'),
                "end_time": slot_info.get('end_time'),
                "course": task['course_code'],
                "class_type": task['type'],
                "student_group": task['student_group'],
                "faculty": faculty_map.get(task['faculty_id'], task['faculty_id']),
                "room": choice['room_id']
            })

    return {"assignments": assignments, "best_fitness": float(best_fitness)}
