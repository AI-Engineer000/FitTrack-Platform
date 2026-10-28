from dashboard.live_analysis import analyze_exercise, estimate_pixels_per_cm


def _kp(x, y, conf=0.9):
    return [x, y, conf]


def test_pixels_per_cm_uses_nose_to_lowest_confident_ankle():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[0] = _kp(320, 100)
    keypoints[15] = _kp(305, 410)
    keypoints[16] = _kp(335, 440)

    assert estimate_pixels_per_cm(keypoints) == 2.0


def test_vertical_jump_uses_ankle_height_and_returns_measurement():
    keypoints = [[320, 120, 0.9]] + [[0, 0, 0.0] for _ in range(16)]
    keypoints[5] = _kp(300, 190)
    keypoints[6] = _kp(340, 190)
    keypoints[11] = _kp(300, 240)
    keypoints[12] = _kp(340, 240)
    keypoints[13] = _kp(300, 300)
    keypoints[14] = _kp(340, 300)
    keypoints[15] = _kp(305, 420)
    keypoints[16] = _kp(335, 420)

    result = analyze_exercise(
        "vertical-jump", keypoints, {"pixels_per_cm": 2.0})

    assert result["valid"] is True
    assert result["unit"] == "cm"
    assert result["current_value"] >= 0


def test_sit_reach_uses_wrist_without_name_error():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[9] = _kp(200, 150)
    keypoints[10] = _kp(250, 150)
    keypoints[11] = _kp(220, 220)
    keypoints[12] = _kp(260, 220)

    result = analyze_exercise("sit-reach", keypoints, {"start_x": 100.0})

    assert result["valid"] is True
    assert result["state"]["reach_px"] > 0


def test_sprint_tracks_movement_finish_and_elapsed_time():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[15] = _kp(100, 400)
    keypoints[16] = _kp(110, 400)
    state = {"pixels_per_cm": 1.0, "now": 1.0}

    ready = analyze_exercise("sprint", keypoints, state)
    assert ready["state_label"] == "READY"

    keypoints[15] = _kp(125, 400)
    keypoints[16] = _kp(135, 400)
    state = {**ready["state"], "now": 2.0}
    running = analyze_exercise("sprint", keypoints, state)
    assert running["state_label"] == "RUNNING"

    keypoints[15] = _kp(310, 400)
    keypoints[16] = _kp(320, 400)
    state = {**running["state"], "now": 4.5}
    finished = analyze_exercise("sprint", keypoints, state)

    assert finished["state_label"] == "FINISHED"
    assert finished["current_value"] == 2.5
    assert finished["state"]["elapsed_sec"] == 2.5
