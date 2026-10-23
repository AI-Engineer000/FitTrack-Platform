import cv2
from ultralytics import YOLO
import numpy as np


def calculate_angle(a, b, c):  # a = hip, b = knee, c = ankle
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
    cosine_angle = dot_product / (norm_ba * norm_bc)
    # keeps value between -1 & 1
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle_radians = np.arccos(cosine_angle)  # radians m
    angle_degrees = np.degrees(angle_radians)  # degrees m convert
    return angle_degrees  # FIXED: Return the angle


# Load the pose model
MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5
# Vertical Jump actual settings.. will be adjusted after actual testing
KNEE_STRAIGHT_THRESHOLD = 160
# checking keypoint confidence


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
        (x+8, y-8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
        # white color - RGB(255,255,255)
    )
# fxn of DRAW BODY SEGMENTS


def draw_line(frame, point1, point2, color=(255, 255, 255)):
    x1, y1 = int(point1[0]), int(point1[1])
    x2, y2 = int(point2[0]), int(point2[1])
    cv2.line(frame, (x1, y1), (x2, y2), color, 2)


# model loading
model = YOLO(MODEL_PATH)
# open laptop webcam
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("Webcam not found")
    exit()
# Vertical Jump variables
standing_position = None
max_jump = None
state = "READY"  # READY -> JUMPING -> COMPLETE
selected_side = None
legs_straight = False

print("Vertical Jump assessment started")
print("Step 1: Stand straight")
print("Step 2: Press 'c' to save standing position and start")
print("Step 3: Jump as high as possible")
print("Press 's' to finish assessment")
print("Press 'r' to reset")
print("Press 'q' to quit")

# Create window
window_name = "AI Fitness - Vertical Jump Assessment"
cv2.namedWindow(window_name)
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
            # Vertical Jump keypoints
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

                # Draw keypoints
                draw_keypoint(
                    frame, shoulder, f"{side}-Shoulder"
                )

                draw_keypoint(
                    frame, hip, f"{side}-Hip"
                )

                draw_keypoint(
                    frame, knee, f"{side}-Knee"
                )

                draw_keypoint(
                    frame, ankle, f"{side}-Ankle"
                )

                # Draw body segments
                draw_line(frame, shoulder, hip)
                draw_line(frame, hip, knee)
                draw_line(frame, knee, ankle)
                # Calculate knee angle
                leg_angle = calculate_angle(
                    hip[:2],
                    knee[:2],
                    ankle[:2]
                )

                # Display leg angle
                cv2.putText(
                    frame,
                    f"Leg Angle: {leg_angle:.1f}",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2
                )
                # Check whether legs are straight
                legs_straight = (
                    leg_angle >= KNEE_STRAIGHT_THRESHOLD
                )
                if not legs_straight:

                    cv2.putText(
                        frame,
                        "WARNING: KEEP LEGS STRAIGHT",
                        (30, 75),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 0, 255),
                        2
                    )
                ankle_y = ankle[1]
                # State machine for vertical jump
                if state == "READY":
                    cv2.putText(
                        frame,
                        "Stand straight and press 'c'",
                        (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )
                    cv2.putText(
                        frame,
                        f"Using: {side} side",
                        (30, 145),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )
                elif state == "JUMPING":
                    # Calculate upward displacement
                    current_jump = standing_position - ankle_y
                    # Negative value ko zero kar denge
                    current_jump = max(0, current_jump)
                    # Track maximum jump
                    if max_jump is None or current_jump > max_jump:
                        max_jump = current_jump
                    # Draw standing baseline
                    cv2.line(
                        frame,
                        (0, int(standing_position)),
                        (frame.shape[1], int(standing_position)),
                        (255, 0, 255),
                        2
                    )
                    # Draw vertical jump line
                    cv2.line(
                        frame,
                        (int(ankle[0]), int(standing_position)),
                        (int(ankle[0]), int(ankle_y)),
                        (0, 255, 255),
                        3
                    )
                    # Display current jump
                    cv2.putText(
                        frame,
                        f"Current Jump: {current_jump:.1f} px",
                        (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )
                    # Display maximum jump
                    cv2.putText(
                        frame,
                        f"Maximum Jump: {max_jump:.1f} px",
                        (30, 145),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 255),
                        2
                    )

                    # Display state
                    cv2.putText(
                        frame,
                        "State: JUMPING",
                        (30, 180),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                    # Display selected side
                    cv2.putText(
                        frame,
                        f"Using: {selected_side} side",
                        (30, 215),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 255, 255),
                        2
                    )

                    # Guidance text
                    cv2.putText(
                        frame,
                        "Jump as high as possible!",
                        (30, 250),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 255),
                        2
                    )

                elif state == "COMPLETE":

                    cv2.putText(
                        frame,
                        f"Final Jump Height: {max_jump:.1f} px",
                        (30, 110),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        "Assessment Complete",
                        (30, 150),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        "Press 'r' to reset for next athlete",
                        (30, 190),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )

            else:

                cv2.putText(
                    frame,
                    "Adjust camera - keypoints unclean",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 0, 255),
                    2
                )

        else:

            cv2.putText(
                frame,
                "No person detected",
                (30, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

    else:

        cv2.putText(
            frame,
            "no pose keypoints detected",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

    # Show webcam frame
    cv2.imshow(window_name, frame)

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q"):
        break

    # Start assessment
    elif key == ord("c"):

        if side is None:

            print("Cannot start. Person/keypoints not visible.")

        elif not legs_straight:

            print("Please stand straight first.")

        else:
            selected_side = side
            standing_position = ankle[1]
            max_jump = 0.0
            state = "JUMPING"
            print(f"Assessment started using {selected_side} side.")

            print(
                f"Standing position: "
                f"{standing_position:.2f} pixels"
            )

    # Complete assessment
    elif key == ord("s"):

        if state == "JUMPING":
            if max_jump is not None:
                state = "COMPLETE"
                print("\n" + "=" * 40)
                print("ASSESSMENT COMPLETE")
                print(
                    f"Maximum Jump Height: "
                    f"{max_jump:.2f} pixels"
                )
                print(
                    "Physical cm conversion will be added later."
                )
                print("=" * 40)

            else:

                print(
                    "No valid jump measurement recorded."
                )

    # Reset everything
    elif key == ord("r"):

        standing_position = None
        max_jump = None
        state = "READY"
        selected_side = None
        legs_straight = False

        print(
            "Reset completed. Stand straight and press 'c' to start."
        )


# Release webcam
cap.release()
cv2.destroyAllWindows()
