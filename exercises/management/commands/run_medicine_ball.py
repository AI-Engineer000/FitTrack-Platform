import math

import cv2
import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from ultralytics import YOLO

from assessments.models import Assessment
from athletes.models import Athlete


MODEL_PATH = "yolo26n.pt"
PERSON_CLASS = 0
SPORTS_BALL_CLASS = 32
CONFIDENCE_THRESHOLD = 0.2
PERSON_MARGIN_PX = 35


def calculate_score(distance_cm, min_distance=0, max_distance=1000):
    if max_distance <= min_distance:
        raise ValueError("max_distance must be greater than min_distance")
    score = (distance_cm - min_distance) / (max_distance - min_distance) * 100
    return round(float(np.clip(score, 0, 100)), 2)


def get_result(score):
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Average"
    return "Needs Improvement"


def choose_ball(ball_boxes, previous_center=None, person_box=None):
    if not ball_boxes:
        return None
    if previous_center is not None:
        return min(
            ball_boxes,
            key=lambda box: math.dist(
                previous_center, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            ),
        )
    if person_box is not None:
        person_center = ((person_box[0] + person_box[2]) / 2,
                         (person_box[1] + person_box[3]) / 2)
        return min(
            ball_boxes,
            key=lambda box: math.dist(
                person_center, ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            ),
        )
    return max(ball_boxes, key=lambda box: box[4])


def is_ball_held(ball_center, person_box):
    if person_box is None:
        return False
    x1, y1, x2, y2 = person_box[:4]
    return (
        x1 - PERSON_MARGIN_PX <= ball_center[0] <= x2 + PERSON_MARGIN_PX
        and y1 - PERSON_MARGIN_PX <= ball_center[1] <= y2 + PERSON_MARGIN_PX
    )


class Command(BaseCommand):
    help = "Run a calibrated medicine ball throw assessment"

    def add_arguments(self, parser):
        parser.add_argument("--athlete-id", type=str)
        parser.add_argument("--camera", type=str, default="")

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
            self.stdout.write(f"Loading YOLO detector {MODEL_PATH}...")
            try:
                model = YOLO(MODEL_PATH)
            except Exception as exc:
                raise CommandError(
                    f"Could not load detector {MODEL_PATH}: {exc}"
                ) from exc

            calibration_points = []
            calibration_mode = False
            pixels_per_cm = None
            state = "CALIBRATING"
            held_center = None
            release_x = None
            previous_ball_center = None
            max_horizontal_px = 0.0
            distance_cm = None
            score = None
            result_text = None
            assessment_saved = False
            window_name = "AI Fitness - Medicine Ball Throw"

            def mouse_callback(event, x, y, flags, param):
                if (calibration_mode and event == cv2.EVENT_LBUTTONDOWN
                        and len(calibration_points) < 2):
                    calibration_points.append((x, y))
                    self.stdout.write(
                        f"Calibration point {len(calibration_points)}: ({x}, {y})"
                    )

            cv2.namedWindow(window_name)
            cv2.setMouseCallback(window_name, mouse_callback)
            self.stdout.write("\nMEDICINE BALL THROW ASSESSMENT")
            self.stdout.write("'k' = calibration mode; click two points on a known length")
            self.stdout.write("'p' = enter known length in cm | 'c' = ready to throw")
            self.stdout.write("'s' = save after landing | 'r' = reset | 'q' = quit")
            self.stdout.write("The person must hold the ball visibly before release.")

            while True:
                ok, frame = cap.read()
                if not ok:
                    self.stderr.write("Could not read a camera frame")
                    break

                try:
                    inference = model(
                        frame, classes=[PERSON_CLASS, SPORTS_BALL_CLASS],
                        verbose=False,
                    )[0]
                except Exception as exc:
                    raise CommandError(f"Object detection failed: {exc}") from exc

                person_boxes = []
                ball_boxes = []
                if inference.boxes is not None:
                    boxes = inference.boxes
                    coordinates = boxes.xyxy.cpu().numpy()
                    classes = boxes.cls.cpu().numpy().astype(int)
                    confidences = boxes.conf.cpu().numpy()
                    for box, class_id, confidence in zip(
                            coordinates, classes, confidences):
                        if confidence < CONFIDENCE_THRESHOLD:
                            continue
                        x1, y1, x2, y2 = map(float, box)
                        detection = (x1, y1, x2, y2, float(confidence))
                        if class_id == PERSON_CLASS:
                            person_boxes.append(detection)
                        elif class_id == SPORTS_BALL_CLASS:
                            ball_boxes.append(detection)

                person_box = max(
                    person_boxes,
                    key=lambda box: (box[2] - box[0]) * (box[3] - box[1]),
                    default=None,
                )
                if person_box is not None:
                    x1, y1, x2, y2 = map(int, person_box[:4])
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 180, 0), 2)
                    cv2.putText(frame, "Person", (x1, max(20, y1 - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 180, 0), 1)

                selected_ball = choose_ball(
                    ball_boxes, previous_ball_center, person_box
                )
                ball_center = None
                if selected_ball is not None:
                    x1, y1, x2, y2 = selected_ball[:4]
                    ball_center = ((x1 + x2) / 2, (y1 + y2) / 2)
                    cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)),
                                  (0, 255, 0), 2)
                    cv2.putText(frame, "Ball", (int(x1), max(20, int(y1) - 8)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

                if state in ("THROWING", "IN_FLIGHT") and ball_center is not None:
                    if release_x is None:
                        if is_ball_held(ball_center, person_box):
                            held_center = ball_center
                        elif held_center is not None:
                            release_x = held_center[0]
                            max_horizontal_px = abs(ball_center[0] - release_x)
                            state = "IN_FLIGHT"
                    else:
                        max_horizontal_px = max(
                            max_horizontal_px, abs(ball_center[0] - release_x)
                        )
                    previous_ball_center = ball_center

                if calibration_mode:
                    status = f"Calibration points: {len(calibration_points)}/2; click endpoints"
                elif pixels_per_cm is None:
                    status = "Press 'k' to calibrate using a known length"
                elif state == "CALIBRATING":
                    status = f"Calibrated: {pixels_per_cm:.2f} px/cm | press 'c'"
                elif state == "READY":
                    status = "Hold ball in view, then press 'c' to arm tracking"
                elif state in ("THROWING", "IN_FLIGHT"):
                    if release_x is None:
                        status = "Tracking ball near athlete; waiting for release"
                    else:
                        live_cm = max_horizontal_px / pixels_per_cm
                        status = f"Ball in flight | distance so far: {live_cm:.1f} cm"
                else:
                    status = f"Saved: {distance_cm:.1f} cm | score {score:.1f}/100"
                    cv2.putText(frame, "Saved - press 'r' for another throw", (30, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

                if pixels_per_cm and release_x is not None and ball_center is not None:
                    cv2.line(frame, (int(release_x), int(ball_center[1])),
                             (int(ball_center[0]), int(ball_center[1])),
                             (0, 255, 255), 2)
                for point in calibration_points:
                    cv2.circle(frame, point, 5, (255, 0, 255), -1)
                cv2.putText(frame, status, (20, 30), cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (255, 255, 0), 2)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF

                if key == ord("q"):
                    break
                if key == ord("k") and pixels_per_cm is None:
                    calibration_mode = True
                    calibration_points.clear()
                elif key == ord("p") and calibration_mode:
                    if len(calibration_points) != 2:
                        self.stdout.write(self.style.WARNING(
                            "Click exactly two calibration endpoints first"
                        ))
                        continue
                    pixel_length = math.dist(*calibration_points)
                    if pixel_length <= 0:
                        self.stdout.write(self.style.WARNING(
                            "Choose two different calibration points"
                        ))
                        continue
                    try:
                        known_length_cm = float(input(
                            "Known distance between calibration points (cm): "
                        ))
                    except (ValueError, EOFError) as exc:
                        raise CommandError("Enter a valid calibration length") from exc
                    if known_length_cm <= 0:
                        raise CommandError("Calibration length must be positive")
                    pixels_per_cm = pixel_length / known_length_cm
                    calibration_mode = False
                    state = "CALIBRATING"
                    self.stdout.write(self.style.SUCCESS(
                        f"Calibration set: {pixels_per_cm:.2f} px/cm"
                    ))
                elif key == ord("c") and pixels_per_cm is not None and state in (
                        "CALIBRATING", "READY"):
                    held_center = None
                    release_x = None
                    previous_ball_center = None
                    max_horizontal_px = 0.0
                    state = "THROWING"
                    assessment_saved = False
                elif key == ord("s") and state == "IN_FLIGHT" and not assessment_saved:
                    distance_cm = max_horizontal_px / pixels_per_cm
                    score = calculate_score(distance_cm)
                    result_text = get_result(score)
                    Assessment.objects.create(
                        athlete=athlete,
                        exercise="Medicine Ball Throw",
                        measurement=round(distance_cm, 2),
                        score=score,
                        result=result_text,
                    )
                    assessment_saved = True
                    state = "COMPLETE"
                    self.stdout.write(self.style.SUCCESS(
                        f"Saved: {distance_cm:.1f} cm, score {score:.1f}/100 "
                        f"({result_text})"
                    ))
                elif key == ord("r"):
                    state = "CALIBRATING" if pixels_per_cm is None else "READY"
                    held_center = None
                    release_x = None
                    previous_ball_center = None
                    max_horizontal_px = 0.0
                    distance_cm = score = result_text = None
                    assessment_saved = False
        finally:
            cap.release()
            cv2.destroyAllWindows()
