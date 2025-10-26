from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import math, random
from fastapi.responses import JSONResponse
from backend.ga_solver import generate_timetable

app = FastAPI(title="Timetable GA Backend")

# ✅ Proper CORS setup
origins = [
    "https://tt-generator-ga.netlify.app",  # your frontend Netlify domain
    "http://localhost:5173",  # optional for local dev
    "http://127.0.0.1:5173"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],  # allows OPTIONS automatically
    allow_headers=["*"]
)



@app.get("/")
def home():
    return {"message": "Timetable Generator API is running!"}

@app.post("/generate")
async def generate(
    courses: UploadFile = File(...),
    faculty: UploadFile = File(...),
    slots: UploadFile = File(...),
    runs: int = Form(3),           # how many independent GA trials to run (default 3)
    seed: int | None = Form(None)  # optional base seed for reproducible trials
):
    # Parse CSVs
    try:
        courses_df = pd.read_csv(courses.file)
        faculty_df = pd.read_csv(faculty.file)
        slots_df = pd.read_csv(slots.file)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Failed to parse CSVs", "detail": str(e)})

    # Run GA multiple times and pick best result
    best_overall = None
    best_fit = -math.inf
    seeds_used = []

    # ensure at least 1 run
    runs = max(1, int(runs))

    for i in range(runs):
        # choose seed for this trial
        if seed is not None:
            s = int(seed) + i
        else:
            # pick a random seed for each trial
            s = random.randrange(1 << 30)
        seeds_used.append(s)

        # set RNG seed so the GA is reproducible for this trial
        random.seed(s)

        # call the GA (it uses python's random module internally)
        result = generate_timetable(courses_df, faculty_df, slots_df)

        # read fitness (fallback to 0.0 if not provided)
        try:
            f = float(result.get("best_fitness", 0.0))
        except Exception:
            f = 0.0

        # log to server console for visibility
        print(f"[MULTI-RUN] trial {i+1}/{runs} seed={s} fitness={f}")

        # keep best
        if f > best_fit:
            best_fit = f
            best_overall = result.copy() if isinstance(result, dict) else {"assignments": result}
            # annotate which trial & seed produced the best
            best_overall["_best_trial_index"] = i
            best_overall["_best_seed"] = s
            best_overall["_best_fitness"] = f

    # add metadata for response
    if best_overall is None:
        best_overall = {"assignments": [], "best_fitness": 0.0}
    best_overall["_runs_requested"] = runs
    best_overall["_seeds_tried"] = seeds_used

    return JSONResponse(content=best_overall)
