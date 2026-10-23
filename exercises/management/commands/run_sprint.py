import cv2
import time
import numpy as np
from ultralytics import YOLO
from django.core.management.base import BaseCommand
from django.conf import settings
from athletes.models import Athlete
from assessments.models import Assessment


MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


def draw_keypoint(frame, keypoint, label):
    x = int(keypoint[0])
    y = int(keypoint[1])
    cv2.circle(frame, (x, y), 7, (0, 255, 0), 1)
    cv2.putText(frame, label, (x + 8, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


def calculate_score(time_seconds):
    best_time = 4.0
    worst_time = 10.0
    score = ((worst_time - time_seconds) / (worst_time - best_time)) * 100
    return round(np.clip(score, 0, 100), 2)


def get_result(score):
    if score >= 80:
        return "Excellent"
    elif score >= 60:
        return "Good"
    elif score >= 40:
        return "Average"
    else:
        return "Needs Improvement"


class Command(BaseCommand):
    help = "Run 30m Sprint assessment"

    def add_arguments(self, parser):
        parser.add_argument("--athlete-id", type=str)
        parser.add_argument("--camera", type=str, default="")

    def handle(self, *args, **options):
        athlete_id = options.get("athlete_id")
        if athlete_id:
            try:
                athlete = Athlete.objects.get(athlete_id=athlete_id)
            except Athlete.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No athlete: {athlete_id}"))
                return
        else:
            athlete = Athlete.objects.first()
            if athlete is None:
                self.stdout.write(self.style.ERROR("No athlete in database"))
                return

        self.stdout.write(self.style.SUCCESS(
            f"Athlete: {athlete.name} ({athlete.athlete_id})"
        ))

        camera_source = options.get("camera") or settings.DROIDCAM_URL

        if not camera_source:
            self.stdout.write(self.style.ERROR("Set DROIDCAM_URL in .env"))
            return

        if camera_source.startswith("http"):
            cap = cv2.VideoCapture(camera_source)
            self.stdout.write("Camera: DroidCam")
        else:
            cap = cv2.VideoCapture(int(camera_source))
            self.stdout.write(f"Camera: local {camera_source}")

        if not cap.isOpened():
            self.stdout.write(self.style.ERROR("Camera not accessible"))
            return

        self.stdout.write("Loading YOLO model...")
        model = YOLO(MODEL_PATH)

        start_line = None
        finish_line = None
        start_time = None
        finish_time = None
        sprint_time = None
        final_score = None
        final_result = None
        state = "SETUP"
        selected_side = None

        window_name = "AI Fitness - 30m Sprint"
        cv2.namedWindow(window_name)

        self.stdout.write("")
        self.stdout.write("30m SPRINT ASSESSMENT")
        self.stdout.write("=" * 40)
        self.stdout.write("Side-view camera setup recommended")
        self.stdout.write("'k' = set start | 'f' = set finish")
        self.stdout.write("'c' = start timer | 's' = save")
        self.stdout.write("'r' = reset | 'q' = quit")
        self.stdout.write("=" * 40)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = model(frame)
            result = results[0]

            ankle = None
            side = None

            if result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()

                if len(keypoints) > 0:
                    person = keypoints[0]

                    left_ankle = person[15]
                    right_ankle = person[16]

                    left_valid = keypoint_valid(left_ankle)
                    right_valid = keypoint_valid(right_ankle)

                    if left_valid and right_valid:
                        if left_ankle[2] >= right_ankle[2]:
                            ankle = left_ankle
                            side = "Left"
                        else:
                            ankle = right_ankle
                            side = "Right"
                    elif right_valid:
                        ankle = right_ankle
                        side = "Right"
                    elif left_valid:
                        ankle = left_ankle
                        side = "Left"

                    if ankle is not None:
                        draw_keypoint(frame, ankle, f"{side}-Ankle")
                        ankle_x = ankle[0]

                        if state == "SETUP":
                            cv2.putText(frame, "'k' set start | 'f' set finish",
                                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                        elif state == "READY":
                            cv2.putText(frame, "Ready - press 'c' to start",
                                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                        elif state == "RUNNING":
                            current = time.time()
                            elapsed = current - start_time

                            if ankle_x >= finish_line:
                                finish_time = current
                                sprint_time = finish_time - start_time
                                final_score = calculate_score(sprint_time)
                                final_result = get_result(final_score)
                                state = "COMPLETE"

                                Assessment.objects.create(
                                    athlete=athlete,
                                    exercise="Sprint",
                                    measurement=round(sprint_time, 2),
                                    score=final_score,
                                    result=final_result,
                                )

                                self.stdout.write("")
                                self.stdout.write("=" * 40)
                                self.stdout.write(
                                    self.style.SUCCESS("SPRINT COMPLETE"))
                                self.stdout.write(
                                    f"Time: {sprint_time:.2f} sec")
                                self.stdout.write(
                                    f"Score: {final_score:.2f}/100")
                                self.stdout.write(f"Result: {final_result}")
                                self.stdout.write(self.style.SUCCESS("Saved"))
                                self.stdout.write("=" * 40)

                            else:
                                cv2.putText(frame, f"Time: {elapsed:.2f} sec",
                                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                                cv2.putText(frame, "RUN!",
                                            (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

                        elif state == "COMPLETE":
                            cv2.putText(frame, f"Time: {sprint_time:.2f} sec",
                                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            cv2.putText(frame, f"Score: {final_score:.1f}",
                                        (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            cv2.putText(frame, f"{final_result}",
                                        (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            cv2.putText(frame, "Saved! 'r' for next",
                                        (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

            if start_line is not None:
                cv2.line(frame, (int(start_line), 0), (int(start_line), frame.shape[0]),
                         (255, 0, 255), 2)
                cv2.putText(frame, "START", (int(start_line) - 30, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)

            if finish_line is not None:
                cv2.line(frame, (int(finish_line), 0), (int(finish_line), frame.shape[0]),
                         (0, 255, 255), 2)
                cv2.putText(frame, "FINISH", (int(finish_line) - 35, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("k"):
                if ankle is not None:
                    start_line = int(ankle[0])
                    self.stdout.write(f"Start line: {start_line}")

            elif key == ord("f"):
                if ankle is not None:
                    finish_line = int(ankle[0])
                    state = "READY"
                    self.stdout.write(f"Finish line: {finish_line}")

            elif key == ord("c"):
                if state == "READY" and ankle is not None:
                    selected_side = side
                    start_time = time.time()
                    state = "RUNNING"
                    self.stdout.write(f"Sprint started ({selected_side})")

            elif key == ord("s"):
                pass

            elif key == ord("r"):
                start_line = None
                finish_line = None
                start_time = None
                finish_time = None
                sprint_time = None
                final_score = None
                final_result = None
                state = "SETUP"
                selected_side = None
                self.stdout.write("Reset done")

        cap.release()
        cv2.destroyAllWindows()
