"""SQLite connection and schema setup for Smart Corridor."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

from .config import DATA_DIRECTORY, DATABASE_PATH, LATE_GRACE_MINUTES, SCHOOL_START_TIME, UNKNOWN_EVENT_COOLDOWN_SECONDS


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a database connection with foreign-key protection enabled."""
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database() -> None:
    """Create all Version 1 tables if they do not already exist."""
    with get_connection() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                roll_number TEXT NOT NULL UNIQUE,
                class_division TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS face_embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                embedding BLOB NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                attendance_date TEXT NOT NULL,
                entry_time TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('Present', 'Late')),
                late_minutes INTEGER NOT NULL DEFAULT 0 CHECK (late_minutes >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                UNIQUE (student_id, attendance_date)
            );

            CREATE TABLE IF NOT EXISTS unknown_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_time TEXT NOT NULL,
                reason TEXT NOT NULL,
                snapshot_path TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # Keep existing local databases compatible after adding late-minute reporting.
        columns = {row[1] for row in connection.execute("PRAGMA table_info(attendance)").fetchall()}
        if "late_minutes" not in columns:
            connection.execute("ALTER TABLE attendance ADD COLUMN late_minutes INTEGER NOT NULL DEFAULT 0")


def get_dashboard_summary() -> dict[str, int]:
    """Return safe, small dashboard counts for the React frontend."""
    with get_connection() as connection:
        total_students = connection.execute("SELECT COUNT(*) FROM students").fetchone()[0]
        attendance_today = connection.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = date('now', 'localtime')"
        ).fetchone()[0]
        late_today = connection.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = date('now', 'localtime') AND status = 'Late'"
        ).fetchone()[0]
        unknown_today = connection.execute(
            "SELECT COUNT(*) FROM unknown_events WHERE date(event_time) = date('now', 'localtime')"
        ).fetchone()[0]

    return {
        "registered_students": total_students,
        "present_today": attendance_today - late_today,
        "late_today": late_today,
        "unknown_events_today": unknown_today,
    }


def create_student(name: str, roll_number: str, class_division: str, embedding: bytes) -> dict:
    with get_connection() as connection:
        cursor = connection.execute(
            "INSERT INTO students (name, roll_number, class_division) VALUES (?, ?, ?)",
            (name, roll_number, class_division),
        )
        student_id = cursor.lastrowid
        connection.execute(
            "INSERT INTO face_embeddings (student_id, embedding) VALUES (?, ?)",
            (student_id, embedding),
        )
    return {"id": student_id, "name": name, "roll_number": roll_number, "class_division": class_division}


def list_students() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, name, roll_number, class_division, created_at FROM students ORDER BY name"
        ).fetchall()
    return [dict(row) for row in rows]


def get_registered_embeddings() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT students.id AS student_id, students.name, students.roll_number,
                   students.class_division, face_embeddings.embedding
            FROM face_embeddings
            JOIN students ON students.id = face_embeddings.student_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def mark_attendance(student_id: int) -> dict:
    now = datetime.now()
    school_start = datetime.strptime(SCHOOL_START_TIME, "%H:%M").replace(
        year=now.year, month=now.month, day=now.day
    )
    late_after = school_start + timedelta(minutes=LATE_GRACE_MINUTES)
    late_minutes = max(0, int((now - school_start).total_seconds() // 60))
    status = "Late" if now > late_after else "Present"
    if status == "Present":
        late_minutes = 0
    with get_connection() as connection:
        existing = connection.execute(
            "SELECT entry_time, status, late_minutes FROM attendance WHERE student_id = ? AND attendance_date = ?",
            (student_id, now.date().isoformat()),
        ).fetchone()
        if existing:
            return {"marked_now": False, "entry_time": existing["entry_time"], "attendance_status": existing["status"], "late_minutes": existing["late_minutes"] or 0}
        connection.execute(
            """
            INSERT INTO attendance (student_id, attendance_date, entry_time, status, late_minutes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (student_id, now.date().isoformat(), now.strftime("%I:%M %p"), status, late_minutes),
        )
    return {"marked_now": True, "entry_time": now.strftime("%I:%M %p"), "attendance_status": status, "late_minutes": late_minutes}


def get_attendance(date_value: str | None = None, query: str = "") -> list[dict]:
    date_value = date_value or datetime.now().date().isoformat()
    with get_connection() as connection:
        rows = connection.execute(
            """
            SELECT students.name, students.roll_number, students.class_division,
                   attendance.attendance_date, attendance.entry_time, attendance.status, attendance.late_minutes
            FROM attendance JOIN students ON students.id = attendance.student_id
            WHERE attendance.attendance_date = ?
              AND (students.name LIKE ? OR students.roll_number LIKE ? OR students.class_division LIKE ?)
            ORDER BY attendance.entry_time ASC
            """,
            (date_value, f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
    return [dict(row) for row in rows]


def recent_unknown_exists(reason: str) -> bool:
    cutoff = (datetime.now() - timedelta(seconds=UNKNOWN_EVENT_COOLDOWN_SECONDS)).isoformat(timespec="seconds")
    with get_connection() as connection:
        row = connection.execute(
            "SELECT 1 FROM unknown_events WHERE reason = ? AND event_time >= ? LIMIT 1", (reason, cutoff)
        ).fetchone()
    return row is not None


def create_unknown_event(reason: str, snapshot_path: str | None) -> None:
    with get_connection() as connection:
        connection.execute(
            "INSERT INTO unknown_events (event_time, reason, snapshot_path) VALUES (?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), reason, snapshot_path),
        )


def list_unknown_events() -> list[dict]:
    with get_connection() as connection:
        rows = connection.execute(
            "SELECT id, event_time, reason, snapshot_path FROM unknown_events ORDER BY event_time DESC LIMIT 100"
        ).fetchall()
    return [dict(row) for row in rows]
