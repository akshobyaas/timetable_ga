# backend/ga_solver.py
"""
Genetic Algorithm timetable solver (patched).

Key features:
 - tolerant CSV field detection
 - normalized slot ids and human-readable slot labels (start-end)
 - exact-token can_teach matching
 - penalizes slot collisions (any course in same slot) and faculty double-booking
 - applies per-course assignment-count penalty vs requested weekly_hours
 - always runs evolution loop (early-stop via NO_IMPROVE_LIMIT)
"""

import random
import math
import re
from collections import defaultdict

# GA parameters (tunable)
POPULATION_SIZE = 80
GENERATIONS = 150
TOURNAMENT_K = 3
CROSSOVER_RATE = 0.9
MUTATION_RATE = 0.08
ELITISM = 1
NO_IMPROVE_LIMIT = 30

# Penalty weights (tunable)
PENALTY_SLOT_COLLISION = 2000      # heavy: multiple courses in same slot
PENALTY_FACULTY_DOUBLE = 1000      # faculty double-booked same slot
PENALTY_COURSE_MISMATCH = 1500     # missing/extra assignment per course

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
    """Split a faculty can-teach string into list of normalized exact tokens."""
    if raw is None or not isinstance(raw, str):
        return []
    parts = re.split(r'[|,;/]+', raw)
    tokens = [p.strip().lower() for p in parts if p.strip()]
    return tokens

# -------------------------
# Domain construction
# -------------------------
def _build_domain(courses_df, faculty_df, slots_df):
    """
    Build tasks (one per required hourly slot) and choices per task.
    Returns: tasks, choices_list, course_weekly
    Each choice includes: slot_id, slot_index, day, faculty_id, faculty_name, room, slot_label, start, end
    """
    slots = slots_df.to_dict(orient="records") if not slots_df.empty else []
    slot_cols = list(slots[0].keys()) if slots else []

    slot_day_col = _pick_col(slot_cols, ['day', 'weekday'], default='day')
    slot_index_col = _pick_col(slot_cols, ['slot_index', 'slot', 'period', 'index'], default='slot_index')
    slot_id_col = _pick_col(slot_cols, ['id', 'slot_id'], default=None)
    slot_room_col = _pick_col(slot_cols, ['room', 'venue'], default=None)
    slot_start_col = _pick_col(slot_cols, ['start_time', 'start', 'from'], default=None)
    slot_end_col = _pick_col(slot_cols, ['end_time', 'end', 'to'], default=None)

    normalized_slots = []
    for idx, s in enumerate(slots):
        # day
        day = None
        if slot_day_col and slot_day_col in s:
            day = s.get(slot_day_col)
        else:
            day = s.get('day')
        # index
        slot_index = s.get(slot_index_col, s.get('slot_index', s.get('period', idx)))
        try:
            slot_index = int(slot_index)
        except Exception:
            slot_index = idx
        # stable normalized day string for id
        day_str = str(day).strip().lower() if day is not None else "day"
        # slot id
        if slot_id_col and slot_id_col in s and s.get(slot_id_col):
            sid_raw = str(s.get(slot_id_col)).strip()
            sid = sid_raw if sid_raw else f"{day_str}-{slot_index}"
        else:
            sid = f"{day_str}-{slot_index}"
        # room
        room = s.get(slot_room_col) if slot_room_col and slot_room_col in s else None
        # start/end/label
        start = s.get(slot_start_col) if slot_start_col and slot_start_col in s else (s.get('start') if 'start' in s else None)
        end = s.get(slot_end_col) if slot_end_col and slot_end_col in s else (s.get('end') if 'end' in s else None)
        start_str = str(start).strip() if start is not None else None
        end_str = str(end).strip() if end is not None else None
        label = f"{start_str}-{end_str}" if start_str and end_str else sid
        normalized_slots.append({
            'id': sid,
            'day': str(day).strip() if day is not None else None,
            'slot_index': slot_index,
            'room': room,
            'start': start_str,
            'end': end_str,
            'label': label
        })

    # Faculties
    faculties = faculty_df.to_dict(orient="records") if not faculty_df.empty else []
    faculty_cols = list(faculties[0].keys()) if faculties else []
    faculty_id_col = _pick_col(faculty_cols, ['id', 'faculty_id', 'uid'], default=None)
    faculty_name_col = _pick_col(faculty_cols, ['name', 'faculty', 'faculty_name'], default=None)
    can_teach_col = _pick_col(faculty_cols, ['can_teach', 'preferred_subjects', 'subjects', 'can_teach_codes'], default=None)

    normalized_faculties = []
    for i, f in enumerate(faculties):
        fid = f.get(faculty_id_col) if faculty_id_col and faculty_id_col in f else None
        if fid is None or str(fid).strip() == "":
            fid = f"F{i+1}"
        name = f.get(faculty_name_col) if faculty_name_col and faculty_name_col in f else f.get('name', f.get('faculty', f"Faculty {i+1}"))
        raw = f.get(can_teach_col) if can_teach_col and can_teach_col in f else f.get('can_teach') or ''
        can_teach_list = _split_can_teach_field(raw)
        normalized_faculties.append({
            'id': str(fid).strip(),
            'name': str(name).strip() if name is not None else name,
            '_can_teach_list': can_teach_list
        })

    # Courses
    courses = courses_df.to_dict(orient="records") if not courses_df.empty else []
    course_cols = list(courses[0].keys()) if courses else []
    code_col = _pick_col(course_cols, ['code', 'course_code', 'id', 'course'], default=None)
    title_col = _pick_col(course_cols, ['title', 'subject', 'name', 'course_title'], default=None)
    hours_col = _pick_col(course_cols, ['weekly_hours', 'hours_per_week', 'hours', 'hrs'], default=None)

    tasks = []
    course_weekly = {}
    for c in courses:
        if code_col and code_col in c and str(c.get(code_col)).strip():
            code = str(c.get(code_col)).strip()
        else:
            fallback = str(c.get(title_col) or '').strip()
            code = fallback.replace(' ', '_')[:20] if fallback else f"C_{len(tasks)+1}"
        title = c.get(title_col) if title_col and title_col in c else c.get('subject', '')
        try:
            hours = int(c.get(hours_col)) if hours_col and hours_col in c else int(c.get('hours_per_week', c.get('weekly_hours', 1)))
        except Exception:
            try:
                hours = int(float(c.get(hours_col, 1)))
            except Exception:
                hours = 1
        if hours <= 0:
            hours = 1
        course_weekly[code.strip()] = hours
        for _ in range(hours):
            tasks.append({'code': code.strip(), 'title': title})

    # Build choices list
    choices_list = []
    for t in tasks:
        code_lower = (t['code'] or '').lower()
        title_low = (t.get('title') or '').lower()
        title_words = [w.strip() for w in re.split(r'\W+', title_low) if w.strip()]
        choices = []
        for s in normalized_slots:
            for f in normalized_faculties:
                matches = False
                if f['_can_teach_list']:
                    for token in f['_can_teach_list']:
                        if token == code_lower or token in title_words:
                            matches = True
                            break
                if matches:
                    choices.append({
                        'slot_id': s['id'],
                        'slot_label': s['label'],
                        'day': s['day'],
                        'slot_index': int(s['slot_index']),
                        'faculty_id': f['id'],
                        'faculty_name': f['name'],
                        'room': s.get('room'),
                        'start': s.get('start'),
                        'end': s.get('end')
                    })
        # fallback: allow any faculty on any slot (if no matches)
        if not choices:
            for s in normalized_slots:
                for f in normalized_faculties:
                    choices.append({
                        'slot_id': s['id'],
                        'slot_label': s['label'],
                        'day': s['day'],
                        'slot_index': int(s['slot_index']),
                        'faculty_id': f['id'],
                        'faculty_name': f['name'],
                        'room': s.get('room'),
                        'start': s.get('start'),
                        'end': s.get('end')
                    })
        choices_list.append(choices)

    return tasks, choices_list, course_weekly

# -------------------------
# Precompute structures
# -------------------------
def _precompute_choice_arrays(choices_list):
    choice_faculty_ids = []
    choice_slot_ids = []
    choice_slot_labels = []
    choice_rooms = []
    for choices in choices_list:
        facs = []
        slots = []
        labels = []
        rooms = []
        for ch in choices:
            facs.append(ch.get('faculty_id'))
            slots.append(ch.get('slot_id'))
            labels.append(ch.get('slot_label'))
            rooms.append(ch.get('room'))
        choice_faculty_ids.append(facs)
        choice_slot_ids.append(slots)
        choice_slot_labels.append(labels)
        choice_rooms.append(rooms)
    return choice_faculty_ids, choice_slot_ids, choice_slot_labels, choice_rooms

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
            'day': choice.get('day'),
            'slot_index': int(choice.get('slot_index')),
            'slot_id': choice.get('slot_id'),
            'slot_label': choice.get('slot_label'),
            'start': choice.get('start'),
            'end': choice.get('end'),
            'course': tasks[i]['code'],
            'faculty_id': choice.get('faculty_id'),
            'faculty': choice.get('faculty_name'),
            'room': choice.get('room')
        })
    return assignments

# -------------------------
# Fitness
# -------------------------
def _fitness_of_individual(individual, choice_faculty_ids, choice_slot_ids):
    """
    Penalize:
      - multiple assignments to the same slot (slot collision)
      - same faculty assigned to >1 task in same slot (double-booking)
    """
    slot_counter = {}
    faculty_slot_counter = {}

    for i, gene in enumerate(individual):
        try:
            faculty_id = choice_faculty_ids[i][gene]
            slot_id = choice_slot_ids[i][gene]
        except Exception:
            continue

        slot_counter[slot_id] = slot_counter.get(slot_id, 0) + 1
        key = (faculty_id, slot_id)
        faculty_slot_counter[key] = faculty_slot_counter.get(key, 0) + 1

    penalty = 0
    for cnt in slot_counter.values():
        if cnt > 1:
            penalty += (cnt - 1) * PENALTY_SLOT_COLLISION
    for cnt in faculty_slot_counter.values():
        if cnt > 1:
            penalty += (cnt - 1) * PENALTY_FACULTY_DOUBLE

    base = 100000.0
    fitness = base - penalty
    return float(max(0.0, fitness))

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
    tasks, choices_list, course_weekly = _build_domain(courses_df, faculty_df, slots_df)
    if not tasks:
        return {"assignments": [], "best_fitness": 0.0, "error": "No tasks found (check courses.csv)"}

    for i, choices in enumerate(choices_list):
        if not choices:
            return {"assignments": [], "best_fitness": 0.0, "error": f"No choices for task {i}"}

    choice_faculty_ids, choice_slot_ids, choice_slot_labels, choice_rooms = _precompute_choice_arrays(choices_list)

    population = [_random_individual(choices_list) for _ in range(POPULATION_SIZE)]
    fitnesses = [_fitness_of_individual(ind, choice_faculty_ids, choice_slot_ids) for ind in population]

    best_ind = None
    best_fitness = -math.inf
    no_improve_counter = 0

    for idx, f in enumerate(fitnesses):
        if f > best_fitness:
            best_fitness = f
            best_ind = population[idx][:]

    # always evolve (early-stop via NO_IMPROVE_LIMIT)
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
        if no_improve_counter >= NO_IMPROVE_LIMIT:
            break

    if best_ind is None:
        best_ind = _random_individual(choices_list)
        best_fitness = _fitness_of_individual(best_ind, choice_faculty_ids, choice_slot_ids)

    # decode best individual
    assignments = _decode_individual(best_ind, tasks, choices_list)

    # compute per-course counts and apply course-count penalty
    course_counts = {}
    for a in assignments:
        code = a.get('course')
        course_counts[code] = course_counts.get(code, 0) + 1

    penalty_course = 0
    for code, req in course_weekly.items():
        got = course_counts.get(code, 0)
        if got != req:
            penalty_course += abs(req - got) * PENALTY_COURSE_MISMATCH

    adjusted_best = float(max(0.0, best_fitness - penalty_course))

    # prepare output assignments (include slot label/start/end)
    out_assignments = []
    for a in assignments:
        out_assignments.append({
            "day": a.get("day"),
            "slot_index": int(a.get("slot_index", 0)),
            "slot_id": a.get("slot_id"),
            "slot_label": a.get("slot_label"),
            "start": a.get("start"),
            "end": a.get("end"),
            "course": a.get("course"),
            "faculty": a.get("faculty"),
            "room": a.get("room")
        })

    return {"assignments": out_assignments, "best_fitness": float(adjusted_best)}
