<<<<<<< HEAD
# smart-corridor-attendance
Smart Corridor is a local laptop-based face recognition attendance system for schools. It uses Python, OpenCV, face_recognition, SQLite, and a Streamlit dashboard to register students, recognize faces through a webcam, and manage attendance with safe manual review for unknown faces.
=======
# Smart Corridor — Face Recognition Attendance System

Smart Corridor is a local, laptop-based biometric attendance MVP for one school entrance. A React dashboard captures webcam frames, a Python API evaluates face matches, and SQLite stores attendance locally.

## Features

- Student registration with name, roll number, class/division, and webcam face capture.
- Local face-embedding storage and safe matching.
- One live laptop-webcam recognition flow.
- Attendance once per student per day, with Present or Late status.
- Configurable school start time and optional grace period; late records include minutes late.
- Unknown / Manual Review for unsafe matches, with no automatic attendance.
- Dashboard, attendance search, and unknown-event review.

## Technology

- React and Vite
- Python and FastAPI
- OpenCV and face_recognition
- SQLite

## Run the backend

From `backend`, run `..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`.

### Attendance timing

The default school start time is `08:00`. A student recognized after that time is marked `Late`; the stored `late_minutes` value shows how many minutes after the start time they arrived. Set `SMART_CORRIDOR_SCHOOL_START` and `SMART_CORRIDOR_LATE_GRACE_MINUTES` before starting the backend when your school schedule changes.

## Run the frontend

From `frontend`, run `npm.cmd run dev`, then open `http://localhost:5173`.

## Important privacy note

Face recognition is probabilistic; it does not claim perfect accuracy. The project uses a conservative threshold and never marks attendance for an unsafe match. The database and unknown snapshots are ignored by Git. Do not upload real student biometric data to a public repository.
>>>>>>> 64c012a (Initial commit for Smart Corridor attendance system)
