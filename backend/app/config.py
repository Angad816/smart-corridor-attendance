from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIRECTORY / "smart_corridor.db"

SCHOOL_START_TIME = os.getenv("SMART_CORRIDOR_SCHOOL_START", "08:00")
LATE_GRACE_MINUTES = int(os.getenv("SMART_CORRIDOR_LATE_GRACE_MINUTES", "0"))
FACE_MATCH_THRESHOLD = 0.48
UNKNOWN_EVENT_COOLDOWN_SECONDS = 30
MAX_IMAGE_DATA_LENGTH = 8_000_000
UNKNOWN_SNAPSHOT_DIRECTORY = PROJECT_ROOT / "assets" / "unknown_snapshots"
ALLOWED_FRONTEND_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
ALLOWED_FRONTEND_ORIGIN_REGEX = r"http://(localhost|127\.0\.0\.1):[0-9]+"


def validate_school_time(value: str) -> str:
    """Return a valid 24-hour HH:MM school start time."""
    from datetime import datetime

    datetime.strptime(value, "%H:%M")
    return value


validate_school_time(SCHOOL_START_TIME)
if not 0 <= LATE_GRACE_MINUTES <= 180:
    raise ValueError("SMART_CORRIDOR_LATE_GRACE_MINUTES must be between 0 and 180")
