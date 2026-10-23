import cv2
import numpy as np
from ultralytics import YOLO


def calculate_angle(a, b, c):  # a= hip, b = knee, c = ankle
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b                      # using this we got the direction from knee to ankle
    dot_product = np.dot(ba, bc)    # yaha se dotproduct aayega
    # yaha se magnitude (FIXED: linalg not linealg)
    norm_ba = np.linalg.norm(ba)
    # yaha se magnitude (FIXED: linalg not linealg)
    norm_bc = np.linalg.norm(bc)
    if norm_ba == 0 or norm_bc == 0:        # Case - magnitude zero hogya
        raise ValueError("Cannot calculate angle with a zero vector.")
    # cos theta ka formula lagaya
    cosine_angle = dot_product / (norm_ba * norm_bc)  # cos theta ka formula
    # keeps value between -1 & 1
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle_radians = np.arccos(cosine_angle)  # radians m
    angle_degrees = np.degrees(angle_radians)  # degrees m convert
    return angle_degrees  # FIXED: Return the angle


# Load the pose model
MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5

# Broad Jump actual settings.. will be adjusted after actual testing
KNEE_STRAIGHT_THRESHOLD = 150

# checking kyepoint confidence


def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


# DRAW a keypoint
def draw_keypoint(frame, keypoint, label):
    x = int(keypoint[0])
    y = int(keypoint[1])
    # syntax - cv2.circle(img, center, radius, color, thickness=None, lineType=None, shift=None)
    cv2.circle(frame, (x, y), 7, (0, 255, 0), 1)
    cv2.putText(
        frame,
        label,
        (x+8, y-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
        # white color - RGB(255,255,255)
    )


# fxn of DRAW BODY SEGMENTS
def draw_line(frame, point1, point2, color=(255, 255, 255)):
    x1, y1 = int(point1[0]), int(point1[1])
    x2, y2 = int(point2[0]), int(point2[1])
    cv2.line(frame, (x1, y1), (x2, y2), color, 2)


# Score calculation fxn
def calculate_score(distance_cm):
    min_distance_cm = 0
    max_distance_cm = 250  # Max broad jump distance

    score = (
        (distance_cm - min_distance_cm)
        / (max_distance_cm - min_distance_cm)
    ) * 100

    score = np.clip(score, 0, 100)

    return score


# Result classification
def get_result(score):
    if score >= 80:
        return "EXCELLENT"
    elif score >= 60:
        return "GOOD"
    elif score >= 40:
        return "AVERAGE"
    else:
        return "NEEDS IMPROVEMENT"


# model loading
model = YOLO(MODEL_PATH)
# open laptop webcam
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("Webcam not found")
    exit()
# Physical calibration variables
calibration_pixels = None
pixels_per_cm = None
calibration_mode = False
calibration_points = []

# Broad Jump variables
start_position = None
max_distance = None
max_distance_cm = None
final_score = None
final_result = None
state = "CALIBRATING"  # CALIBRATING -> READY -> JUMPING -> COMPLETE
selected_side = None
legs_straight = False

print("Broad Jump assessment started")
print("Step 1: Place a known-length reference object in the frame")
print("Step 2: Press 'k' to start calibration")
print("Step 3: Click two endpoints of the reference object")
print("Step 4: Enter the reference length in cm")
print("Step 5: Stand at start line and press 'c' to start")
print("Step 6: Jump forward as far as possible")
print("Press 's' to finish assessment")
print("Press 'r' to reset")
print("Press 'q' to quit")


# Mouse callback for calibration
def mouse_callback(event, x, y, flags, param):
    global calibration_points
    if calibration_mode:
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(calibration_points) < 2:
                calibration_points.append((x, y))
                print(
                    f"Calibration point {len(calibration_points)}: ({x}, {y})"
                )


# Create window with mouse callback
window_name = "AI Fitness - Broad Jump Assessment"
cv2.namedWindow(window_name)
cv2.setMouseCallback(window_name, mouse_callback)


while True:
    ret, frame = cap.read()

    if not ret:
        print("Couldn't read webcam frame")
        break

    results = model(frame)
    result = results[0]

    if result.keypoints is not None:
        keypoints = result.keypoints.data.cpu().numpy()

        if len(keypoints) > 0:
            person = keypoints[0]
            # Broad Jump keypoints
            # left
            left_shoulder = person[5]
            left_hip = person[11]
            left_knee = person[13]
            left_ankle = person[15]
            # right
            right_shoulder = person[6]
            right_hip = person[12]
            right_knee = person[14]
            right_ankle = person[16]
            # Check left side
            left_valid = (
                keypoint_valid(left_shoulder)
                and keypoint_valid(left_hip)
                and keypoint_valid(left_knee)
                and keypoint_valid(left_ankle)
            )
            # Check right side
            right_valid = (
                keypoint_valid(right_shoulder)
                and keypoint_valid(right_hip)
                and keypoint_valid(right_knee)
                and keypoint_valid(right_ankle)
            )
            # Calculate confidence scores for each side
            left_confidence = (
                left_shoulder[2]
                + left_hip[2]
                + left_knee[2]
                + left_ankle[2]
            )
            right_confidence = (
                right_shoulder[2]
                + right_hip[2]
                + right_knee[2]
                + right_ankle[2]
            )

            # Use that side jiski visibility jayda ho...
            if selected_side is None:
                if left_valid and right_valid:
                    if right_confidence >= left_confidence:
                        shoulder = right_shoulder
                        hip = right_hip
                        knee = right_knee
                        ankle = right_ankle
                        side = "Right"
                    else:
                        shoulder = left_shoulder
                        hip = left_hip
                        knee = left_knee
                        ankle = left_ankle
                        side = "Left"

                elif right_valid:
                    shoulder = right_shoulder
                    hip = right_hip
                    knee = right_knee
                    ankle = right_ankle
                    side = "Right"

                elif left_valid:
                    shoulder = left_shoulder
                    hip = left_hip
                    knee = left_knee
                    ankle = left_ankle
                    side = "Left"

                else:
                    shoulder = None
                    hip = None
                    knee = None
                    ankle = None
                    side = None

            else:
                if selected_side == "Right":
                    shoulder = right_shoulder
                    hip = right_hip
                    knee = right_knee
                    ankle = right_ankle
                    side = "Right"
                    side_valid = right_valid

                else:
                    shoulder = left_shoulder
                    hip = left_hip
                    knee = left_knee
                    ankle = left_ankle
                    side = "Left"
                    side_valid = left_valid

                if not side_valid:
                    shoulder = None
                    hip = None
                    knee = None
                    ankle = None

            if shoulder is not None:
                draw_keypoint(frame, shoulder, f"{side}-Shoulder")
                draw_keypoint(frame, hip, f"{side}-Hip")
                draw_keypoint(frame, knee, f"{side}-Knee")
                draw_keypoint(frame, ankle, f"{side}-Ankle")

                draw_line(frame, shoulder, hip)
                draw_line(frame, hip, knee)
                draw_line(frame, knee, ankle)

                # Check knee angle (to ensure proper form)
                leg_angle = calculate_angle(
                    hip[:2],
                    knee[:2],
                    ankle[:2]
                )

                # Display leg angle
                cv2.putText(
                    frame,
                    f"Leg Angle: {leg_angle:.1f}",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                )

                legs_straight = (
                    leg_angle >= KNEE_STRAIGHT_THRESHOLD
                )

                if not legs_straight:
                    cv2.putText(
                        frame,
                        "WARNING: KEEP LEGS STRAIGHT",
                        (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                    )

                ankle_x = ankle[0]
                ankle_y = ankle[1]

                # State machine for broad jump
                if state == "CALIBRATING":
                    cv2.putText(
                        frame,
                        "Press 'k' to calibrate",
                        (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                    )

                elif state == "READY":
                    cv2.putText(
                        frame,
                        "Stand at start line and press 'c'",
                        (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                    )

                    # Show start position line
                    if start_position is not None:
                        cv2.line(
                            frame,
                            (int(start_position), 0),
                            (int(start_position), frame.shape[0]),
                            (255, 0, 255),
                            2
                        )
                        cv2.putText(
                            frame,
                            "Start Line",
                            (int(start_position) - 30, 30),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (255, 0, 255),
                            2
                        )

                    cv2.putText(
                        frame,
                        f"Using: {selected_side} side",
                        (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                    )

                elif state == "JUMPING":
                    # Calculate horizontal displacement from start
                    current_distance = ankle_x - start_position
                    current_distance = max(0, current_distance)

                    # Track maximum distance
                    if max_distance is None or current_distance > max_distance:
                        max_distance = current_distance

                        if pixels_per_cm is not None:
                            max_distance_cm = max_distance / pixels_per_cm

                    # Draw start line
                    cv2.line(
                        frame,
                        (int(start_position), 0),
                        (int(start_position), frame.shape[0]),
                        (255, 0, 255),
                        2
                    )

                    # Draw measurement line from start to ankle
                    cv2.line(
                        frame,
                        (int(start_position), int(ankle_y)),
                        (int(ankle_x), int(ankle_y)),
                        (0, 255, 255),
                        3
                    )

                    # Display current distance
                    if pixels_per_cm is not None:
                        current_distance_cm = current_distance / pixels_per_cm

                        cv2.putText(
                            frame,
                            f"Current Distance: {current_distance_cm:.1f} cm",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                        )

                        cv2.putText(
                            frame,
                            f"Maximum Distance: {max_distance_cm:.1f} cm",
                            (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                        )

                    else:
                        cv2.putText(
                            frame,
                            f"Current Distance: {current_distance:.1f} px",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                        )

                        cv2.putText(
                            frame,
                            f"Maximum Distance: {max_distance:.1f} px",
                            (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                        )

                    cv2.putText(
                        frame,
                        "State: JUMPING",
                        (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                    )

                    cv2.putText(
                        frame,
                        f"Using: {selected_side} side",
                        (30, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2
                    )

                    cv2.putText(
                        frame,
                        "Jump forward as far as possible!",
                        (30, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                    )

                elif state == "COMPLETE":
                    if max_distance_cm is not None:
                        cv2.putText(
                            frame,
                            f"Final Distance: {max_distance_cm:.1f} cm",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
                        )

                        cv2.putText(
                            frame,
                            f"Score: {final_score:.1f}/100",
                            (30, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
                        )

                        cv2.putText(
                            frame,
                            f"Result: {final_result}",
                            (30, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
                        )

                    cv2.putText(
                        frame,
                        "Press 'r' to reset for next athlete",
                        (30, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                    )

            else:
                cv2.putText(
                    frame,
                    "Adjust camera - keypoints unclean",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                )

        else:
            cv2.putText(
                frame,
                "No person detected",
                (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
            )

    else:
        cv2.putText(
            frame,
            "no pose keypoints detected",
            (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
        )

    # Draw calibration points on frame
    if calibration_mode:
        cv2.putText(
            frame,
            "Click two endpoints of known reference",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 255),
            2
        )

        for point in calibration_points:
            cv2.circle(frame, point, 7, (0, 0, 255), -1)

        if len(calibration_points) == 2:
            cv2.line(
                frame,
                calibration_points[0],
                calibration_points[1],
                (0, 255, 255),
                2
            )

    # Display calibration information
    if pixels_per_cm is not None:
        cv2.putText(
            frame,
            f"Scale: {pixels_per_cm:.2f} px/cm",
            (30, 290),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            2
        )

    # Show webcam frame
    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    # Start calibration
    elif key == ord("k"):
        calibration_mode = True
        calibration_points = []

        print(
            "Calibration started. Click the two endpoints of the known reference."
        )

    # Finish calibration
    elif (
        key == ord("c")
        and calibration_mode
        and len(calibration_points) == 2
    ):
        point1 = np.array(calibration_points[0])
        point2 = np.array(calibration_points[1])

        calibration_pixels = np.linalg.norm(point1 - point2)

        print(
            f"Reference length in image: "
            f"{calibration_pixels:.2f} pixels"
        )

        try:
            known_length_cm = float(
                input("Enter known reference length in cm: ")
            )

            if known_length_cm <= 0:
                print("Invalid reference length.")

            else:
                pixels_per_cm = (
                    calibration_pixels / known_length_cm
                )

                calibration_mode = False
                state = "READY"

                print(
                    f"Calibration completed. "
                    f"Scale = {pixels_per_cm:.2f} pixels/cm"
                )

        except ValueError:
            print("Invalid input. Please enter a number.")

    # Start assessment
    elif (
        key == ord("c")
        and not calibration_mode
        and state == "READY"
    ):
        if pixels_per_cm is None:
            print(
                "Please complete physical calibration first. "
                "Press 'k' to start."
            )

        elif side is None:
            print(
                "Cannot start. Person/keypoints not visible."
            )

        elif not legs_straight:
            print(
                "Please stand straight first."
            )

        else:
            selected_side = side
            start_position = ankle_x

            max_distance = 0.0
            max_distance_cm = 0.0

            final_score = None
            final_result = None

            state = "JUMPING"

            print(
                f"Assessment started using {selected_side} side."
            )
            print(
                f"Start position: "
                f"{start_position:.2f} pixels"
            )

    # Complete assessment
    elif key == ord("s"):
        if state == "JUMPING":
            if max_distance_cm is not None:
                final_score = calculate_score(max_distance_cm)
                final_result = get_result(final_score)

                state = "COMPLETE"

                print("\n" + "=" * 40)
                print("ASSESSMENT COMPLETE")
                print(
                    f"Maximum Distance: "
                    f"{max_distance_cm:.2f} cm"
                )
                print(
                    f"Score: {final_score:.2f}/100"
                )
                print(
                    f"Result: {final_result}"
                )
                print("=" * 40)

            elif max_distance is not None:
                print("\n" + "=" * 40)
                print("ASSESSMENT COMPLETE")
                print(
                    f"Maximum Distance: "
                    f"{max_distance:.2f} px"
                )
                print(
                    "(Please calibrate for cm measurement)"
                )
                print("=" * 40)

            else:
                print(
                    "No valid jump measurement recorded."
                )

    # Reset everything
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

        print(
            "Everything reset. Press 'k' to start calibration."
        )


# Release webcam
cap.release()
cv2.destroyAllWindows()
