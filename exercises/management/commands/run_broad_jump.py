import cv2
import numpy as np
from ultralytics import YOLO
from django.core.management.base import BaseCommand
from django.conf import settings
from athletes.models import Athlete
from assessments.models import Assessment


MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5
KNEE_STRAIGHT_THRESHOLD = 150


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


def draw_keypoint(frame, keypoint, label):
    x = int(keypoint[0])
    y = int(keypoint[1])
    cv2.circle(frame, (x, y), 7, (0, 255, 0), 1)
    cv2.putText(frame, label, (x + 8, y - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


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
        raise ValueError("Zero vector")
    cosine_angle = dot_product / (norm_ba * norm_bc)
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    return np.degrees(np.arccos(cosine_angle))


def calculate_score(distance_cm):
    min_distance = 0
    max_distance = 250
    score = ((distance_cm - min_distance) /
             (max_distance - min_distance)) * 100
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
    help = "Run Broad Jump assessment"

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

        calibration_pixels = None
        pixels_per_cm = None
        calibration_mode = False
        calibration_points = []

        start_position = None
        max_distance = None
        max_distance_cm = None
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
                        f"Point {len(calibration_points)}: ({x}, {y})")

        window_name = "AI Fitness - Broad Jump"
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, mouse_callback)

        self.stdout.write("")
        self.stdout.write("BROAD JUMP ASSESSMENT")
        self.stdout.write("=" * 40)
        self.stdout.write("'k' = calibrate | 'c' = start | 's' = save")
        self.stdout.write("'r' = reset | 'q' = quit")
        self.stdout.write("=" * 40)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            results = model(frame)
            result = results[0]

            shoulder = hip = knee = ankle = None
            side = None

            if result.keypoints is not None:
                keypoints = result.keypoints.data.cpu().numpy()

                if len(keypoints) > 0:
                    person = keypoints[0]

                    ls, lh, lk, la = person[5], person[11], person[13], person[15]
                    rs, rh, rk, ra = person[6], person[12], person[14], person[16]

                    left_valid = all(keypoint_valid(x)
                                     for x in [ls, lh, lk, la])
                    right_valid = all(keypoint_valid(x)
                                      for x in [rs, rh, rk, ra])

                    if selected_side is None:
                        if right_valid:
                            shoulder, hip, knee, ankle = rs, rh, rk, ra
                            side = "Right"
                        elif left_valid:
                            shoulder, hip, knee, ankle = ls, lh, lk, la
                            side = "Left"
                    else:
                        if selected_side == "Right":
                            shoulder, hip, knee, ankle = rs, rh, rk, ra
                            side = "Right"
                            side_valid = right_valid
                        else:
                            shoulder, hip, knee, ankle = ls, lh, lk, la
                            side = "Left"
                            side_valid = left_valid

                        if not side_valid:
                            shoulder = hip = knee = ankle = None

                    if shoulder is not None:
                        draw_keypoint(frame, shoulder, f"{side}-S")
                        draw_keypoint(frame, hip, f"{side}-H")
                        draw_keypoint(frame, knee, f"{side}-K")
                        draw_keypoint(frame, ankle, f"{side}-A")

                        draw_line(frame, shoulder, hip)
                        draw_line(frame, hip, knee)
                        draw_line(frame, knee, ankle)

                        leg_angle = calculate_angle(
                            hip[:2], knee[:2], ankle[:2])
                        legs_straight = leg_angle >= KNEE_STRAIGHT_THRESHOLD

                        cv2.putText(frame, f"Leg: {leg_angle:.1f}",
                                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                        if not legs_straight:
                            cv2.putText(frame, "KEEP LEGS STRAIGHT",
                                        (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                        ankle_x = ankle[0]

                        if state == "CALIBRATING":
                            cv2.putText(frame, "Press 'k' to calibrate",
                                        (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                        elif state == "READY":
                            cv2.putText(frame, "Stand at start, press 'c'",
                                        (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                            if start_position is not None:
                                cv2.line(frame,
                                         (int(start_position), 0),
                                         (int(start_position), frame.shape[0]),
                                         (255, 0, 255), 2)

                        elif state == "JUMPING":
                            if start_position is not None:
                                if side == "Right":
                                    current_distance = ankle_x - start_position
                                else:
                                    current_distance = start_position - ankle_x

                                current_distance = max(0, current_distance)

                                if max_distance is None or current_distance > max_distance:
                                    max_distance = current_distance
                                    if pixels_per_cm:
                                        max_distance_cm = max_distance / pixels_per_cm

                                if pixels_per_cm:
                                    cv2.putText(frame, f"Distance: {(current_distance/pixels_per_cm):.1f} cm",
                                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                                    if max_distance_cm:
                                        cv2.putText(frame, f"Max: {max_distance_cm:.1f} cm",
                                                    (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)

                                cv2.putText(frame, "JUMP!",
                                            (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                        elif state == "COMPLETE":
                            if max_distance_cm:
                                cv2.putText(frame, f"Final: {max_distance_cm:.1f} cm",
                                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                                if final_score:
                                    cv2.putText(frame, f"Score: {final_score:.1f}",
                                                (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                                    cv2.putText(frame, f"{final_result}",
                                                (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                            cv2.putText(frame, "Saved! 'r' for next",
                                        (30, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

                    else:
                        cv2.putText(frame, "Keypoints not visible",
                                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            if calibration_mode:
                cv2.putText(frame, "Click 2 endpoints",
                            (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                for pt in calibration_points:
                    cv2.circle(frame, pt, 7, (0, 0, 255), -1)
                if len(calibration_points) == 2:
                    cv2.line(
                        frame, calibration_points[0], calibration_points[1], (0, 255, 255), 2)

            if pixels_per_cm:
                cv2.putText(frame, f"Scale: {pixels_per_cm:.2f} px/cm",
                            (30, 290), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            cv2.imshow(window_name, frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

            elif key == ord("k"):
                calibration_mode = True
                calibration_points = []
                self.stdout.write("Calibration started")

            elif key == ord("c") and calibration_mode and len(calibration_points) == 2:
                p1 = np.array(calibration_points[0])
                p2 = np.array(calibration_points[1])
                calibration_pixels = np.linalg.norm(p1 - p2)
                known = float(input("Reference length in cm: "))
                if known > 0:
                    pixels_per_cm = calibration_pixels / known
                    calibration_mode = False
                    state = "READY"
                    self.stdout.write(self.style.SUCCESS(
                        f"Scale = {pixels_per_cm:.2f} px/cm"))

            elif key == ord("c") and not calibration_mode and state == "READY":
                if pixels_per_cm and ankle is not None and legs_straight:
                    selected_side = side
                    start_position = ankle[0]
                    max_distance = 0.0
                    max_distance_cm = 0.0
                    state = "JUMPING"
                    self.stdout.write("Jump forward")

            elif key == ord("s"):
                if state == "JUMPING" and max_distance_cm:
                    final_score = calculate_score(max_distance_cm)
                    final_result = get_result(final_score)

                    Assessment.objects.create(
                        athlete=athlete,
                        exercise="Broad Jump",
                        measurement=max_distance_cm,
                        score=final_score,
                        result=final_result,
                    )

                    state = "COMPLETE"

                    self.stdout.write("")
                    self.stdout.write("=" * 40)
                    self.stdout.write(self.style.SUCCESS("COMPLETE"))
                    self.stdout.write(f"Distance: {max_distance_cm:.2f} cm")
                    self.stdout.write(f"Score: {final_score:.2f}/100")
                    self.stdout.write(f"Result: {final_result}")
                    self.stdout.write(self.style.SUCCESS("Saved"))
                    self.stdout.write("=" * 40)

            elif key == ord("r"):
                calibration_pixels = None
                pixels_per_cm = None
                calibration_mode = False
                calibration_points = []
                start_position = None
                max_distance = None
                max_distance_cm = None
                final_score = None
                final_result = None
                state = "CALIBRATING"
                selected_side = None
                legs_straight = False
                self.stdout.write("Reset done")

        cap.release()
        cv2.destroyAllWindows()
