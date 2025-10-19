# backend/app.py
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
import pandas as pd
from backend.ga_solver import generate_timetable   # import the stub we created

# Add CORS middleware so the frontend can call the API (local dev)
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Timetable GA (MVP)")

# Allow everything for local development only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # allow all origins (safe for local dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def home():
    return {"message": "Timetable Generator API is running!"}

@app.post("/generate")
async def generate(
    courses: UploadFile = File(...),
    faculty: UploadFile = File(...),
    slots: UploadFile = File(...)
):
    # Read uploaded CSV files into pandas DataFrames
    try:
        courses_df = pd.read_csv(courses.file)
        faculty_df = pd.read_csv(faculty.file)
        slots_df = pd.read_csv(slots.file)
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": "Failed to parse CSVs", "detail": str(e)})

    # Call the generator (currently the random stub)
    result = generate_timetable(courses_df, faculty_df, slots_df)
    return JSONResponse(content=result)
