import cv2
import numpy as np
from ultralytics import YOLO
from django.core.management.base import BaseCommand
from django.conf import settings
from athletes.models import Athlete
from assessments.models import Assessment


MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5

# Sit-up settings
UP_THRESHOLD = 140
DOWN_THRESHOLD = 90


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


def draw_keypoint(frame, keypoint, label):
    x = int(keypoint[0])
    y = int(keypoint[1])
    cv2.circle(frame, (x, y), 7, (0, 255, 0), 1)
    cv2.putText(
        frame, label, (x + 8, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
    )


def draw_line(frame, point1, point2, color=(255, 255, 255)):
    x1, y1 = int(point1[0]), int(point1[1])
    x2, y2 = int(point2[0]), int(point2[1])
    cv2.line(frame, (x1, y1), (x2, y2), color, 2)


def calculate_angle(a, b, c):
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    dot_product = np.dot(ba, bc)
    norm_ba = np.linalg.norm(ba)
    norm_bc = np.linalg.norm(bc)

    if norm_ba == 0 or norm_bc == 0:
        raise ValueError("Cannot calculate angle with a zero vector.")

    cosine_angle = dot_product / (norm_ba * norm_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)

    angle_radians = np.arccos(cosine_angle)
    angle_degrees = np.degrees(angle_radians)
    return angle_degrees


def calculate_score(repetitions):
    min_reps = 0
    max_reps = 30
    score = (repetitions / max_reps) * 100
    score = np.clip(score, 0, 100)
    return round(score, 2)


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
    help = "Run Sit-ups assessment and save result to database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--athlete-id", type=str,
            help="Athlete ID (default: first athlete)"
        )
        parser.add_argument(
            "--camera", type=str, default="",
            help="Camera index or DroidCam URL (default: from .env)"
        )

    def handle(self, *args, **options):

        # athlete nikalo
        athlete_id = options.get("athlete_id")

        if athlete_id:
            try:
                athlete = Athlete.objects.get(athlete_id=athlete_id)
            except Athlete.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f"No athlete with ID: {athlete_id}"
                ))
                return
        else:
            athlete = Athlete.objects.first()
            if athlete is None:
                self.stdout.write(self.style.ERROR(
                    "No athlete in database. Create one in admin first."
                ))
                return

        self.stdout.write(self.style.SUCCESS(
            f"Athlete: {athlete.name} ({athlete.athlete_id})"
        ))

        # camera source
        camera_source = options.get("camera") or settings.DROIDCAM_URL

        if not camera_source:
            self.stdout.write(self.style.ERROR(
                "Set DROIDCAM_URL in .env or pass --camera"
            ))
            return

        if camera_source.startswith("http"):
            cap = cv2.VideoCapture(camera_source)
            self.stdout.write(f"Camera: DroidCam ({camera_source})")
        else:
            cap = cv2.VideoCapture(int(camera_source))
            self.stdout.write(f"Camera: local index {camera_source}")

        if not cap.isOpened():
            self.stdout.write(self.style.ERROR(
                f"Camera not accessible: {camera_source}"
            ))
            return

        self.stdout.write("Loading YOLO model...")
        model = YOLO(MODEL_PATH)

        # state variables
        state = None
        previous_state = None
        repetitions = 0
        final_score = None
        final_result = None
        assessment_saved = False

        window_name = "AI Fitness - Sit-ups Assessment"
        cv2.namedWindow(window_name)

        self.stdout.write("")
        self.stdout.write("SIT-UPS ASSESSMENT")
        self.stdout.write("=" * 40)
        self.stdout.write("'s' = finish & save | 'r' = reset | 'q' = quit")
        self.stdout.write("=" * 40)
        self.stdout.write("")

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            # Original size dekho
            h, w = frame.shape[:2]

            # Aspect ratio maintain karke resize karo (width 480 pe)
            new_w = 480
            new_h = int(h * (new_w / w))

            frame = cv2.resize(frame, (new_w, new_h))

            results = model(frame)

            shoulder = None
            hip = None
            knee = None
            side = None

            if result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()

                if len(keypoints) > 0:
                    person = keypoints[0]

                    left_shoulder = person[5]
                    left_hip = person[11]
                    left_knee = person[13]

                    right_shoulder = person[6]
                    right_hip = person[12]
                    right_knee = person[14]

                    right_valid = (
                        keypoint_valid(right_shoulder)
                        and keypoint_valid(right_hip)
                        and keypoint_valid(right_knee)
                    )
                    left_valid = (
                        keypoint_valid(left_shoulder)
                        and keypoint_valid(left_hip)
                        and keypoint_valid(left_knee)
                    )

                    if right_valid:
                        shoulder = right_shoulder
                        hip = right_hip
                        knee = right_knee
                        side = "Right"
                    elif left_valid:
                        shoulder = left_shoulder
                        hip = left_hip
                        knee = left_knee
                        side = "Left"
                    else:
                        shoulder = None
                        hip = None
                        knee = None
                        side = None

                    if shoulder is not None:
                        draw_keypoint(frame, shoulder, f"{side}-Shoulder")
                        draw_keypoint(frame, hip, f"{side}-Hip")
                        draw_keypoint(frame, knee, f"{side}-Knee")

                        draw_line(frame, shoulder, hip)
                        draw_line(frame, hip, knee)

                        hip_angle = calculate_angle(
                            shoulder[:2], hip[:2], knee[:2]
                        )

                        # state detection
                        if hip_angle > UP_THRESHOLD:
                            state = "UP"
                        elif hip_angle < DOWN_THRESHOLD:
                            state = "DOWN"
                        else:
                            state = "TRANSITION"

                        # count repetition
                        if previous_state == "UP" and state == "DOWN":
                            repetitions += 1

                        if state != "TRANSITION":
                            previous_state = state

                        # display on frame
                        cv2.putText(
                            frame, f"Hip Angle: {hip_angle:.1f}",
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2
                        )
                        cv2.putText(
                            frame, f"State: {state}",
                            (30, 80), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2
                        )
                        cv2.putText(
                            frame, f"Reps: {repetitions}",
                            (30, 120), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2
                        )
                        cv2.putText(
                            frame, f"Using: {side} side",
                            (30, 160), cv2.FONT_HERSHEY_SIMPLEX,
                            0.5, (255, 255, 255), 1
                        )

                        if assessment_saved:
                            cv2.putText(
                                frame, f"Saved! Score: {final_score:.1f}",
                                (30, 200), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 255), 2
                            )
                            cv2.putText(
                                frame, f"Result: {final_result}",
                                (30, 240), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 255), 2
                            )

                    else:
                        cv2.putText(
                            frame, "Adjust camera - keypoints not visible",
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 0, 255), 2
                        )

                else:
                    cv2.putText(
                        frame, "No person detected",
                        (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (0, 0, 255), 2
                    )
            else:
                cv2.putText(
                    frame, "No pose detected",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 255), 2
                )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("s"):
                if repetitions > 0 and not assessment_saved:
                    final_score = calculate_score(repetitions)
                    final_result = get_result(final_score)

                    Assessment.objects.create(
                        athlete=athlete,
                        exercise="Sit-ups",
                        measurement=float(repetitions),
                        score=final_score,
                        result=final_result,
                    )

                    assessment_saved = True

                    self.stdout.write("")
                    self.stdout.write("=" * 40)
                    self.stdout.write(self.style.SUCCESS("COMPLETE"))
                    self.stdout.write(f"Repetitions: {repetitions}")
                    self.stdout.write(f"Score: {final_score:.2f}/100")
                    self.stdout.write(f"Result: {final_result}")
                    self.stdout.write(self.style.SUCCESS("Saved to database"))
                    self.stdout.write("=" * 40)
                    self.stdout.write("")
                else:
                    self.stdout.write(self.style.WARNING(
                        "No repetitions recorded or already saved"
                    ))

            elif key == ord("r"):
                repetitions = 0
                state = None
                previous_state = None
                final_score = None
                final_result = None
                assessment_saved = False
                self.stdout.write("Reset done")

        cap.release()
        cv2.destroyAllWindows()
