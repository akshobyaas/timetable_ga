# backend/ga_solver.py
"""
Optimized Genetic Algorithm timetable solver (MVP).

This version is tolerant to different CSV header names and ensures tasks
are created according to each course's required hours. It also normalizes
faculty IDs/names and slot ids so output assignments include both course
and faculty (and room if available).
"""

import random
import math
from collections import defaultdict

# GA parameters (tunable)
POPULATION_SIZE = 80
GENERATIONS = 150
TOURNAMENT_K = 3
CROSSOVER_RATE = 0.9
MUTATION_RATE = 0.08
ELITISM = 1
NO_IMPROVE_LIMIT = 30

# -------------------------
# Helpers for tolerant CSV fields
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

def _split_can_teach_field(raw):
    """Split a faculty can-teach string into list of normalized tokens (codes or subjects)."""
    if raw is None:
        return []
    if not isinstance(raw, str):
        return []
    # accept separators: '|', ';', ',', '/'
    parts = []
    for sep in ['|', ';', ',', '/']:
        if sep in raw:
            parts = [p.strip() for p in raw.split(sep) if p.strip()]
            break
    if not parts:
        parts = [raw.strip()] if raw.strip() else []
    # normalize to lower for matching
    return [p.lower() for p in parts]

# -------------------------
# Domain construction
# -------------------------
def _build_domain(courses_df, faculty_df, slots_df):
    """
    Build tasks (one per required hourly slot) and choices per task.
    This function is tolerant of CSV header variations and normalizes faculty/slot fields.
    Returns: tasks, choices_list
    """
    # Convert frames to lists of dicts
    slots = slots_df.to_dict(orient="records")
    # Choose slot fields tolerant to variations
    if slots:
        slot_cols = list(slots[0].keys())
    else:
        slot_cols = []

    slot_day_col = _pick_col(slot_cols, ['day', 'weekday'], default='day')
    slot_index_col = _pick_col(slot_cols, ['slot_index', 'slot', 'period'], default='slot_index')
    slot_id_col = _pick_col(slot_cols, ['id', 'slot_id'], default=None)
    slot_room_col = _pick_col(slot_cols, ['room', 'venue'], default=None)

    # normalize slot objects: ensure 'id', 'day', 'slot_index', 'room'
    normalized_slots = []
    for idx, s in enumerate(slots):
        day = s.get(slot_day_col) if slot_day_col in s else s.get('day')
        slot_index = s.get(slot_index_col, s.get('slot_index', s.get('period', 0)))
        try:
            slot_index = int(slot_index)
        except Exception:
            slot_index = idx  # fallback
        if slot_id_col and slot_id_col in s:
            sid = s.get(slot_id_col)
        else:
            # create a compact id
            sid = f"{str(day) or 'day'}-{slot_index}"
        room = None
        if slot_room_col and slot_room_col in s:
            room = s.get(slot_room_col)
        normalized_slots.append({
            'id': sid,
            'day': day,
            'slot_index': slot_index,
            'room': room
        })

    # Faculties: tolerant fields
    faculties = faculty_df.to_dict(orient="records") if not faculty_df.empty else []
    faculty_cols = list(faculties[0].keys()) if faculties else []
    faculty_id_col = _pick_col(faculty_cols, ['id', 'faculty_id', 'uid'], default=None)
    faculty_name_col = _pick_col(faculty_cols, ['name', 'faculty', 'faculty_name'], default=None)
    can_teach_col = _pick_col(faculty_cols, ['can_teach', 'preferred_subjects', 'subjects', 'can_teach_codes'], default=None)

    # if faculty entries lack explicit id, assign sequential ids
    normalized_faculties = []
    for i, f in enumerate(faculties):
        fid = f.get(faculty_id_col) if faculty_id_col and faculty_id_col in f else None
        if fid is None or str(fid).strip() == "":
            fid = f"F{i+1}"
        name = f.get(faculty_name_col) if faculty_name_col and faculty_name_col in f else f.get('faculty', f.get('name', f"Faculty {i+1}"))
        raw = f.get(can_teach_col) if can_teach_col and can_teach_col in f else f.get('can_teach') or f.get('preferred_subjects') or ''
        can_teach_list = _split_can_teach_field(raw)
        normalized_faculties.append({
            'id': fid,
            'name': name,
            '_can_teach_list': can_teach_list
        })

    # Courses: tolerant fields
    courses = courses_df.to_dict(orient="records") if not courses_df.empty else []
    course_cols = list(courses[0].keys()) if courses else []
    code_col = _pick_col(course_cols, ['code', 'course_code', 'id', 'course'], default=None)
    title_col = _pick_col(course_cols, ['title', 'subject', 'name', 'course_title'], default=None)
    hours_col = _pick_col(course_cols, ['weekly_hours', 'hours_per_week', 'hours', 'hrs'], default=None)

    tasks = []
    for c in courses:
        # extract course code
        if code_col and code_col in c:
            code = str(c.get(code_col))
        else:
            # try common alternatives
            # if there's a 'subject' or 'title' fallback to a generated code
            fallback = str(c.get(title_col) or c.get(title_col, '')).strip()
            code = fallback.replace(' ', '_')[:20] if fallback else f"C_{len(tasks)+1}"
        # title
        title = c.get(title_col) if title_col and title_col in c else c.get('subject', '')
        # hours
        try:
            hours = int(c.get(hours_col)) if hours_col and hours_col in c else int(c.get('hours_per_week', c.get('weekly_hours', 1)))
        except Exception:
            try:
                hours = int(float(c.get(hours_col, 1)))
            except Exception:
                hours = 1
        if hours <= 0:
            hours = 1
        # create a task entry repeated by hours
        for _ in range(hours):
            tasks.append({'code': code.strip(), 'title': title})

    # Build choices list: for each task, list feasible (slot, faculty) pairs
    choices_list = []
    for t in tasks:
        code_lower = (t['code'] or '').lower()
        choices = []
        for s in normalized_slots:
            for f in normalized_faculties:
                # if faculty has can_teach_list and course matches any entry, prefer it
                if f['_can_teach_list']:
                    # check code or title match
                    matches = False
                    # match if code (or code fragment) is listed
                    for token in f['_can_teach_list']:
                        if token == code_lower or token in code_lower:
                            matches = True
                            break
                        # also match by title words or subject
                        title_low = (t.get('title') or '').lower()
                        if token == title_low or token in title_low:
                            matches = True
                            break
                    if matches:
                        choices.append({
                            'slot_id': s['id'],
                            'day': s['day'],
                            'slot_index': int(s['slot_index']),
                            'faculty_id': f['id'],
                            'faculty_name': f['name'],
                            'room': s.get('room')
                        })
                else:
                    # will add fallback later
                    pass
        # fallback: if no choices were created (no faculty matched), allow any faculty on any slot
        if not choices:
            for s in normalized_slots:
                for f in normalized_faculties:
                    choices.append({
                        'slot_id': s['id'],
                        'day': s['day'],
                        'slot_index': int(s['slot_index']),
                        'faculty_id': f['id'],
                        'faculty_name': f['name'],
                        'room': s.get('room')
                    })
        choices_list.append(choices)

    return tasks, choices_list

# -------------------------
# Precompute structures
# -------------------------
def _precompute_choice_arrays(choices_list):
    choice_faculty_ids = []
    choice_slot_ids = []
    choice_rooms = []
    for choices in choices_list:
        facs = []
        slots = []
        rooms = []
        for ch in choices:
            facs.append(ch.get('faculty_id'))
            slots.append(ch.get('slot_id'))
            rooms.append(ch.get('room'))
        choice_faculty_ids.append(facs)
        choice_slot_ids.append(slots)
        choice_rooms.append(rooms)
    return choice_faculty_ids, choice_slot_ids, choice_rooms

# -------------------------
# Individual ops
# -------------------------
def _random_individual(choices_list):
    return [random.randrange(len(choices)) for choices in choices_list]

def _decode_individual(individual, tasks, choices_list):
    assignments = []
    for i, gene in enumerate(individual):
        choice = choices_list[i][gene]
        assignments.append({
            'day': choice['day'],
            'slot_index': int(choice['slot_index']),
            'slot_id': choice['slot_id'],
            'course': tasks[i]['code'],
            'faculty_id': choice['faculty_id'],
            'faculty': choice.get('faculty_name'),
            'room': choice.get('room')
        })
    return assignments

# -------------------------
# Fitness (optimized)
# -------------------------
def _fitness_of_individual(individual, choice_faculty_ids, choice_slot_ids):
    counter = {}
    for i, gene in enumerate(individual):
        try:
            faculty_id = choice_faculty_ids[i][gene]
            slot_id = choice_slot_ids[i][gene]
        except Exception:
            continue
        key = (faculty_id, slot_id)
        counter[key] = counter.get(key, 0) + 1

    penalty = 0
    for cnt in counter.values():
        if cnt > 1:
            penalty += (cnt - 1) * 1000

    base = 100000
    fitness = base - penalty
    return float(max(0, fitness))

# -------------------------
# Crossover / mutation / selection
# -------------------------
def _crossover(a, b):
    if len(a) < 2:
        return a[:], b[:]
    point = random.randrange(1, len(a))
    child1 = a[:point] + b[point:]
    child2 = b[:point] + a[point:]
    return child1, child2

def _mutate(individual, choices_list, mutation_rate=MUTATION_RATE):
    for i in range(len(individual)):
        if random.random() < mutation_rate:
            individual[i] = random.randrange(len(choices_list[i]))

def _evolve_population(population, fitnesses, choices_list):
    n = len(population)
    new_pop = []
    sorted_idx = sorted(range(n), key=lambda i: fitnesses[i], reverse=True)
    for i in sorted_idx[:ELITISM]:
        new_pop.append(population[i][:])

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
    tasks, choices_list = _build_domain(courses_df, faculty_df, slots_df)
    if not tasks:
        return {"assignments": [], "best_fitness": 0.0, "error": "No tasks found (check courses.csv)"}

    for i, choices in enumerate(choices_list):
        if not choices:
            return {"assignments": [], "best_fitness": 0.0, "error": f"No choices for task {i}"}

    choice_faculty_ids, choice_slot_ids, choice_rooms = _precompute_choice_arrays(choices_list)

    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]
    fitnesses = [_fitness_of_individual(ind, choice_faculty_ids, choice_slot_ids) for ind in population]

    best_ind = None
    best_fitness = -math.inf
    no_improve_counter = 0

    for idx, f in enumerate(fitnesses):
        if f > best_fitness:
            best_fitness = f
            best_ind = population[idx][:]

    if best_fitness < 100000:
        for gen in range(GENERATIONS):
            population = _evolve_population(population, fitnesses, choices_list)
            fitnesses = [_fitness_of_individual(ind, choice_faculty_ids, choice_slot_ids) for ind in population]
            gen_best_idx = max(range(len(population)), key=lambda i: fitnesses[i])
            gen_best_f = fitnesses[gen_best_idx]
            if gen_best_f > best_fitness:
                best_fitness = gen_best_f
                best_ind = population[gen_best_idx][:]
                no_improve_counter = 0
            else:
                no_improve_counter += 1
            if best_fitness >= 100000:
                break
            if no_improve_counter >= NO_IMPROVE_LIMIT:
                break

    if best_ind is None:
        best_ind = _random_individual(choices_list)
        best_fitness = _fitness_of_individual(best_ind, choice_faculty_ids, choice_slot_ids)

    assignments = _decode_individual(best_ind, tasks, choices_list)

    out_assignments = []
    for a in assignments:
        out_assignments.append({
            "day": a.get("day"),
            "slot_index": int(a.get("slot_index", 0)),
            "course": a.get("course"),
            "faculty": a.get("faculty"),
            "room": a.get("room")
        })

    return {"assignments": out_assignments, "best_fitness": float(best_fitness)}
