from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch


class FrameAnalysisQueueTests(TestCase):
    def test_analyze_frame_falls_back_when_task_dispatch_fails(self):
        expected = {
            "keypoints": [],
            "analysis": {"valid": False, "state": {}},
        }
        with (
                patch(
                    "dashboard.tasks.analyze_frame_task.delay",
                    side_effect=ConnectionError("Redis is unavailable"),
                ),
                patch("dashboard.frame_processing.process_frame",
                      return_value=expected),
        ):
            response = self.client.post(
                reverse("dashboard:analyze_frame"),
                {
                    "frame": "data:image/jpeg;base64,ZmFrZQ==",
                    "exercise": "vertical-jump",
                    "state": "{}",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)

    def test_check_task_returns_completed_result(self):
        result = {"keypoints": [], "analysis": {"state": {}}}
        with patch("celery.result.AsyncResult") as async_result:
            async_result.return_value.ready.return_value = True
            async_result.return_value.failed.return_value = False
            async_result.return_value.result = result

            response = self.client.get(
                reverse("dashboard:check_task", args=["task-123"])
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "complete", "result": result},
        )
