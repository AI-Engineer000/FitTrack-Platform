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
CROSSING_HYSTERESIS_PX = 12


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


def calculate_score(distance_m, min_distance=800, max_distance=2400):
    if max_distance <= min_distance:
        raise ValueError("max_distance must be greater than min_distance")
    score = (distance_m - min_distance) / (max_distance - min_distance) * 100
    return round(float(np.clip(score, 0, 100)), 2)


def get_result(score):
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Average"
    return "Needs Improvement"


def update_lap_count(ankle_x, finish_line, last_side, laps):
    """Count a line crossing once, ignoring ankle jitter near the line."""
    if ankle_x <= finish_line - CROSSING_HYSTERESIS_PX:
        current_side = -1
    elif ankle_x >= finish_line + CROSSING_HYSTERESIS_PX:
        current_side = 1
    else:
        current_side = last_side

    if last_side is not None and current_side is not None and current_side != last_side:
        laps += 1
    return current_side, laps


class Command(BaseCommand):
    help = "Run a timed endurance assessment and save distance covered"

    def add_arguments(self, parser):
        parser.add_argument("--athlete-id", type=str)
        parser.add_argument("--camera", type=str, default="")
        parser.add_argument("--duration-seconds", type=float, default=30.0)
        parser.add_argument("--track-length-m", type=float, default=400.0)
        parser.add_argument("--min-distance", type=float, default=800.0)
        parser.add_argument("--max-distance", type=float, default=2400.0)

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
        track_length = options["track_length_m"]
        min_distance = options["min_distance"]
        max_distance = options["max_distance"]
        if duration <= 0 or track_length <= 0:
            raise CommandError("Duration and track length must be positive")
        if min_distance < 0 or max_distance <= min_distance:
            raise CommandError("Distance bounds must satisfy 0 <= min < max")

        camera_source = options.get("camera") or settings.DROIDCAM_URL
        if not camera_source:
            raise CommandError("Set DROIDCAM_URL in .env or pass --camera")
        if camera_source.startswith(("http://", "https://")):
            cap = cv2.VideoCapture(camera_source)
        else:
            try:
                camera_index = int(camera_source)
            except ValueError as exc:
                raise CommandError("--camera must be an index or stream URL") from exc
            cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            cap.release()
            raise CommandError("Camera not accessible")

        try:
            self.stdout.write(self.style.SUCCESS(
                f"Athlete: {athlete.name} ({athlete.athlete_id})"
            ))
            self.stdout.write("Loading YOLO pose model...")
            try:
                model = YOLO(MODEL_PATH)
            except Exception as exc:
                raise CommandError(f"Could not load pose model {MODEL_PATH}: {exc}") from exc

            finish_line = None
            state = "SETUP"
            last_side = None
            laps = 0
            start_time = None
            distance = 0.0
            score = None
            result_text = None
            assessment_saved = False
            window_name = "AI Fitness - Endurance Run"

            self.stdout.write("\nENDURANCE RUN ASSESSMENT")
            self.stdout.write("'k' = set finish line | 'c' = start timer")
            self.stdout.write("'r' = reset run | 'q' = quit")
            self.stdout.write(
                f"Duration: {duration:g}s | Track length: {track_length:g}m"
            )

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
                        valid_ankles = [p for p in (person[15], person[16])
                                        if keypoint_valid(p)]
                        if valid_ankles:
                            ankle = max(valid_ankles, key=lambda p: p[2])
                            ankle_x, ankle_y = int(ankle[0]), int(ankle[1])
                            cv2.circle(frame, (ankle_x, ankle_y), 7,
                                       (0, 255, 0), 2)
                            cv2.putText(frame, "Ankle", (ankle_x + 8, ankle_y - 8),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                                        (255, 255, 255), 1)

                if finish_line is not None:
                    cv2.line(frame, (finish_line, 0),
                             (finish_line, frame.shape[0]), (255, 0, 255), 2)
                    cv2.putText(frame, "LAP LINE", (finish_line + 5, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 0, 255), 2)

                if state == "SETUP":
                    status = "Stand at the lap line and press 'k'"
                elif state == "READY":
                    status = "Press 'c' to start the timed run"
                elif state == "RUNNING":
                    elapsed = min(time.monotonic() - start_time, duration)
                    status = f"Time {elapsed:.1f}/{duration:g}s | Laps {laps}"
                    if ankle is not None and elapsed < duration:
                        last_side, laps = update_lap_count(
                            ankle[0], finish_line, last_side, laps
                        )
                        status = f"Time {elapsed:.1f}/{duration:g}s | Laps {laps}"
                    if elapsed >= duration:
                        distance = laps * track_length
                        score = calculate_score(distance, min_distance, max_distance)
                        result_text = get_result(score)
                        Assessment.objects.create(
                            athlete=athlete,
                            exercise="Endurance Run",
                            measurement=round(distance, 2),
                            score=score,
                            result=result_text,
                        )
                        assessment_saved = True
                        state = "COMPLETE"
                        self.stdout.write(self.style.SUCCESS(
                            f"Complete: {laps} laps, {distance:.0f} m, "
                            f"score {score:.1f}/100 ({result_text})"
                        ))
                else:
                    status = f"Done: {laps} laps | {distance:.0f} m | {score:.1f}/100"
                    cv2.putText(frame, "Saved - press 'r' for another run", (30, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

                cv2.putText(frame, status, (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, (255, 255, 0), 2)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key == ord("q"):
                    break
                if key == ord("k") and ankle is not None and state != "RUNNING":
                    finish_line = int(ankle[0])
                    state = "READY"
                    self.stdout.write(f"Lap line set at x={finish_line}")
                elif key == ord("c") and state == "READY" and ankle is not None:
                    if not assessment_saved:
                        last_side = None
                        laps = 0
                        start_time = time.monotonic()
                        state = "RUNNING"
                elif key == ord("r"):
                    state = "READY" if finish_line is not None else "SETUP"
                    last_side = None
                    laps = 0
                    start_time = None
                    distance = 0.0
                    score = result_text = None
                    assessment_saved = False
        finally:
            cap.release()
            cv2.destroyAllWindows()
