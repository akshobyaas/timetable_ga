from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd
import math, random
from fastapi.responses import JSONResponse
from backend.ga_solver import generate_timetable
from fastapi.responses import Response

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


# add this before your @app.post("/generate") handler
@app.options("/generate")
async def generate_options():
    # return the headers browsers expect for preflight
    headers = {
        "Access-Control-Allow-Origin": "https://tt-generator-ga.netlify.app",
        "Access-Control-Allow-Methods": "POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
        "Access-Control-Allow-Credentials": "true",
    }
    return Response(status_code=200, headers=headers)


import traceback
from fastapi.responses import JSONResponse, Response

# keep your existing imports and CORS middleware above this

@app.post("/generate")
async def generate(
    courses: UploadFile = File(...),
    faculty: UploadFile = File(...),
    slots: UploadFile = File(...),
    runs: int = Form(3),
    seed: int | None = Form(None)
):
    try:
        # Parse CSVs (explicitly catch parse errors separately if desired)
        try:
            courses_df = pd.read_csv(courses.file)
        except Exception as e:
            raise ValueError(f"Failed to parse courses CSV: {e}")

        try:
            faculty_df = pd.read_csv(faculty.file)
        except Exception as e:
            raise ValueError(f"Failed to parse faculty CSV: {e}")

        try:
            slots_df = pd.read_csv(slots.file)
        except Exception as e:
            raise ValueError(f"Failed to parse slots CSV: {e}")

        # run GA runs (your existing logic)
        best_overall = None
        best_fit = -float("inf")
        seeds_used = []
        runs = max(1, int(runs))

        for i in range(runs):
            if seed is not None:
                s = int(seed) + i
            else:
                s = random.randrange(1 << 30)
            seeds_used.append(s)
            random.seed(s)
            result = generate_timetable(courses_df, faculty_df, slots_df)
            f = float(result.get("best_fitness", 0.0)) if isinstance(result, dict) else 0.0
            print(f"[MULTI-RUN] trial {i+1}/{runs} seed={s} fitness={f}")
            if f > best_fit:
                best_fit = f
                best_overall = result.copy() if isinstance(result, dict) else {"assignments": result}
                best_overall["_best_trial_index"] = i
                best_overall["_best_seed"] = s
                best_overall["_best_fitness"] = f

        if best_overall is None:
            best_overall = {"assignments": [], "best_fitness": 0.0}
        best_overall["_runs_requested"] = runs
        best_overall["_seeds_tried"] = seeds_used

        return JSONResponse(content=best_overall)

    except Exception as exc:
        # Print full traceback to server logs (Render Console)
        tb = traceback.format_exc()
        print("=== /generate error ===")
        print(tb)
        print("=== end traceback ===")

        # Return JSON error with CORS headers so browser will show it
        headers = {
            "Access-Control-Allow-Origin": "https://tt-generator-ga.netlify.app",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept",
            "Access-Control-Allow-Credentials": "true",
        }
        return JSONResponse(
            status_code=500,
            content={"error": str(exc), "traceback": tb.splitlines()[-30:]},  # last 30 lines for brevity
            headers=headers
        )
