import base64
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from dashboard.frame_processing import process_frame


class _FakeTensor:
    def __init__(self, value):
        self.value = value

    def cpu(self):
        return self

    def numpy(self):
        return self.value


def test_process_frame_does_not_invent_physical_scale_from_person_height():
    keypoints = np.zeros((1, 17, 3), dtype=float)
    keypoints[0, :, 2] = 0.9
    keypoints[0, 0, 1] = 100
    keypoints[0, 15, 1] = 410
    keypoints[0, 16, 1] = 440

    fake_results = SimpleNamespace(
        keypoints=SimpleNamespace(data=_FakeTensor(keypoints))
    )
    def fake_model(frame, verbose=False): return [fake_results]
    image_data = base64.b64encode(b"mock-image").decode("ascii")

    with (
        patch("dashboard.frame_processing.cv2.imdecode",
              return_value=np.zeros((480, 640, 3), dtype=np.uint8)),
        patch("dashboard.frame_processing._get_yolo_model",
              return_value=fake_model),
    ):
        result = process_frame(image_data, "vertical-jump", {})

    assert "pixels_per_cm" not in result["analysis"]["state"]
    assert result["analysis"]["unit"] == "px"
    assert result["frame_width"] == 640
    assert result["frame_height"] == 480


def test_process_frame_estimates_scale_from_confident_upright_pose():
    keypoints = np.zeros((1, 17, 3), dtype=float)
    keypoints[0, :, 2] = 0.9
    keypoints[0, 0] = [100, 50, 0.9]
    keypoints[0, [5, 6]] = [100, 100, 0.9]
    keypoints[0, [11, 12]] = [100, 200, 0.9]
    keypoints[0, [13, 14]] = [100, 300, 0.9]
    keypoints[0, [15, 16]] = [100, 450, 0.9]
    fake_results = SimpleNamespace(
        keypoints=SimpleNamespace(data=_FakeTensor(keypoints))
    )
    def fake_model(frame, verbose=False): return [fake_results]
    image_data = base64.b64encode(b"mock-image").decode("ascii")

    with (
        patch("dashboard.frame_processing.cv2.imdecode",
              return_value=np.zeros((480, 640, 3), dtype=np.uint8)),
        patch("dashboard.frame_processing._get_yolo_model",
              return_value=fake_model),
    ):
        calibrated = process_frame(
            image_data, "vertical-jump", {}, athlete_height_cm=200)

    assert calibrated["analysis"]["state"]["pixels_per_cm"] == 2.0
    assert calibrated["analysis"]["state"]["calibration_status"] == "estimated"
    assert calibrated["analysis"]["unit"] == "cm"


def test_process_frame_does_not_estimate_scale_from_non_upright_pose():
    keypoints = np.zeros((1, 17, 3), dtype=float)
    keypoints[0, :, 2] = 0.9
    keypoints[0, 0] = [100, 50, 0.9]
    keypoints[0, [5, 6]] = [100, 200, 0.9]
    keypoints[0, [11, 12]] = [100, 200, 0.9]
    keypoints[0, [13, 14]] = [100, 300, 0.9]
    keypoints[0, [15, 16]] = [100, 450, 0.9]
    fake_results = SimpleNamespace(
        keypoints=SimpleNamespace(data=_FakeTensor(keypoints))
    )
    def fake_model(frame, verbose=False): return [fake_results]
    image_data = base64.b64encode(b"mock-image").decode("ascii")

    with (
        patch("dashboard.frame_processing.cv2.imdecode",
              return_value=np.zeros((480, 640, 3), dtype=np.uint8)),
        patch("dashboard.frame_processing._get_yolo_model",
              return_value=fake_model),
    ):
        result = process_frame(
            image_data, "vertical-jump", {}, athlete_height_cm=200)

    assert "pixels_per_cm" not in result["analysis"]["state"]
    assert result["analysis"]["unit"] == "px"


def test_process_frame_handles_invalid_image_data():
    result = process_frame("invalid_base64_data", "vertical-jump", {})
    assert "error" in result


def test_process_frame_handles_no_person_detected():
    fake_results = SimpleNamespace(
        keypoints=SimpleNamespace(data=_FakeTensor(np.zeros((0, 17, 3))))
    )
    def fake_model(frame, verbose=False): return [fake_results]
    image_data = base64.b64encode(b"mock-image").decode("ascii")

    with (
        patch("dashboard.frame_processing.cv2.imdecode",
              return_value=np.zeros((480, 640, 3), dtype=np.uint8)),
        patch("dashboard.frame_processing._get_yolo_model",
              return_value=fake_model),
    ):
        result = process_frame(image_data, "vertical-jump", {})

    assert result["keypoints"] == []
    assert result["analysis"]["valid"] is False
    assert result["frame_width"] == 640
    assert result["frame_height"] == 480


def test_process_frame_preserves_situp_state_between_serialized_requests():
    def situp_keypoints(angle):
        keypoints = np.zeros((1, 17, 3), dtype=float)
        keypoints[0, :, 2] = 0.9
        hip_x, hip_y, segment_length = 100.0, 100.0, 100.0
        radians = np.radians(angle)
        shoulder_x = hip_x - segment_length * np.sin(radians)
        shoulder_y = hip_y + segment_length * np.cos(radians)
        keypoints[0, [5, 6]] = [shoulder_x, shoulder_y, 0.9]
        keypoints[0, [11, 12]] = [hip_x, hip_y, 0.9]
        keypoints[0, [13, 14]] = [hip_x, hip_y + segment_length, 0.9]
        return keypoints

    frame_results = [
        SimpleNamespace(
            keypoints=SimpleNamespace(data=_FakeTensor(situp_keypoints(angle)))
        )
        for angle in (160, 160, 90, 90)
    ]
    def fake_model(frame, verbose=False):
        return [frame_results.pop(0)]

    image_data = base64.b64encode(b"mock-image").decode("ascii")
    state = {}
    with (
        patch(
            "dashboard.frame_processing.cv2.imdecode",
            return_value=np.zeros((480, 640, 3), dtype=np.uint8),
        ),
        patch("dashboard.frame_processing._get_yolo_model", return_value=fake_model),
    ):
        for _ in range(4):
            result = process_frame(
                image_data, "sit-ups", json.dumps(state))
            state = result["analysis"]["state"]

    assert state["reps"] == 1
    assert state["situp_phase"] == "top"
