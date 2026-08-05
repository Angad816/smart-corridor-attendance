"""FastAPI entry point for the Smart Corridor local backend."""

from contextlib import asynccontextmanager
from datetime import datetime

import cv2
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import ALLOWED_FRONTEND_ORIGINS, ALLOWED_FRONTEND_ORIGIN_REGEX, LATE_GRACE_MINUTES, MAX_IMAGE_DATA_LENGTH, SCHOOL_START_TIME, UNKNOWN_SNAPSHOT_DIRECTORY
from .database import (
    create_student, create_unknown_event, get_attendance, get_dashboard_summary,
    get_registered_embeddings, initialize_database, list_students, list_unknown_events,
    mark_attendance, recent_unknown_exists,
)
from .face_engine import FaceValidationError, decode_camera_image, encode_for_storage, encode_single_face, find_safe_match


class StudentRegistration(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    roll_number: str = Field(min_length=1, max_length=30)
    class_division: str = Field(min_length=1, max_length=50)
    image_data: str = Field(min_length=30)


class CameraFrame(BaseModel):
    image_data: str = Field(min_length=30)


def _validate_image_size(image_data: str) -> None:
    # Base64 is intentionally capped before decoding to avoid memory abuse on this local API.
    if len(image_data) > MAX_IMAGE_DATA_LENGTH:
        raise HTTPException(status_code=413, detail="The camera image is too large. Please try again.")


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(
    title="Smart Corridor API",
    version="0.1.0",
    description="Local API for the Face Recognition Attendance System.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_FRONTEND_ORIGINS,
    allow_origin_regex=ALLOWED_FRONTEND_ORIGIN_REGEX,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_IMAGE_DATA_LENGTH + 200_000:
        return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response

UNKNOWN_SNAPSHOT_DIRECTORY.mkdir(parents=True, exist_ok=True)
app.mount("/snapshots", StaticFiles(directory=str(UNKNOWN_SNAPSHOT_DIRECTORY)), name="snapshots")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    return {"status": "ok", "service": "smart-corridor-backend"}


@app.get("/api/dashboard-summary")
def dashboard_summary() -> dict[str, int | str]:
    return {**get_dashboard_summary(), "school_start_time": SCHOOL_START_TIME, "late_grace_minutes": LATE_GRACE_MINUTES}


@app.get("/api/students")
def students() -> list[dict]:
    return list_students()


@app.post("/api/students", status_code=201)
def register_student(payload: StudentRegistration) -> dict:
    try:
        _validate_image_size(payload.image_data)
        _, rgb_image = decode_camera_image(payload.image_data)
        embedding = encode_single_face(rgb_image)
        return create_student(
            payload.name.strip(), payload.roll_number.strip(), payload.class_division.strip(), encode_for_storage(embedding)
        )
    except FaceValidationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        if "UNIQUE constraint failed: students.roll_number" in str(error):
            raise HTTPException(status_code=409, detail="That roll number is already registered.") from error
        raise


@app.post("/api/recognition/identify")
def identify_face(payload: CameraFrame) -> dict:
    try:
        _validate_image_size(payload.image_data)
        bgr_image, rgb_image = decode_camera_image(payload.image_data)
        encoding = encode_single_face(rgb_image)
    except FaceValidationError as error:
        return _unknown_result(str(error), None)

    match = find_safe_match(encoding, get_registered_embeddings())
    if match.student is None:
        return _unknown_result("No safe face match found.", bgr_image, match.distance)

    attendance = mark_attendance(match.student["student_id"])
    return {
        "recognized": True,
        "name": match.student["name"],
        "roll_number": match.student["roll_number"],
        "class_division": match.student["class_division"],
        "match_distance": round(match.distance, 3),
        **attendance,
    }


def _unknown_result(reason: str, bgr_image=None, distance: float | None = None) -> dict:
    if not recent_unknown_exists(reason):
        snapshot_path = None
        if bgr_image is not None:
            UNKNOWN_SNAPSHOT_DIRECTORY.mkdir(parents=True, exist_ok=True)
            filename = f"unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            file_path = UNKNOWN_SNAPSHOT_DIRECTORY / filename
            cv2.imwrite(str(file_path), bgr_image)
            snapshot_path = filename
        create_unknown_event(reason, snapshot_path)
    return {"recognized": False, "reason": reason, "match_distance": round(distance, 3) if distance is not None else None}


@app.get("/api/attendance")
def attendance(date: str | None = None, query: str = "") -> list[dict]:
    return get_attendance(date, query)


@app.get("/api/unknown-events")
def unknown_events() -> list[dict]:
    return list_unknown_events()
