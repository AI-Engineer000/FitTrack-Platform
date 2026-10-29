import base64
import json
from pathlib import Path

import cv2
import numpy as np

from dashboard.live_analysis import analyze_exercise, estimate_pixels_per_cm


_yolo_model = None


def _get_yolo_model():
    global _yolo_model
    if _yolo_model is None:
        from ultralytics import YOLO

        model_path = Path(__file__).resolve().parent.parent / "yolo26n-pose.pt"
        _yolo_model = YOLO(str(model_path))
    return _yolo_model


def process_frame(frame_data, exercise, state):
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
        if len(detected_keypoints) > 0:
            keypoints = detected_keypoints[0].tolist()

    if keypoints and "pixels_per_cm" not in state:
        nose = keypoints[0]
        valid_ankles = [
            ankle for ankle in (keypoints[15], keypoints[16])
            if len(ankle) >= 3 and ankle[2] >= 0.5
        ]
        if len(nose) >= 3 and nose[2] >= 0.5 and valid_ankles:
            pixel_height = abs(
                max(float(ankle[1]) for ankle in valid_ankles)
                - float(nose[1])
            )
            if pixel_height > 100:
                state["pixels_per_cm"] = estimate_pixels_per_cm(keypoints)

    analysis = analyze_exercise(exercise, keypoints, state)
    return {
        "keypoints": keypoints,
        "analysis": analysis,
        "frame_width": frame.shape[1],
        "frame_height": frame.shape[0],
    }
