"""Face decoding, encoding, and safe comparison functions."""

import base64
import binascii
from dataclasses import dataclass

import cv2
import face_recognition
import numpy as np

from .config import FACE_MATCH_THRESHOLD


class FaceValidationError(ValueError):
    """Raised when an image cannot safely be used for face registration or recognition."""


@dataclass
class MatchResult:
    student: dict | None
    distance: float | None


def decode_camera_image(image_data: str) -> tuple[np.ndarray, np.ndarray]:
    """Turn a browser data URL into BGR and RGB OpenCV images."""
    try:
        encoded = image_data.split(",", 1)[1] if "," in image_data else image_data
        raw = base64.b64decode(encoded, validate=True)
        bgr_image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    except (ValueError, IndexError, binascii.Error) as error:
        raise FaceValidationError("The camera image could not be read.") from error
    if bgr_image is None:
        raise FaceValidationError("The camera image could not be read.")
    return bgr_image, cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)


def encode_single_face(rgb_image: np.ndarray) -> np.ndarray:
    locations = face_recognition.face_locations(rgb_image, model="hog")
    if not locations:
        raise FaceValidationError("No face found. Center one clear face in the camera and try again.")
    if len(locations) > 1:
        raise FaceValidationError("More than one face found. Keep only one person in the camera frame.")
    encodings = face_recognition.face_encodings(rgb_image, known_face_locations=locations)
    if not encodings:
        raise FaceValidationError("The face could not be encoded. Improve lighting and try again.")
    return encodings[0]


def encode_for_storage(encoding: np.ndarray) -> bytes:
    return np.asarray(encoding, dtype=np.float64).tobytes()


def find_safe_match(encoding: np.ndarray, registered_embeddings: list[dict]) -> MatchResult:
    if not registered_embeddings:
        return MatchResult(student=None, distance=None)
    known_encodings = [np.frombuffer(row["embedding"], dtype=np.float64) for row in registered_embeddings]
    distances = face_recognition.face_distance(known_encodings, encoding)
    best_index = int(np.argmin(distances))
    best_distance = float(distances[best_index])
    if best_distance > FACE_MATCH_THRESHOLD:
        return MatchResult(student=None, distance=best_distance)
    return MatchResult(student=registered_embeddings[best_index], distance=best_distance)
