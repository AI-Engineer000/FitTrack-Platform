import cv2
import time
import numpy as np
from ultralytics import YOLO


# Load the pose model
MODEL_PATH = "yolo26n-pose.pt"
CONFIDENCE_THRESHOLD = 0.5


# Sprint timing settings
MIN_TIME = 3.0
MAX_TIME = 15.0


# checking keypoint confidence
def keypoint_valid(keypoint):
    return keypoint[2] >= CONFIDENCE_THRESHOLD


# DRAW a keypoint
def draw_keypoint(frame, keypoint, label):
    x = int(keypoint[0])
    y = int(keypoint[1])

    cv2.circle(
        frame,
        (x, y),
        7,
        (0, 255, 0),
        1
    )

    cv2.putText(
        frame,
        label,
        (x + 8, y - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.5,
        (255, 255, 255),
        1
    )


# Score calculation function
def calculate_score(time_seconds):

    # Lower time = better performance
    best_time = 4.0
    worst_time = 10.0

    score = (
        (worst_time - time_seconds)
        / (worst_time - best_time)
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


# Sprint variables
start_line = None
finish_line = None

start_time = None
finish_time = None

sprint_time = None
final_score = None
final_result = None

state = "SETUP"
# SETUP -> READY -> RUNNING -> COMPLETE


selected_side = None


# Create window
window_name = "AI Fitness - 30m Sprint Assessment"

cv2.namedWindow(window_name)


while True:

    ret, frame = cap.read()

    if not ret:
        break

    results = model(frame)

    result = results[0]

    # Default values
    shoulder = None
    hip = None
    knee = None
    ankle = None
    side = None

    ankle_x = None

    if result.keypoints is not None:

        keypoints = result.keypoints.data.cpu().numpy()

        if len(keypoints) > 0:

            person = keypoints[0]

            # Left side
            left_shoulder = person[5]
            left_hip = person[11]
            left_knee = person[13]
            left_ankle = person[15]

            # Right side
            right_shoulder = person[6]
            right_hip = person[12]
            right_knee = person[14]
            right_ankle = person[16]

            # Check left ankle
            left_ankle_valid = keypoint_valid(left_ankle)

            # Check right ankle
            right_ankle_valid = keypoint_valid(right_ankle)

            # Select the ankle with better confidence
            if left_ankle_valid and right_ankle_valid:

                if left_ankle[2] >= right_ankle[2]:

                    ankle = left_ankle
                    shoulder = left_shoulder
                    hip = left_hip
                    knee = left_knee
                    side = "Left"

                else:

                    ankle = right_ankle
                    shoulder = right_shoulder
                    hip = right_hip
                    knee = right_knee
                    side = "Right"

            elif left_ankle_valid:

                ankle = left_ankle
                shoulder = left_shoulder
                hip = left_hip
                knee = left_knee
                side = "Left"

            elif right_ankle_valid:

                ankle = right_ankle
                shoulder = right_shoulder
                hip = right_hip
                knee = right_knee
                side = "Right"

            # Draw detected ankle
            if ankle is not None:

                draw_keypoint(
                    frame,
                    ankle,
                    f"{side}-Ankle"
                )

                # Draw body points if valid
                if keypoint_valid(hip):

                    draw_keypoint(
                        frame,
                        hip,
                        f"{side}-Hip"
                    )

                if keypoint_valid(knee):

                    draw_keypoint(
                        frame,
                        knee,
                        f"{side}-Knee"
                    )

                # Current ankle position
                ankle_x = ankle[0]

                # ------------------------------------------------
                # SETUP STATE
                # ------------------------------------------------

                if state == "SETUP":

                    cv2.putText(
                        frame,
                        "Press 'k' = START LINE",
                        (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        "Press 'f' = FINISH LINE",
                        (30, 75),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )

                # ------------------------------------------------
                # READY STATE
                # ------------------------------------------------

                elif state == "READY":

                    cv2.putText(
                        frame,
                        "Athlete ready - Press 'c' to start",
                        (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )

                # ------------------------------------------------
                # RUNNING STATE
                # ------------------------------------------------

                elif state == "RUNNING":

                    current_time = time.time()

                    elapsed_time = current_time - start_time

                    # Stop if athlete crosses finish line
                    if ankle_x >= finish_line:

                        finish_time = current_time

                        sprint_time = (
                            finish_time - start_time
                        )

                        final_score = calculate_score(
                            sprint_time
                        )

                        final_result = get_result(
                            final_score
                        )

                        state = "COMPLETE"

                    else:

                        cv2.putText(
                            frame,
                            f"Time: {elapsed_time:.2f} sec",
                            (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0, 255, 255),
                            2
                        )

                        cv2.putText(
                            frame,
                            "RUN!",
                            (30, 80),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.8,
                            (0, 255, 0),
                            2
                        )

                # ------------------------------------------------
                # COMPLETE STATE
                # ------------------------------------------------

                elif state == "COMPLETE":

                    cv2.putText(
                        frame,
                        f"30m Sprint Time: {sprint_time:.2f} sec",
                        (30, 40),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"Score: {final_score:.1f}/100",
                        (30, 80),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        f"Result: {final_result}",
                        (30, 120),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.8,
                        (0, 255, 0),
                        2
                    )

                    cv2.putText(
                        frame,
                        "Press 'r' for next athlete",
                        (30, 160),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (255, 255, 0),
                        2
                    )

    else:

        cv2.putText(
            frame,
            "No pose keypoints detected",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2
        )

    # ------------------------------------------------
    # DRAW START LINE
    # ------------------------------------------------

    if start_line is not None:

        cv2.line(
            frame,
            (int(start_line), 0),
            (int(start_line), frame.shape[0]),
            (255, 0, 255),
            2
        )

        cv2.putText(
            frame,
            "START",
            (int(start_line) - 30, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 0, 255),
            2
        )

    # ------------------------------------------------
    # DRAW FINISH LINE
    # ------------------------------------------------

    if finish_line is not None:

        cv2.line(
            frame,
            (int(finish_line), 0),
            (int(finish_line), frame.shape[0]),
            (0, 255, 255),
            2
        )

        cv2.putText(
            frame,
            "FINISH",
            (int(finish_line) - 35, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 255),
            2
        )

    # Show webcam frame
    cv2.imshow(
        window_name,
        frame
    )

    key = cv2.waitKey(1) & 0xFF

    # Quit
    if key == ord("q"):

        break

    # Set START line
    elif key == ord("k"):

        if ankle_x is not None:

            start_line = int(ankle_x)

        else:

            pass

    # Set FINISH line
    elif key == ord("f"):

        if ankle_x is not None:

            finish_line = int(ankle_x)

            state = "READY"

        else:

            pass

    # Start assessment
    elif key == ord("c"):

        if state == "READY":

            if ankle_x is None:

                pass

            else:

                selected_side = side

                start_time = time.time()

                finish_time = None

                sprint_time = None

                final_score = None

                final_result = None

                state = "RUNNING"

    # Reset
    elif key == ord("r"):

        start_time = None
        finish_time = None

        sprint_time = None

        final_score = None
        final_result = None

        selected_side = None

        # Lines ko preserve karo - sirf timer reset karo
        if start_line is not None and finish_line is not None:

            state = "READY"

        else:

            state = "SETUP"

    # Clear lines
    elif key == ord("l"):

        start_line = None
        finish_line = None

        state = "SETUP"


# Release webcam
cap.release()

cv2.destroyAllWindows()
