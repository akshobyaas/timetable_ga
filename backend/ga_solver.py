# backend/ga_solver.py
"""
Genetic Algorithm timetable solver for engineering colleges.

Key features:
 - Handles Lectures (1-hour) and Labs (2-hour, contiguous).
 - Parses L-T-P input from courses file robustly.
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
PENALTY_LAB_CONTIGUITY = 10000  # Very high penalty

# -------------------------
# Helpers
# -------------------------
def _pick_col(cols, candidates, default=None):
    """Return first matching column name from candidates present in cols (case-insensitive)."""
    lower_map = {c.lower(): c for c in cols}
    for cand in candidates:
        if cand is None:
            continue
        key = cand.lower()
        if key in lower_map:
            return lower_map[key]
    return default

def _parse_ltp(ltp_value):
    """Robustly parse an L-T-P value like '3-0-2'. Returns (l, t, p) as ints."""
    if ltp_value is None:
        return 0, 0, 0
    if isinstance(ltp_value, (int, float)):
        # unusual case where ltp given as number — treat as lectures
        try:
            return int(ltp_value), 0, 0
        except Exception:
            return 0, 0, 0
    try:
        s = re.sub(r'\s+', '', str(ltp_value).strip())
        parts = s.split('-')
        parts += ['0'] * (3 - len(parts))
        l = int(parts[0]) if parts[0] else 0
        t = int(parts[1]) if parts[1] else 0
        p = int(parts[2]) if parts[2] else 0
        return l, t, p
    except Exception:
        return 0, 0, 0

# -------------------------
# Domain Construction
# -------------------------
def _build_domain(courses_df, faculty_df, slots_df, rooms_df):
    """
    Build tasks from courses (L-T-P), normalize slots, and produce choices for each task.
    Returns: tasks, choices_list, normalized_slots, faculty_map
    """
    # Normalize slots: ensure slot_index is int, fill missing ids and times
    raw_slots = slots_df.to_dict(orient='records')
    slots = []
    for s in raw_slots:
        day = s.get('day') or s.get('Day') or 'Day'
        # safe parse slot_index
        try:
            slot_index = int(s.get('slot_index') if s.get('slot_index') is not None else s.get('slotIndex', 0))
        except Exception:
            slot_index = 0
        slots.append({
            'id': s.get('id') or f"{day}-{slot_index}",
            'day': day,
            'slot_index': slot_index,
            'start_time': s.get('start_time'),
            'end_time': s.get('end_time'),
            'type': s.get('type', 'Class')
        })
    # sort by day then slot_index (deterministic)
    slots = sorted(slots, key=lambda x: (str(x['day']), int(x['slot_index'])))

    # Normalize rooms and faculty
    rooms = rooms_df.to_dict(orient='records')
    fac_records = faculty_df.to_dict(orient='records')
    # Build faculty_map safely using possible name/id column names
    fac_cols = faculty_df.columns.tolist()
    fac_id_col = _pick_col(fac_cols, ['id', 'faculty_id', 'facultyId'], default=None)
    fac_name_col = _pick_col(fac_cols, ['name', 'faculty_name', 'facultyName'], default=None)
    faculty_map = {}
    for f in fac_records:
        fid = f.get(fac_id_col) if fac_id_col else f.get('id') or f.get('faculty_id') or f.get('facultyId')
        fname = f.get(fac_name_col) if fac_name_col else f.get('name') or f.get('faculty_name') or f.get('facultyName') or str(fid)
        faculty_map[str(fid)] = fname

    # Build tasks from courses based on L-T-P
    tasks = []
    course_cols = courses_df.columns.tolist()
    course_code_col = _pick_col(course_cols, ['course_code', 'code', 'courseCode', 'course'], default='course_code')
    ltp_col = _pick_col(course_cols, ['ltp', 'L-T-P', 'LTP'], default='ltp')
    student_group_col = _pick_col(course_cols, ['student_group', 'studentGroup', 'group'], default='student_group')
    student_count_col = _pick_col(course_cols, ['student_count', 'studentCount', 'students'], default='student_count')
    fac_col = _pick_col(course_cols, ['faculty_id', 'faculty', 'teacher_id', 'instructor'], default='faculty_id')
    req_room_lecture_col = _pick_col(course_cols, ['required_room_type_lecture', 'req_room_lecture', 'req_room_lecture_type'], default='required_room_type_lecture')
    req_room_lab_col = _pick_col(course_cols, ['required_room_type_lab', 'req_room_lab', 'req_room_lab_type'], default='required_room_type_lab')

    for _, course in courses_df.iterrows():
        course_code = course.get(course_code_col) or course.get('course_code') or course.get('code') or 'UNKNOWN'
        l, t, p = _parse_ltp(course.get(ltp_col, '0-0-0'))
        student_group = course.get(student_group_col) or course.get('student_group') or 'Group'
        try:
            student_count = int(course.get(student_count_col) or 0)
        except Exception:
            student_count = 0
        faculty_id = str(course.get(fac_col) or course.get('faculty_id') or course.get('faculty') or '')
        req_room_lecture = course.get(req_room_lecture_col) or course.get('req_room_lecture') or course.get('required_room_type_lecture') or None
        req_room_lab = course.get(req_room_lab_col) or course.get('req_room_lab') or course.get('required_room_type_lab') or None

        # Add lecture tasks (duration 1 per lecture hour)
        for _ in range(l):
            tasks.append({
                'course_code': course_code,
                'type': 'Lecture',
                'duration': 1,
                'student_group': student_group,
                'student_count': student_count,
                'faculty_id': faculty_id,
                'required_room_type': req_room_lecture
            })

        # Add lab tasks (duration 2 per lab hour unit)
        for _ in range(p):
            tasks.append({
                'course_code': course_code,
                'type': 'Lab',
                'duration': 2,
                'student_group': student_group,
                'student_count': student_count,
                'faculty_id': faculty_id,
                'required_room_type': req_room_lab
            })
        # Tutorials (T) can be added here if needed (duration 1)

    # Create choices for each task (faculty fixed per task per your CSV design)
    choices_list = []
    for task in tasks:
        choices = []
        # Filter rooms based on type and capacity (if required_room_type is None, allow all)
        if task['required_room_type']:
            valid_rooms = [r for r in rooms if r.get('room_type') == task['required_room_type'] and int(r.get('capacity', 0)) >= int(task['student_count'] or 0)]
        else:
            valid_rooms = [r for r in rooms if int(r.get('capacity', 0)) >= int(task['student_count'] or 0)]

        # If no valid room, choices will remain empty and caller will receive a clear error
        for i in range(len(slots)):
            start_slot = slots[i]
            # Lab contiguity check (if duration > 1)
            if task['duration'] > 1:
                if i + task['duration'] > len(slots):
                    continue
                contiguous = True
                for j in range(1, task['duration']):
                    next_slot = slots[i + j]
                    if next_slot['day'] != start_slot['day'] or next_slot['slot_index'] != start_slot['slot_index'] + j:
                        contiguous = False
                        break
                if not contiguous:
                    continue
            # For each valid room, create a choice
            for room in valid_rooms:
                choices.append({
                    'faculty_id': task['faculty_id'],
                    'room_id': room.get('room_id') or room.get('id') or room.get('name'),
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
    penalty = 0.0

    # Use sets for O(1) clash checks
    used_faculty = set()   # (faculty_id, day, slot_idx)
    used_room = set()      # (room_id, day, slot_idx)
    used_group = set()     # (group, day, slot_idx)

    # Evaluate each task placement
    for i, gene in enumerate(individual):
        task = tasks[i]
        choices = choices_list[i]
        if not choices:
            # impossible placement (should have been caught earlier)
            penalty += 100000.0
            continue
        # gene must be a valid index; safe-check
        if gene < 0 or gene >= len(choices):
            penalty += 100000.0
            continue

        choice = choices[gene]
        day = choice['day']
        faculty_id = str(choice['faculty_id'])
        room_id = choice['room_id']
        group = task['student_group']

        # for the duration of the task (1 or 2), check resource usage
        for j in range(task['duration']):
            slot_idx = choice['start_slot_index'] + j

            if (faculty_id, day, slot_idx) in used_faculty:
                penalty += PENALTY_FACULTY_CLASH
            used_faculty.add((faculty_id, day, slot_idx))

            if (room_id, day, slot_idx) in used_room:
                penalty += PENALTY_ROOM_CLASH
            used_room.add((room_id, day, slot_idx))

            if (group, day, slot_idx) in used_group:
                penalty += PENALTY_GROUP_CLASH
            used_group.add((group, day, slot_idx))

    base_fitness = 100000.0
    fitness = max(0.0, base_fitness - penalty)
    return float(fitness)

# -------------------------
# GA operators
# -------------------------
def _random_individual(choices_list):
    individual = []
    for choices in choices_list:
        if not choices:
            individual.append(0)
        else:
            individual.append(random.randrange(len(choices)))
    return individual

def _crossover(a, b):
    if len(a) < 2:
        return a[:], b[:]
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
    for idx in sorted_idx[:ELITISM]:
        new_pop.append(population[idx][:])

    # tournament selection
    def tournament_select():
        best = None
        best_f = -1
        for _ in range(TOURNAMENT_K):
            idx = random.randrange(n)
            f = fitnesses[idx]
            if f > best_f or best is None:
                best = population[idx]
                best_f = f
        return best

    while len(new_pop) < n:
        p1 = tournament_select()
        p2 = tournament_select()
        if random.random() < CROSSOVER_RATE:
            c1, c2 = _crossover(p1, p2)
        else:
            c1, c2 = p1[:], p2[:]
        _mutate(c1, choices_list)
        _mutate(c2, choices_list)
        new_pop.append(c1)
        if len(new_pop) < n:
            new_pop.append(c2)

    return new_pop

# -------------------------
# Main Entry
# -------------------------
def generate_timetable(courses_df, faculty_df, slots_df, rooms_df):
    tasks, choices_list, slots, faculty_map = _build_domain(courses_df, faculty_df, slots_df, rooms_df)

    if not tasks:
        return {"assignments": [], "best_fitness": 0.0, "error": "No tasks created from courses. Check L-T-P format and values."}

    for i, choices in enumerate(choices_list):
        if not choices:
            return {"assignments": [], "best_fitness": 0.0, "error": f"No valid choices for task {i+1} ('{tasks[i]['course_code']}' {tasks[i]['type']}). Check room availability and capacity."}

    # Initialize population
    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]
    fitnesses = [_fitness_of_individual(ind, tasks, choices_list) for ind in population]

    best_ind = None
    best_fitness = -1.0
    no_improve = 0

    for gen in range(GENERATIONS):
        population = _evolve_population(population, fitnesses, choices_list)
        fitnesses = [_fitness_of_individual(ind, tasks, choices_list) for ind in population]

        gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
        gen_best_f = fitnesses[gen_best_idx]

        if gen_best_f > best_fitness:
            best_fitness = gen_best_f
            best_ind = population[gen_best_idx][:]
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= NO_IMPROVE_LIMIT:
            break

    if best_ind is None:
        return {"assignments": [], "best_fitness": 0.0, "error": "Failed to find a solution."}

    # Decode assignments
    assignments = []
    for i, gene in enumerate(best_ind):
        task = tasks[i]
        choice = choices_list[i][gene]

        for j in range(task['duration']):
            slot_index = choice['start_slot_index'] + j
            slot_info = next((s for s in slots if s['day'] == choice['day'] and s['slot_index'] == slot_index), None)

            assignments.append({
                "day": choice['day'],
                "slot_index": slot_index,
                "slot_id": slot_info['id'] if slot_info else f"{choice['day']}-{slot_index}",
                "start_time": slot_info.get('start_time') if slot_info else None,
                "end_time": slot_info.get('end_time') if slot_info else None,
                "course": task['course_code'],
                "class_type": task['type'],
                "student_group": task['student_group'],
                "faculty": faculty_map.get(str(task['faculty_id']), task['faculty_id']),
                "room": choice['room_id']
            })

    return {"assignments": assignments, "best_fitness": float(best_fitness)}
