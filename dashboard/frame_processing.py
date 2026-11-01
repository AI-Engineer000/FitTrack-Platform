import base64
import json
from pathlib import Path

import cv2
import numpy as np

from dashboard.live_analysis import analyze_exercise


CONFIDENCE_THRESHOLD = 0.5
UPRIGHT_ANGLE_THRESHOLD = 150.0
_yolo_model = None


def _keypoint_valid(keypoint):
    return (
        len(keypoint) >= 3
        and np.isfinite(keypoint[:3]).all()
        and keypoint[2] >= CONFIDENCE_THRESHOLD
    )


def _angle_at_joint(first, joint, last):
    first_vector = np.asarray(first[:2], dtype=float) - joint[:2]
    last_vector = np.asarray(last[:2], dtype=float) - joint[:2]
    first_norm = np.linalg.norm(first_vector)
    last_norm = np.linalg.norm(last_vector)
    if first_norm < 1e-6 or last_norm < 1e-6:
        return None

    cosine = np.dot(first_vector, last_vector) / (first_norm * last_norm)
    return float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))))


def _estimate_pixels_per_cm(keypoints, athlete_height_cm):
    try:
        height_cm = float(athlete_height_cm)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(height_cm) or not 100 <= height_cm <= 250:
        return None
    if len(keypoints) < 17 or not _keypoint_valid(keypoints[0]):
        return None
    if not (
        _keypoint_valid(keypoints[15])
        and _keypoint_valid(keypoints[16])
    ):
        return None

    upright_side = False
    for shoulder_index, hip_index, knee_index, ankle_index in (
        (5, 11, 13, 15),
        (6, 12, 14, 16),
    ):
        shoulder, hip, knee, ankle = (
            keypoints[shoulder_index],
            keypoints[hip_index],
            keypoints[knee_index],
            keypoints[ankle_index],
        )
        if not all(_keypoint_valid(point) for point in (shoulder, hip, knee, ankle)):
            continue
        if not (
            float(keypoints[0][1])
            < float(shoulder[1])
            < float(hip[1])
            < float(knee[1])
            < float(ankle[1])
        ):
            continue
        hip_angle = _angle_at_joint(shoulder, hip, knee)
        knee_angle = _angle_at_joint(hip, knee, ankle)
        if (
            hip_angle is not None
            and knee_angle is not None
            and hip_angle >= UPRIGHT_ANGLE_THRESHOLD
            and knee_angle >= UPRIGHT_ANGLE_THRESHOLD
        ):
            upright_side = True
            break
    if not upright_side:
        return None

    nose_y = float(keypoints[0][1])
    ankle_y = (float(keypoints[15][1]) + float(keypoints[16][1])) / 2
    pixel_span = ankle_y - nose_y
    if not np.isfinite(pixel_span) or pixel_span <= 0:
        return None
    return pixel_span / height_cm


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO

        model_path = Path(__file__).resolve().parent.parent / "yolo26n-pose.pt"
        _yolo_model = YOLO(str(model_path))
    return _yolo_model


def process_frame(frame_data, exercise, state, athlete_height_cm=None):
    if isinstance(state, str):
        state = json.loads(state or "{}")
    if not isinstance(state, dict):
        raise ValueError("State must be a JSON object")

    if "," in frame_data:
        frame_data = frame_data.split(",", 1)[1]
    try:
        frame_bytes = base64.b64decode(frame_data, validate=True)
    except Exception:
        return {"error": "Invalid frame", "keypoints": [], "analysis": {"valid": False, "state": state}}
    frame_array = np.frombuffer(frame_bytes, np.uint8)
    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

    if frame is None:
        return {"error": "Invalid frame"}

    results = _get_yolo_model()(frame, verbose=False)[0]
    keypoints = []
    if results.keypoints is not None:
        detected_keypoints = results.keypoints.data.cpu().numpy()
        if len(detected_keypoints) == 1:
            keypoints = detected_keypoints[0].tolist()
        elif len(detected_keypoints) > 1 and results.boxes is not None and len(results.boxes) > 0:
            boxes = results.boxes.xyxy.cpu().numpy()
            areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
            keypoints = detected_keypoints[int(np.argmax(areas))].tolist()
        elif len(detected_keypoints) > 0:
            keypoints = detected_keypoints[0].tolist()

    if athlete_height_cm is not None and not state.get("pixels_per_cm"):
        pixels_per_cm = _estimate_pixels_per_cm(
            keypoints, athlete_height_cm)
        if pixels_per_cm is not None:
            state["pixels_per_cm"] = pixels_per_cm
            state["calibration_status"] = "estimated"
            state["calibration_method"] = "nose_to_ankle_height"
            state["athlete_height_cm"] = float(athlete_height_cm)

    analysis = analyze_exercise(exercise, keypoints, state)
    return {
        "keypoints": keypoints,
        "analysis": analysis,
        "frame_width": frame.shape[1],
        "frame_height": frame.shape[0],
    }
