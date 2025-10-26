# 🧠 Automated Timetable Scheduler (GA-Based)

A web application that automatically generates optimized class timetables using a **Genetic Algorithm (GA)**.
It allows users to upload course, faculty, and slot CSV files — or manually enter data — and generates a clash-free, balanced timetable instantly.

---

## 🚀 Live Demo

| Component                   | Platform                                           | Link                                                                 |
| --------------------------- | -------------------------------------------------- | -------------------------------------------------------------------- |
| 🖥️ **Frontend (Netlify)**  | Static web UI built with Tailwind CSS & Vanilla JS | [🔗 View Frontend on Netlify](https://your-netlify-link.netlify.app) |
| ⚙️ **Backend API (Render)** | FastAPI service running GA solver                  | [🔗 View Backend on Render](https://your-render-link.onrender.com)   |

---

## 🧩 Project Architecture

```
frontend/
 ├─ index.html          → Main UI
 ├─ src/main.js         → DOM logic, file upload, manual entry, timetable render
 ├─ src/styles.css      → Tailwind source
 ├─ dist/styles.css     → Compiled Tailwind bundle
 ├─ config.js           → API_BASE for backend
 └─ tailwind.config.js  → Tailwind build setup

backend/
 ├─ app.py              → FastAPI app with /generate endpoint
 ├─ ga_solver.py        → Genetic Algorithm timetable engine
 └─ requirements.txt    → Backend dependencies
```

---

## 🧬 How It Works

### 1. Input Data

The system accepts three CSV files:

* **Courses** → `code`, `title`, `weekly_hours`
* **Faculty** → `id`, `name`, `can_teach` (pipe-separated course codes)
* **Slots** → `id`, `day`, `slot_index`

Or, users can manually enter data in the UI.

### 2. Genetic Algorithm (GA) Optimization

Each possible timetable is treated as an *individual* in a population.
The GA performs:

* **Selection** → Tournament selection
* **Crossover** → Single-point crossover
* **Mutation** → Random slot/faculty changes
* **Fitness Evaluation** → Penalizes clashes and over-allocations

The process repeats until convergence or max generations.
The best solution (highest fitness) becomes the final timetable.

### 3. Output

* A neatly formatted timetable table (rendered on the page).
* Download options:

  * **CSV**
  * **PNG image** (via `html2canvas`)

---

## 🛠️ Tech Stack

| Area          | Technology                                                         |
| ------------- | ------------------------------------------------------------------ |
| **Frontend**  | HTML5, Tailwind CSS, Vanilla JavaScript                            |
| **Backend**   | Python 3.10+, FastAPI, Pandas                                      |
| **Algorithm** | Genetic Algorithm (custom implementation)                          |
| **Database**  | MongoDB *(currently not in use — optional for future persistence)* |
| **Hosting**   | Netlify (frontend) + Render (backend API)                          |

---

## 🧑‍💻 Local Development Setup

### Prerequisites

* Python 3.10 +
* Node.js + npm
* (Optional) MongoDB if you plan to enable persistence

### 1️⃣ Clone the repository

```bash
git clone https://github.com/akshobyaas/timetable_ga.git
cd timetable_ga
```

### 2️⃣ Backend setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app:app --reload
```

Backend runs at `http://127.0.0.1:8000`

### 3️⃣ Frontend setup

```bash
cd frontend
npm install
npm run build:css    # or npm run watch:css
```

Open `index.html` in your browser.
(If you want to point the frontend to your local backend, edit `config.js`:

````js
window.__ENV = { API_BASE: "http://127.0.0.1:8000" };
```)

---

## 🧾 Example CSV Formats

### 🧱 courses.csv
```csv
code,title,weekly_hours
CS101,Data Structures,3
CS102,Database Systems,3
CS103,Operating Systems,3
````

### 👨‍🏫 faculty.csv

```csv
id,name,can_teach
f1,Prof Rao,CS101|CS103
f2,Prof Patil,CS102
```

### ⏰ slots.csv

```csv
id,day,slot_index
mon-0,Mon,0
mon-1,Mon,1
tue-0,Tue,0
tue-1,Tue,1
```

---

## 📸 Screenshots (add later)

| Upload Mode              | Manual Mode              | Generated Timetable      |
| ------------------------ | ------------------------ | ------------------------ |
| *(add screenshots here)* | *(add screenshots here)* | *(add screenshots here)* |

---

## ⚙️ Environment Variables

| Variable                 | Description                                    | Example                                                 |
| ------------------------ | ---------------------------------------------- | ------------------------------------------------------- |
| `API_BASE`               | Backend URL for frontend requests              | `https://timetable-ga-backend.onrender.com`             |
| `MONGO_URI` *(optional)* | MongoDB connection string (for future storage) | `mongodb+srv://user:pass@cluster.mongodb.net/timetable` |

---

## 🧠 Future Enhancements

* ✅ Light-only UI (fixed)
* 🗂 Save generated timetables to MongoDB
* 📊 Display GA convergence graph (fitness vs. generation)
* 🧮 Add constraints like teacher availability or classroom limits
* 🌙 Re-enable optional dark mode toggle
* 📅 Export timetables to PDF

---

## 👨‍💻 Authors & Credits

* **Akshobyaa S** — Developer & Project Owner
* **Bavi (you)** — Frontend & Deployment optimization
* Built using [FastAPI](https://fastapi.tiangolo.com/) and [Tailwind CSS](https://tailwindcss.com/).

---

## 🧾 License

This project is licensed under the **MIT License** — you can freely use and modify it with attribution.

---

## ⭐ Support

If this project helped you, please **star the repo** 🌟 on GitHub!
Pull requests and improvements are always welcome.

---

## 🧩 Summary

| Feature             | Status             |
| ------------------- | ------------------ |
| Upload CSVs         | ✅                  |
| Manual entry        | ✅                  |
| Genetic Algorithm   | ✅                  |
| CSV & PNG download  | ✅                  |
| MongoDB persistence | ⚙️ Planned         |
| Dark/Light mode     | ✅ Light-only fixed |
| Deployments         | ✅ Render + Netlify |

---


