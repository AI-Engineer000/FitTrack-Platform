import numpy as np

from dashboard.live_analysis import (
    analyze_exercise,
    build_assessment_record,
    estimate_pixels_per_cm,
)


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


def test_pixels_per_cm_is_not_inferred_without_physical_calibration():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[0] = _kp(320, 100)
    keypoints[15] = _kp(305, 410)
    keypoints[16] = _kp(335, 440)

    assert estimate_pixels_per_cm(keypoints) is None


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

    result = analyze_exercise("vertical-jump", keypoints, {})

    assert result["valid"] is True
    assert result["unit"] == "px"
    assert result["current_value"] >= 0
    assert "pixels_per_cm" not in result["state"]


def test_vertical_jump_height_scale_is_estimated_and_saved_as_unvalidated():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[15] = _kp(100, 400)
    state = {
        "pixels_per_cm": 2.0,
        "calibration_status": "estimated",
        "calibration_method": "nose_to_ankle_height",
        "athlete_height_cm": 200.0,
    }

    analyze_exercise("vertical-jump", keypoints, state)
    keypoints[15] = _kp(100, 300)
    result = analyze_exercise("vertical-jump", keypoints, state)
    record = build_assessment_record("vertical-jump", state)

    assert result["current_value"] == 50.0
    assert result["unit"] == "cm"
    assert record["measurement"] == 50.0
    assert record["measurement_unit"] == "cm"
    assert record["measurement_status"] == "unvalidated"
    assert record["score"] is None
    assert record["details"]["scale_calibration"]["status"] == "estimated"


def test_broad_jump_height_scale_is_estimated_and_saved_as_unvalidated():
    state = {
        "pixels_per_cm": 2.0,
        "calibration_status": "estimated",
        "calibration_method": "nose_to_ankle_height",
        "athlete_height_cm": 200.0,
    }
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[15] = _kp(100, 400)
    keypoints[16] = _kp(110, 400)
    analyze_exercise("broad-jump", keypoints, state)
    keypoints[15] = _kp(120, 380)
    keypoints[16] = _kp(130, 380)
    analyze_exercise("broad-jump", keypoints, state)
    keypoints[15] = _kp(150, 400)
    keypoints[16] = _kp(160, 400)
    result = analyze_exercise("broad-jump", keypoints, state)
    record = build_assessment_record("broad-jump", state)

    assert result["max_value"] == 25.0
    assert result["unit"] == "cm"
    assert record["measurement"] == 25.0
    assert record["measurement_unit"] == "cm"
    assert record["measurement_status"] == "unvalidated"
    assert record["score"] is None


def test_sit_reach_uses_wrist_without_name_error():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[9] = _kp(200, 150)
    keypoints[10] = _kp(250, 150)
    keypoints[11] = _kp(220, 220)
    keypoints[12] = _kp(260, 220)

    result = analyze_exercise("sit-reach", keypoints, {"start_x": 100.0})

    assert result["valid"] is True
    assert result["state"]["reach_px"] > 0


def test_situp_counts_at_upper_position_and_completes_on_lower_return():
    state = {}
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in (160, 160, 90, 90)
    ]

    assert [result["max_value"] for result in results] == [0, 0, 0, 1]
    assert results[-1]["state_label"] == "UP"
    assert results[-1]["state"]["completed_cycles"] == 0

    analyze_exercise("sit-ups", _situp_keypoints(160), state)
    completed = analyze_exercise("sit-ups", _situp_keypoints(160), state)
    assert completed["max_value"] == 1
    assert completed["state"]["completed_cycles"] == 1
    assert completed["state"]["situp_phase"] == "bottom"


def test_situp_counts_five_consecutive_upper_transitions():
    state = {}
    angles = [160, 160] + [
        angle for _ in range(5) for angle in (90, 90, 160, 160)
    ]
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in angles
    ]

    assert results[-1]["state"]["reps"] == 5
    assert results[-1]["state"]["completed_cycles"] == 5


def test_situp_completes_cycle_when_lower_position_reaches_125_degrees():
    state = {}
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in (125, 125, 125, 80, 80, 125, 125)
    ]

    assert results[-1]["state"]["reps"] == 1
    assert results[-1]["state"]["completed_cycles"] == 1
    assert results[-1]["state"]["situp_phase"] == "bottom"


def test_situp_holds_and_partial_movements_do_not_duplicate_or_count():
    state = {}
    angles = (160, 160, 90, 90, 90, 90, 120, 115, 160, 160)
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in angles
    ]
    assert results[3]["max_value"] == 1
    assert results[-1]["max_value"] == 1


def test_situp_starting_at_upper_pose_is_ignored_until_lower_position():
    state = {}
    results = [
        analyze_exercise("sit-ups", _situp_keypoints(angle), state)
        for angle in (90, 90, 90, 160, 160, 90, 90)
    ]
    assert results[1]["max_value"] == 0
    assert results[-1]["max_value"] == 1


def test_situp_noisy_angle_spikes_missing_keypoints_and_tracking_loss():
    state = {}
    analyze_exercise("sit-ups", _situp_keypoints(160), state)
    analyze_exercise("sit-ups", _situp_keypoints(160), state)
    analyze_exercise("sit-ups", _situp_keypoints(90), state)
    missing = analyze_exercise("sit-ups", [], state)
    low_confidence = analyze_exercise(
        "sit-ups", _situp_keypoints(90, confidence=0.1), state)
    noisy_spike = analyze_exercise("sit-ups", _situp_keypoints(90), state)
    assert missing["valid"] is False
    assert low_confidence["valid"] is False
    assert noisy_spike["state"]["reps"] == 1

    state = {}
    for angle in (160, 160, 108, 99, 110, 108, 160, 160):
        result = analyze_exercise("sit-ups", _situp_keypoints(angle), state)
    assert result["state"]["reps"] == 0


def test_situp_video_end_distinguishes_upper_reps_from_complete_cycles():
    state = {}
    for angle in (160, 160, 90, 90):
        result = analyze_exercise("sit-ups", _situp_keypoints(angle), state)
    record = build_assessment_record("sit-ups", state)
    assert result["state"]["reps"] == 1
    assert state["completed_cycles"] == 0
    assert record["measurement"] == 1
    assert record["details"]["upper_positions_not_yet_completed"] == 1

    state = {}
    for angle in (160, 160, 90, 90, 160, 160):
        result = analyze_exercise("sit-ups", _situp_keypoints(angle), state)
    assert result["state"]["completed_cycles"] == 1
    assert build_assessment_record("sit-ups", state)["measurement"] == 1


def test_vertical_and_broad_jumps_are_distinct_uncalibrated_measurements():
    vertical_keypoints = [[0, 0, 0.0] for _ in range(17)]
    vertical_keypoints[15] = _kp(100, 100)
    vertical = analyze_exercise("vertical-jump", vertical_keypoints, {})
    vertical_keypoints[15] = _kp(100, 50)
    vertical = analyze_exercise(
        "vertical-jump", vertical_keypoints, vertical["state"])

    broad_keypoints = [[0, 0, 0.0] for _ in range(17)]
    broad_keypoints[15] = _kp(100, 100)
    broad_keypoints[16] = _kp(110, 100)
    broad = analyze_exercise("broad-jump", broad_keypoints, {})
    broad_keypoints[15] = _kp(120, 80)
    broad_keypoints[16] = _kp(130, 80)
    broad = analyze_exercise("broad-jump", broad_keypoints, broad["state"])
    broad_keypoints[15] = _kp(150, 100)
    broad_keypoints[16] = _kp(160, 100)
    broad = analyze_exercise("broad-jump", broad_keypoints, broad["state"])

    assert vertical["max_value"] == 50
    assert vertical["unit"] == "px"
    assert broad["max_value"] == 50
    assert broad["unit"] == "px"
    assert broad["state"]["valid_attempts"] == 1


def test_uncalibrated_jump_records_have_no_scores_or_centimeter_units():
    vertical = build_assessment_record(
        "vertical-jump", {"max_jump_px": 44.0, "pixels_per_cm": 2.2})
    broad = build_assessment_record(
        "broad-jump", {"best_distance_px": 180.0, "valid_attempts": 2})

    assert vertical["measurement_unit"] == "px"
    assert broad["measurement_unit"] == "px"
    assert vertical["score"] is None
    assert broad["score"] is None
    assert vertical["benchmark_status"] == "unavailable"


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

    keypoints[15] = _kp(330, 400)
    keypoints[16] = _kp(340, 400)
    state = {**running["state"], "now": 4.5}
    finished = analyze_exercise("sprint", keypoints, state)

    assert finished["state_label"] == "FINISHED"
    assert finished["current_value"] == 2.5
    assert finished["state"]["elapsed_sec"] == 2.5


def test_sprint_uses_height_scale_estimate_and_marks_record_unvalidated():
    keypoints = [[0, 0, 0.0] for _ in range(17)]
    keypoints[15] = _kp(100, 400)
    keypoints[16] = _kp(110, 400)
    state = {
        "pixels_per_cm": 2.0,
        "calibration_status": "estimated",
        "calibration_method": "nose_to_ankle_height",
        "athlete_height_cm": 200.0,
        "now": 1.0,
    }

    ready = analyze_exercise("sprint", keypoints, state)
    keypoints[15] = _kp(150, 400)
    keypoints[16] = _kp(160, 400)
    running = analyze_exercise(
        "sprint", keypoints, {**ready["state"], "now": 2.0})
    keypoints[15] = _kp(560, 400)
    keypoints[16] = _kp(570, 400)
    finished = analyze_exercise(
        "sprint", keypoints, {**running["state"], "now": 4.5})
    record = build_assessment_record("sprint", finished["state"])

    assert finished["state_label"] == "FINISHED"
    assert finished["state"]["elapsed_sec"] == 2.5
    assert record["measurement"] == 2.5
    assert record["measurement_unit"] == "s"
    assert record["measurement_status"] == "unvalidated"
    assert record["details"]["scale_calibration"]["status"] == "estimated"
