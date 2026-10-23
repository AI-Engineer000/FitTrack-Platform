import time

import cv2
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ultralytics import YOLO

from assessments.models import Assessment
from athletes.models import Athlete


MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


def calculate_score(speed_mps, min_speed=1.0, max_speed=4.0):
    if max_speed <= min_speed:
        raise ValueError("max_speed must be greater than min_speed")
    score = (speed_mps - min_speed) / (max_speed - min_speed) * 100
    return round(float(np.clip(score, 0, 100)), 2)


def update_crossings(ankle_x, line_a, line_b, direction, crossings):
    """Count a completed lane traversal and turn back toward the other line."""
    if direction == 1 and ankle_x >= max(line_a, line_b):
        return -1, crossings + 1
    if direction == -1 and ankle_x <= min(line_a, line_b):
        return 1, crossings + 1
    return direction, crossings


def get_result(score):
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Average"
    return "Needs Improvement"


class Command(BaseCommand):
    help = "Run a timed shuttle run assessment and save the average speed"

    def add_arguments(self, parser):
        parser.add_argument("--athlete-id", type=str)
        parser.add_argument("--camera", type=str, default="")
        parser.add_argument("--duration-seconds", type=float, default=30.0)
        parser.add_argument("--lane-length-m", type=float, default=5.0)
        parser.add_argument("--min-speed", type=float, default=1.0)
        parser.add_argument("--max-speed", type=float, default=4.0)

    def handle(self, *args, **options):
        athlete_id = options.get("athlete_id")
        if athlete_id:
            try:
                athlete = Athlete.objects.get(athlete_id=athlete_id)
            except Athlete.DoesNotExist as exc:
                raise CommandError(f"No athlete: {athlete_id}") from exc
        else:
            athlete = Athlete.objects.first()
            if athlete is None:
                raise CommandError("No athlete in database")

        duration = options["duration_seconds"]
        lane_length = options["lane_length_m"]
        min_speed = options["min_speed"]
        max_speed = options["max_speed"]
        if duration <= 0 or lane_length <= 0:
            raise CommandError("Duration and lane length must be positive")
        if min_speed < 0 or max_speed <= min_speed:
            raise CommandError("Speed bounds must satisfy 0 <= min < max")

        camera_source = options.get("camera") or settings.DROIDCAM_URL
        if not camera_source:
            raise CommandError("Set DROIDCAM_URL in .env or pass --camera")

        if camera_source.startswith(("http://", "https://")):
            cap = cv2.VideoCapture(camera_source)
            self.stdout.write("Camera: network stream")
        else:
            try:
                camera_index = int(camera_source)
            except ValueError as exc:
                raise CommandError("--camera must be an index or stream URL") from exc
            cap = cv2.VideoCapture(camera_index)
            self.stdout.write(f"Camera: local {camera_index}")

        if not cap.isOpened():
            cap.release()
            raise CommandError("Camera not accessible")

        self.stdout.write(self.style.SUCCESS(
            f"Athlete: {athlete.name} ({athlete.athlete_id})"
        ))
        self.stdout.write("Loading YOLO pose model...")
        try:
            model = YOLO(MODEL_PATH)
        except Exception as exc:
            cap.release()
            raise CommandError(f"Could not load pose model {MODEL_PATH}: {exc}") from exc

        line_a = None
        line_b = None
        state = "SETUP"
        direction = None
        crossings = 0
        start_time = None
        elapsed = 0.0
        average_speed = 0.0
        score = None
        result_text = None
        assessment_saved = False
        window_name = "AI Fitness - Shuttle Run"

        self.stdout.write("\nSHUTTLE RUN ASSESSMENT")
        self.stdout.write("'k' = set line A | 'f' = set line B from the detected ankle")
        self.stdout.write("Return to line A, then press 'c' to start the timed run")
        self.stdout.write("'r' = reset | 'q' = quit")
        self.stdout.write(
            f"Duration: {duration:g}s | Lane: {lane_length:g}m | "
            f"Score range: {min_speed:g}-{max_speed:g} m/s"
        )

        try:
            cv2.namedWindow(window_name)
            while True:
                ok, frame = cap.read()
                if not ok:
                    self.stderr.write("Could not read a camera frame")
                    break

                ankle = None
                inference = model(frame, verbose=False)[0]
                if inference.keypoints is not None:
                    people = inference.keypoints.data.cpu().numpy()
                    if len(people):
                        person = people[0]
                        ankles = [person[15], person[16]]
                        valid_ankles = [p for p in ankles if keypoint_valid(p)]
                        if valid_ankles:
                            ankle = max(valid_ankles, key=lambda p: p[2])
                            ankle_x = int(ankle[0])
                            cv2.circle(frame, (ankle_x, int(ankle[1])), 7,
                                       (0, 255, 0), 2)
                            cv2.putText(frame, "Ankle", (ankle_x + 8, int(ankle[1]) - 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (255, 255, 255), 1)

                if line_a is not None:
                    cv2.line(frame, (line_a, 0), (line_a, frame.shape[0]),
                             (255, 0, 255), 2)
                    cv2.putText(frame, "A", (line_a + 5, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
                if line_b is not None:
                    cv2.line(frame, (line_b, 0), (line_b, frame.shape[0]),
                             (0, 255, 255), 2)
                    cv2.putText(frame, "B", (line_b + 5, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                if state == "SETUP":
                    status = "Set line A and line B with ankle at each line"
                elif state == "READY":
                    status = "Press 'c' when the athlete is at line A"
                elif state == "RUNNING":
                    elapsed = min(time.monotonic() - start_time, duration)
                    laps = crossings / 2
                    status = (
                        f"Time {elapsed:.1f}/{duration:g}s | Laps: {laps:.1f} "
                        f"| Crossings: {crossings}"
                    )
                    if ankle is not None and elapsed < duration:
                        direction, crossings = update_crossings(
                            ankle[0], line_a, line_b, direction, crossings
                        )

                    if elapsed >= duration:
                        average_speed = crossings * lane_length / duration
                        score = calculate_score(average_speed, min_speed, max_speed)
                        result_text = get_result(score)
                        Assessment.objects.create(
                            athlete=athlete,
                            exercise="Shuttle Run",
                            measurement=round(average_speed, 2),
                            score=score,
                            result=result_text,
                        )
                        assessment_saved = True
                        state = "COMPLETE"
                        self.stdout.write(self.style.SUCCESS(
                            f"Complete: {crossings} crossings, "
                            f"{average_speed:.2f} m/s, score {score:.1f}/100 ({result_text})"
                        ))
                elif state == "COMPLETE":
                    laps = crossings / 2
                    status = (
                        f"Done: {laps:.1f} laps | {average_speed:.2f} m/s "
                        f"| {score:.1f}/100"
                    )
                    cv2.putText(frame, "Saved - press 'r' for another run", (30, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

                cv2.putText(frame, status, (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (255, 255, 0), 2)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                if key == ord("k") and ankle is not None and state != "RUNNING":
                    line_a = int(ankle[0])
                    state = "READY" if line_b is not None else "SETUP"
                elif key == ord("f") and ankle is not None and state != "RUNNING":
                    line_b = int(ankle[0])
                    state = "READY" if line_a is not None and line_a != line_b else "SETUP"
                elif key == ord("c") and state == "READY" and ankle is not None:
                    if not assessment_saved:
                        crossings = 0
                        direction = 1 if line_b > line_a else -1
                        start_time = time.monotonic()
                        state = "RUNNING"
                elif key == ord("r"):
                    line_a = line_b = None
                    state = "SETUP"
                    direction = None
                    crossings = 0
                    start_time = None
                    elapsed = 0.0
                    average_speed = 0.0
                    score = result_text = None
                    assessment_saved = False
        finally:
            cap.release()
            cv2.destroyAllWindows()
