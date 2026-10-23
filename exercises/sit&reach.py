import cv2
import numpy as np
from ultralytics import YOLO


def calculate_angle(a, b, c):  # a = hip, b = knee, c = ankle
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b                      # we got direction from knee to hip
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


MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5


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

# Score calculation function


def calculate_score(reach_cm):
    min_reach_cm = 0
    max_reach_cm = 35
    score = ((reach_cm - min_reach_cm) / (max_reach_cm - min_reach_cm)) * 100
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
cap = cv2.VideoCapture(1)
if not cap.isOpened():
    print("Webcam not found")
    exit()

# sit&reach variables set karenge
KNEE_STRAIGHT_THRESHOLD = 150

# Physical calibration variables
calibration_pixels = None
pixels_per_cm = None
calibration_mode = False
calibration_points = []

# variables
start_position = None
max_reach = None
max_reach_cm = None
final_score = None
final_result = None
state = "CALIBRATING"  # CALIBRATING -> REACHING -> COMPLETE
selected_side = None

print("Sit and Reach assessment started")
print("Step 1: Place a known-length reference object in the frame")
print("Step 2: Press 'k' to start calibration")
print("Step 3: Click two endpoints of the reference object")
print("Step 4: Enter the reference length in cm")
print("Step 5: Sit with legs straight and press 'c' to start")
print("Step 6: Reach forward as far as possible")
print("Press 's' to finish assessment")
print("Press 'r' to reset")
print("Press 'q' to quit")

# ye wala kuch smjh nhin aaya ye mouse callback wala..internet + gpt ne suggest kiya
# Mouse callback for calibration


def mouse_callback(event, x, y, flags, param):
    global calibration_points
    if calibration_mode:
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(calibration_points) < 2:
                calibration_points.append((x, y))
                print(
                    f"Calibration point {len(calibration_points)}: ({x}, {y})")


# Create window with mouse callback
window_name = "AI Fitness - sit & reach assessment"
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

            # Sit & Reach Keypoints
            # left
            left_shoulder = person[5]
            left_hip = person[11]
            left_knee = person[13]
            left_ankle = person[15]
            left_wrist = person[9]

            # right
            right_shoulder = person[6]
            right_hip = person[12]
            right_knee = person[14]
            right_ankle = person[16]
            right_wrist = person[10]

            # Check validity
            left_valid = (
                keypoint_valid(left_shoulder)
                and keypoint_valid(left_hip)
                and keypoint_valid(left_knee)
                and keypoint_valid(left_ankle)
                and keypoint_valid(left_wrist)
            )
            right_valid = (
                keypoint_valid(right_shoulder)
                and keypoint_valid(right_hip)
                and keypoint_valid(right_knee)
                and keypoint_valid(right_ankle)
                and keypoint_valid(right_wrist)
            )

            # Use that side jiski visibility jayda ho...
            # Calculate confidence scores for each side
            left_confidence = (
                left_shoulder[2] + left_hip[2] + left_knee[2] +
                left_ankle[2] + left_wrist[2]
            )
            right_confidence = (
                right_shoulder[2] + right_hip[2] + right_knee[2] +
                right_ankle[2] + right_wrist[2]
            )

            if left_valid and right_valid:
                if right_confidence >= left_confidence:
                    shoulder = right_shoulder
                    hip = right_hip
                    knee = right_knee
                    ankle = right_ankle
                    wrist = right_wrist
                    side = "Right"
                else:
                    shoulder = left_shoulder
                    hip = left_hip
                    knee = left_knee
                    ankle = left_ankle
                    wrist = left_wrist
                    side = "Left"
            elif right_valid:
                shoulder = right_shoulder
                hip = right_hip
                knee = right_knee
                ankle = right_ankle
                wrist = right_wrist
                side = "Right"
            elif left_valid:
                shoulder = left_shoulder
                hip = left_hip
                knee = left_knee
                ankle = left_ankle
                wrist = left_wrist
                side = "Left"
            else:
                shoulder = None
                hip = None
                knee = None
                ankle = None
                wrist = None
                side = None

            if shoulder is not None:
                draw_keypoint(frame, shoulder, f"{side}-Shoulder")
                draw_keypoint(frame, hip, f"{side}-Hip")
                draw_keypoint(frame, knee, f"{side}-Knee")
                draw_keypoint(frame, ankle, f"{side}-Ankle")
                draw_keypoint(frame, wrist, f"{side}-Wrist")

                draw_line(frame, shoulder, hip)
                draw_line(frame, hip, knee)
                draw_line(frame, knee, ankle)
                draw_line(frame, shoulder, wrist, (0, 255, 255))

                leg_angle = calculate_angle(
                    hip[:2],
                    knee[:2],
                    ankle[:2]
                )

                # Wrist aur hip Positions
                wrist_x = wrist[0]
                wrist_y = wrist[1]
                hip_x = hip[0]
                hip_y = hip[1]
                ankle_x = ankle[0]

                # Distance in pixels (horizontal reach from hip)
                reach_pixels = wrist_x - hip_x
                # Vertical distance (to check if hands are at hip lvl)
                vertical_diff = abs(wrist_y - hip_y)

                # Calculate reach in cm if calibrated
                reach_cm = None
                if pixels_per_cm is not None:
                    if side == "Right":
                        reach_pixels_from_ankle = wrist_x - ankle_x
                    else:
                        reach_pixels_from_ankle = ankle_x - wrist_x
                    reach_cm = max(0, reach_pixels_from_ankle / pixels_per_cm)

                # Display leg angle
                cv2.putText(
                    frame,
                    f"Leg Angle: {leg_angle:.1f}",
                    (30, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                )

                # Check if legs are straight enough or not(angle should be more than 150 degrees)
                legs_straight = (
                    leg_angle is not None
                    and leg_angle >= KNEE_STRAIGHT_THRESHOLD
                )

                if not legs_straight:
                    cv2.putText(
                        frame,
                        "WARNING: KEEP LEGS STRAIGHT",
                        (30, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                    )

                # State machine for sit&reach
                if state == "CALIBRATING":
                    cv2.putText(
                        frame,
                        "Press 'c' to calibrate start position",
                        (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2
                    )
                    # Show reach in pixels
                    cv2.putText(
                        frame,
                        f"Reach: {reach_pixels:.1f} px",
                        (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                    )

                elif state == "REACHING":
                    if legs_straight:
                        # Calculate current reach correctly
                        if side == "Right":
                            current_reach = wrist_x - start_position
                        else:
                            current_reach = start_position - wrist_x

                        # Track maximum reach
                        if max_reach is None or current_reach > max_reach:
                            max_reach = current_reach
                            if reach_cm is not None:
                                max_reach_cm = reach_cm

                        # Draw reach line from hip to wrist
                        draw_line(frame, [hip_x, hip_y], [
                            wrist_x, wrist_y], (0, 255, 255))

                        # Display current reach
                        if reach_cm is not None:
                            cv2.putText(
                                frame,
                                f"Current Reach: {reach_cm:.1f} cm",
                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                            )
                            cv2.putText(
                                frame,
                                f"Maximum Reach: {max_reach_cm:.1f} cm",
                                (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                            )
                        else:
                            cv2.putText(
                                frame,
                                f"Current Reach: {current_reach:.1f} px",
                                (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                            )
                            cv2.putText(
                                frame,
                                f"Maximum Reach: {max_reach:.1f} px",
                                (30, 145), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2
                            )

                        # Display state
                        cv2.putText(
                            frame,
                            "State: REACHING",
                            (30, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2
                        )

                        # Display side (jo use kar rhe hain)
                        cv2.putText(
                            frame,
                            f"Using: {side} side",
                            (30, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1
                        )

                        # Guidance text
                        cv2.putText(
                            frame,
                            "Reach forward as far as possible!",
                            (30, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2
                        )

                    else:
                        cv2.putText(
                            frame,
                            "Straighten your legs first!",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2
                        )

                elif state == "COMPLETE":
                    if max_reach_cm is not None:
                        cv2.putText(
                            frame,
                            f"Final Reach: {max_reach_cm:.1f} cm",
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
                    else:
                        cv2.putText(
                            frame,
                            f"Final Reach: {max_reach:.1f} px",
                            (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2
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
            cv2.line(frame, calibration_points[0],
                     calibration_points[1], (0, 255, 255), 2)

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
    if key == ord('q'):
        break

    # Start calibration
    elif key == ord("k"):
        calibration_mode = True
        calibration_points = []
        print("Calibration started. Click the two endpoints of the known reference.")

    # Finish calibration
    elif key == ord("c") and calibration_mode and len(calibration_points) == 2:
        point1 = np.array(calibration_points[0])
        point2 = np.array(calibration_points[1])
        calibration_pixels = np.linalg.norm(point1 - point2)
        print(f"Reference length in image: {calibration_pixels:.2f} pixels")

        try:
            known_length_cm = float(
                input("Enter known reference length in cm: "))
            if known_length_cm <= 0:
                print("Invalid reference length.")
            else:
                pixels_per_cm = calibration_pixels / known_length_cm
                calibration_mode = False
                state = "CALIBRATING"
                print(
                    f"Calibration completed. Scale = {pixels_per_cm:.2f} pixels/cm")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # Start assessment
    elif key == ord("c") and not calibration_mode:
        if pixels_per_cm is None:
            print("Please complete physical calibration first. Press 'k' to start.")
        elif side is None:
            print("Cannot start. Person/keypoints not visible.")
        else:
            start_position = wrist[0]
            max_reach = 0.0
            max_reach_cm = 0.0
            final_score = None
            final_result = None
            state = "REACHING"
            selected_side = side
            print(f"Assessment started using {selected_side} side.")

    # Complete assessment
    elif key == ord("s"):
        if state == "REACHING":
            if max_reach_cm is not None:
                final_score = calculate_score(max_reach_cm)
                final_result = get_result(final_score)
                state = "COMPLETE"
                print("\n" + "="*40)
                print("ASSESSMENT COMPLETE")
                print(f"Maximum Reach: {max_reach_cm:.2f} cm")
                print(f"Score: {final_score:.2f}/100")
                print(f"Result: {final_result}")
                print("="*40)
            elif max_reach is not None:
                # Fallback if no calibration
                print("\n" + "="*40)
                print("ASSESSMENT COMPLETE")
                print(f"Maximum Reach: {max_reach:.2f} px")
                print("(Please calibrate for cm measurement)")
                print("="*40)
            else:
                print("No valid reach measurement recorded.")

    # Reset everything
    elif key == ord("r"):
        calibration_pixels = None
        pixels_per_cm = None
        calibration_mode = False
        calibration_points = []
        start_position = None
        max_reach = None
        max_reach_cm = None
        final_score = None
        final_result = None
        state = "CALIBRATING"
        selected_side = None
        print("Everything reset. Press 'k' to start calibration.")

# Release webcam
cap.release()
cv2.destroyAllWindows()
