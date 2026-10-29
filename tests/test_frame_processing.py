import base64
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


def test_process_frame_persists_height_based_scale_in_analysis_state():
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

    assert result["analysis"]["state"]["pixels_per_cm"] == 2.0
    assert result["frame_width"] == 640
    assert result["frame_height"] == 480


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
