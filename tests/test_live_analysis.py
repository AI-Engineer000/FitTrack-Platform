import numpy as np

from dashboard.live_analysis import analyze_exercise, estimate_pixels_per_cm


def _kp(x, y, conf=0.9):
    return [x, y, conf]


def _situp_keypoints(angle, confidence=0.9):
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    hip_x, hip_y, segment_length = 100.0, 100.0, 100.0
    radians = np.radians(angle)
    shoulder = [
        hip_x - segment_length * np.sin(radians),
        hip_y + segment_length * np.cos(radians),
        confidence,
    ]
    hip = [hip_x, hip_y, confidence]
    knee = [hip_x, hip_y + segment_length, confidence]
    for index in (5, 6):
        keypoints[index] = shoulder
    for index in (11, 12):
        keypoints[index] = hip
    for index in (13, 14):
        keypoints[index] = knee
    return keypoints


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


def test_situp_counts_one_complete_bottom_top_bottom_cycle():
    state = {}
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in (160, 90, 160)
    ]

    assert [result["max_value"] for result in results] == [0, 0, 1]
    assert results[-1]["state"]["situp_phase"] == "bottom"


def test_situp_counts_five_complete_cycles():
    state = {}
    angles = [160] + [angle for _ in range(5) for angle in (90, 160)]
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in angles
    ]

    assert results[-1]["max_value"] == 5


def test_situp_does_not_count_an_incomplete_cycle_or_start_at_the_top():
    state = {}
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in (90, 160, 160)
    ]

    assert results[-1]["max_value"] == 0
    assert results[-1]["state"]["situp_phase"] == "bottom"


def test_situp_holding_top_or_bottom_does_not_duplicate_reps():
    state = {}
    angles = [160, 90, 90, 90, 160, 160, 160]
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in angles
    ]

    assert [result["max_value"] for result in results] == [0, 0, 0, 0, 1, 1, 1]


def test_situp_preserves_state_through_brief_missing_or_low_confidence_keypoints():
    state = {}
    bottom = analyze_exercise("sit-ups", _situp_keypoints(160), state)
    missing = analyze_exercise("sit-ups", [], state)
    low_confidence = analyze_exercise(
        "sit-ups", _situp_keypoints(90, confidence=0.1), state)
    top = analyze_exercise("sit-ups", _situp_keypoints(90), state)
    top_phase = top["state"]["situp_phase"]
    missing_bottom = analyze_exercise(
        "sit-ups", _situp_keypoints(160, confidence=0.1), state)
    missing_bottom_reps = missing_bottom["state"]["reps"]
    completed = analyze_exercise("sit-ups", _situp_keypoints(160), state)

    assert bottom["state"]["situp_phase"] == "bottom"
    assert missing["valid"] is False
    assert low_confidence["valid"] is False
    assert top_phase == "top"
    assert missing_bottom_reps == 0
    assert completed["state"]["reps"] == 1


def test_situp_reset_starts_without_a_previous_count_or_position():
    state = {}
    analyze_exercise("sit-ups", _situp_keypoints(160), state)
    analyze_exercise("sit-ups", _situp_keypoints(90), state)
    completed = analyze_exercise("sit-ups", _situp_keypoints(160), state)

    reset_state = {}
    after_reset = analyze_exercise(
        "sit-ups", _situp_keypoints(160), reset_state)

    assert completed["state"]["reps"] == 1
    assert after_reset["state"]["reps"] == 0
    assert after_reset["state"]["situp_phase"] == "bottom"


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
