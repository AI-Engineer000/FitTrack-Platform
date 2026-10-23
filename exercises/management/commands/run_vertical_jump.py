import cv2
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
    cv2.putText(
        frame, label, (x + 8, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
    )


def draw_line(frame, point1, point2, color=(255, 255, 255)):
    x1, y1 = int(point1[0]), int(point1[1])
    x2, y2 = int(point2[0]), int(point2[1])
    cv2.line(frame, (x1, y1), (x2, y2), color, 2)


def calculate_score(jump_height_cm):
    min_jump_cm = 0
    max_jump_cm = 60
    score = ((jump_height_cm - min_jump_cm) /
             (max_jump_cm - min_jump_cm)) * 100
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


class Command(BaseCommand):
    help = "Run Vertical Jump assessment and save result to database"

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

        KNEE_STRAIGHT_THRESHOLD = 160
        JUMP_START_THRESHOLD = 15

        calibration_pixels = None
        pixels_per_cm = None
        calibration_mode = False
        calibration_points = []

        standing_position = None
        max_jump = None
        max_jump_cm = None
        final_score = None
        final_result = None
        state = "CALIBRATING"
        selected_side = None
        legs_straight = False

        def mouse_callback(event, x, y, flags, param):
            nonlocal calibration_points
            if calibration_mode and event == cv2.EVENT_LBUTTONDOWN:
                if len(calibration_points) < 2:
                    calibration_points.append((x, y))
                    self.stdout.write(
                        f"Point {len(calibration_points)}: ({x}, {y})"
                    )

        window_name = "AI Fitness - Vertical Jump Assessment"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, mouse_callback)

        self.stdout.write("")
        self.stdout.write("VERTICAL JUMP ASSESSMENT")
        self.stdout.write("=" * 40)
        self.stdout.write("'k' = calibrate | 'c' = start | 's' = save")
        self.stdout.write("'r' = reset | 'q' = quit")
        self.stdout.write("=" * 40)
        self.stdout.write("")

        while True:
            ret, frame = cap.read()
            if not ret:
                self.stdout.write(self.style.ERROR("Frame read failed"))
                break

            results = model(frame)
            result = results[0]

            shoulder = None
            hip = None
            knee = None
            ankle = None
            side = None

            if result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()

                if len(keypoints) > 0:
                    person = keypoints[0]

                    left_shoulder = person[5]
                    left_hip = person[11]
                    left_knee = person[13]
                    left_ankle = person[15]

                    right_shoulder = person[6]
                    right_hip = person[12]
                    right_knee = person[14]
                    right_ankle = person[16]

                    left_valid = (
                        keypoint_valid(left_shoulder)
                        and keypoint_valid(left_hip)
                        and keypoint_valid(left_knee)
                        and keypoint_valid(left_ankle)
                    )
                    right_valid = (
                        keypoint_valid(right_shoulder)
                        and keypoint_valid(right_hip)
                        and keypoint_valid(right_knee)
                        and keypoint_valid(right_ankle)
                    )

                    left_confidence = (
                        left_shoulder[2] + left_hip[2] +
                        left_knee[2] + left_ankle[2]
                    )
                    right_confidence = (
                        right_shoulder[2] + right_hip[2] +
                        right_knee[2] + right_ankle[2]
                    )

                    if selected_side is None:
                        if left_valid and right_valid:
                            if right_confidence >= left_confidence:
                                shoulder, hip, knee, ankle = (
                                    right_shoulder, right_hip,
                                    right_knee, right_ankle
                                )
                                side = "Right"
                            else:
                                shoulder, hip, knee, ankle = (
                                    left_shoulder, left_hip,
                                    left_knee, left_ankle
                                )
                                side = "Left"
                        elif right_valid:
                            shoulder, hip, knee, ankle = (
                                right_shoulder, right_hip,
                                right_knee, right_ankle
                            )
                            side = "Right"
                        elif left_valid:
                            shoulder, hip, knee, ankle = (
                                left_shoulder, left_hip,
                                left_knee, left_ankle
                            )
                            side = "Left"
                    else:
                        if selected_side == "Right":
                            shoulder, hip, knee, ankle = (
                                right_shoulder, right_hip,
                                right_knee, right_ankle
                            )
                            side = "Right"
                            side_valid = right_valid
                        else:
                            shoulder, hip, knee, ankle = (
                                left_shoulder, left_hip,
                                left_knee, left_ankle
                            )
                            side = "Left"
                            side_valid = left_valid

                        if not side_valid:
                            shoulder = hip = knee = ankle = None

                    if shoulder is not None:
                        draw_keypoint(frame, shoulder, f"{side}-Shoulder")
                        draw_keypoint(frame, hip, f"{side}-Hip")
                        draw_keypoint(frame, knee, f"{side}-Knee")
                        draw_keypoint(frame, ankle, f"{side}-Ankle")

                        draw_line(frame, shoulder, hip)
                        draw_line(frame, hip, knee)
                        draw_line(frame, knee, ankle)

                        leg_angle = calculate_angle(
                            hip[:2], knee[:2], ankle[:2]
                        )

                        cv2.putText(
                            frame, f"Leg Angle: {leg_angle:.1f}",
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                            0.7, (0, 255, 0), 2
                        )

                        legs_straight = leg_angle >= KNEE_STRAIGHT_THRESHOLD

                        if not legs_straight:
                            cv2.putText(
                                frame, "KEEP LEGS STRAIGHT",
                                (30, 75), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 0, 255), 2
                            )

                        ankle_y = ankle[1]

                        if state == "CALIBRATING":
                            cv2.putText(
                                frame, "Press 'k' to calibrate",
                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (255, 255, 0), 2
                            )

                        elif state == "READY":
                            cv2.putText(
                                frame, "Stand straight, press 'c'",
                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (255, 255, 0), 2
                            )
                            if standing_position is not None:
                                cv2.line(
                                    frame,
                                    (0, int(standing_position)),
                                    (frame.shape[1], int(standing_position)),
                                    (255, 0, 255), 2
                                )
                            cv2.putText(
                                frame, f"Using: {selected_side} side",
                                (30, 145), cv2.FONT_HERSHEY_SIMPLEX,
                                0.6, (255, 255, 255), 2
                            )

                        elif state == "JUMPING":
                            current_jump = standing_position - ankle_y
                            current_jump = max(0, current_jump)

                            if max_jump is None or current_jump > max_jump:
                                max_jump = current_jump
                                if pixels_per_cm is not None:
                                    max_jump_cm = max_jump / pixels_per_cm

                            cv2.line(
                                frame,
                                (0, int(standing_position)),
                                (frame.shape[1], int(standing_position)),
                                (255, 0, 255), 2
                            )
                            cv2.line(
                                frame,
                                (int(ankle[0]), int(standing_position)),
                                (int(ankle[0]), int(ankle_y)),
                                (0, 255, 255), 3
                            )

                            if pixels_per_cm is not None:
                                current_jump_cm = current_jump / pixels_per_cm
                                cv2.putText(
                                    frame, f"Current: {current_jump_cm:.1f} cm",
                                    (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, (0, 255, 255), 2
                                )
                                if max_jump_cm is not None:
                                    cv2.putText(
                                        frame, f"Max: {max_jump_cm:.1f} cm",
                                        (30, 145), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.7, (0, 255, 255), 2
                                    )
                            else:
                                cv2.putText(
                                    frame, f"Current: {current_jump:.1f} px",
                                    (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.7, (0, 255, 255), 2
                                )
                                if max_jump is not None:
                                    cv2.putText(
                                        frame, f"Max: {max_jump:.1f} px",
                                        (30, 145), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.7, (0, 255, 255), 2
                                    )

                            cv2.putText(
                                frame, "JUMP!",
                                (30, 180), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (0, 255, 0), 2
                            )

                        elif state == "COMPLETE":
                            if max_jump_cm is not None:
                                cv2.putText(
                                    frame, f"Final: {max_jump_cm:.1f} cm",
                                    (30, 110), cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (0, 255, 0), 2
                                )
                                if final_score is not None:
                                    cv2.putText(
                                        frame, f"Score: {final_score:.1f}/100",
                                        (30, 150), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.8, (0, 255, 0), 2
                                    )
                                    cv2.putText(
                                        frame, f"Result: {final_result}",
                                        (30, 190), cv2.FONT_HERSHEY_SIMPLEX,
                                        0.8, (0, 255, 0), 2
                                    )
                            cv2.putText(
                                frame, "Saved! Press 'r' for next",
                                (30, 230), cv2.FONT_HERSHEY_SIMPLEX,
                                0.7, (255, 255, 0), 2
                            )

                    else:
                        cv2.putText(
                            frame, "Keypoints not visible",
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

            if calibration_mode:
                cv2.putText(
                    frame, "Click two endpoints of reference",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 255, 255), 2
                )
                for point in calibration_points:
                    cv2.circle(frame, point, 7, (0, 0, 255), -1)
                if len(calibration_points) == 2:
                    cv2.line(
                        frame,
                        calibration_points[0],
                        calibration_points[1],
                        (0, 255, 255), 2
                    )

            if pixels_per_cm is not None:
                cv2.putText(
                    frame, f"Scale: {pixels_per_cm:.2f} px/cm",
                    (30, 290), cv2.FONT_HERSHEY_SIMPLEX,
                    0.6, (255, 255, 255), 2
                )

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("k"):
                calibration_mode = True
                calibration_points = []
                self.stdout.write("Calibration started")

            elif key == ord("c") and calibration_mode and len(calibration_points) == 2:
                point1 = np.array(calibration_points[0])
                point2 = np.array(calibration_points[1])
                calibration_pixels = np.linalg.norm(point1 - point2)

                known_length_cm = float(
                    input("Reference length in cm: ")
                )

                if known_length_cm <= 0:
                    self.stdout.write(self.style.ERROR("Invalid length"))
                else:
                    pixels_per_cm = calibration_pixels / known_length_cm
                    calibration_mode = False
                    state = "READY"
                    self.stdout.write(self.style.SUCCESS(
                        f"Scale = {pixels_per_cm:.2f} px/cm"
                    ))

            elif key == ord("c") and not calibration_mode and state == "READY":
                if pixels_per_cm is None:
                    self.stdout.write(self.style.ERROR("Calibrate first"))
                elif ankle is None:
                    self.stdout.write(self.style.ERROR("Athlete not visible"))
                elif not legs_straight:
                    self.stdout.write(self.style.ERROR("Stand straight first"))
                else:
                    selected_side = side
                    standing_position = ankle_y
                    max_jump = 0.0
                    max_jump_cm = 0.0
                    final_score = None
                    final_result = None
                    state = "JUMPING"
                    self.stdout.write(f"Jump started ({selected_side} side)")

            elif key == ord("s"):
                if state == "JUMPING" and max_jump_cm is not None:
                    final_score = calculate_score(max_jump_cm)
                    final_result = get_result(final_score)

                    Assessment.objects.create(
                        athlete=athlete,
                        exercise="Vertical Jump",
                        measurement=max_jump_cm,
                        score=final_score,
                        result=final_result,
                    )

                    state = "COMPLETE"

                    self.stdout.write("")
                    self.stdout.write("=" * 40)
                    self.stdout.write(self.style.SUCCESS("COMPLETE"))
                    self.stdout.write(f"Jump: {max_jump_cm:.2f} cm")
                    self.stdout.write(f"Score: {final_score:.2f}/100")
                    self.stdout.write(f"Result: {final_result}")
                    self.stdout.write(self.style.SUCCESS("Saved to database"))
                    self.stdout.write("=" * 40)
                    self.stdout.write("")

            elif key == ord("r"):
                calibration_pixels = None
                pixels_per_cm = None
                calibration_mode = False
                calibration_points = []
                standing_position = None
                max_jump = None
                max_jump_cm = None
                final_score = None
                final_result = None
                state = "CALIBRATING"
                selected_side = None
                legs_straight = False
                self.stdout.write("Reset done")

        cap.release()
        cv2.destroyAllWindows()
