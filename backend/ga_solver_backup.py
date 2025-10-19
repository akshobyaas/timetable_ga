# backend/ga_solver.py
import random

def generate_timetable(courses_df, faculty_df, slots_df):
    """
    Very small starter: random simple assignment so you can test the pipeline.
    Expects pandas.DataFrame objects for courses, faculty, slots.
    """
    assignments = []

    # convert slots to list of dicts
    slots = slots_df.to_dict(orient="records")

    for _, course in courses_df.iterrows():
        hours = int(course["weekly_hours"])
        # find faculty rows that can teach this course (string contains course code)
        possible_faculty = faculty_df[faculty_df["can_teach"].str.contains(str(course["code"]), na=False)]

        for _ in range(hours):
            slot = random.choice(slots)
            if not possible_faculty.empty:
                faculty = possible_faculty.sample(1).iloc[0]
            else:
                faculty = faculty_df.sample(1).iloc[0]
            assignments.append({
                "day": slot.get("day"),
                "slot_index": int(slot.get("slot_index", 0)),
                "course": course.get("code"),
                "faculty": faculty.get("name")
            })

    return {"assignments": assignments}

