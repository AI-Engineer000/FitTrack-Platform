import numpy as np
from assessments.scoring import build_assessment_record as _build_assessment_record


CONFIDENCE_THRESHOLD = 0.5
KNEE_STRAIGHT_THRESHOLD = 160
JUMP_START_THRESHOLD_PX = 15
SITUP_UP_ANGLE = 105.0
SITUP_DOWN_ANGLE = 120.0
SITUP_ANGLE_HISTORY_SIZE = 3
BROAD_JUMP_TAKEOFF_DELTA_PX = 12.0
BROAD_JUMP_LANDING_TOLERANCE_PX = 24.0
CROSSING_HYSTERESIS_PX = 25.0


def _result(valid, current_value, max_value, unit, state_label, state, current_unit=None, max_unit=None):
    return {
        "valid": valid,
        "current_value": current_value,
        "max_value": max_value,
        "unit": unit,
        "current_unit": current_unit or unit,
        "max_unit": max_unit or unit,
        "state_label": state_label,
        "state": state,
    }


def _invalid(state):
    return _result(False, None, None, None, "NO DATA", state)


def estimate_pixels_per_cm(keypoints):
    """Do not infer a real-world scale from an assumed participant height."""
    return None


def _keypoint_valid(kp):
    return (
        bool(kp)
        and len(kp) >= 3
        and np.isfinite(kp[:3]).all()
        and kp[2] >= CONFIDENCE_THRESHOLD
    )


def _pick_keypoint(*candidates):
    """Return the highest-confidence valid keypoint, or None."""
    best = None
    for kp in candidates:
        if _keypoint_valid(kp):
            if best is None or kp[2] > best[2]:
                best = kp
    return best


def _calculate_angle(a, b, c):
    """Angle at joint b in degrees, for three [x, y, conf] keypoints."""
    va = np.array(a[:2], dtype=float)
    vb = np.array(b[:2], dtype=float)
    vc = np.array(c[:2], dtype=float)

    ba = va - vb
    bc = vc - vb
    norm_ba = float(np.linalg.norm(ba))
    norm_bc = float(np.linalg.norm(bc))

    if norm_ba < 1e-6 or norm_bc < 1e-6:
        return None

    cosine = float(np.dot(ba, bc) / (norm_ba * norm_bc))
    cosine = float(np.clip(cosine, -1.0, 1.0))
    return float(np.degrees(np.arccos(cosine)))


def _analyze_vertical_jump(keypoints, state):
    """Track ankle vertical displacement in image pixels, not jump-and-reach height."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("standing_y", None)
    state.setdefault("max_jump_px", 0.0)

    ankle = _pick_keypoint(keypoints[15], keypoints[16])
    if ankle is None:
        return _invalid(state)

    ankle_y = float(ankle[1])
    if state["standing_y"] is None:
        state["standing_y"] = ankle_y
    current_px = max(0.0, state["standing_y"] - ankle_y)
    state["max_jump_px"] = max(state["max_jump_px"], current_px)

    label = "JUMPING" if current_px >= JUMP_START_THRESHOLD_PX else "READY"
    pixels_per_cm = state.get("pixels_per_cm")
    if pixels_per_cm and state.get("calibration_status") == "estimated":
        current_cm = round(current_px / pixels_per_cm, 1)
        max_cm = round(state["max_jump_px"] / pixels_per_cm, 1)
        state["max_jump_cm"] = max_cm
        return _result(
            True,
            current_cm,
            max_cm,
            "cm",
            label,
            state,
        )
    return _result(
        True,
        round(current_px, 1),
        round(state["max_jump_px"], 1),
        "px",
        label,
        state,
    )


def _analyze_broad_jump(keypoints, state):
    """Measure best horizontal ankle-centre displacement for detected attempts."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    left_ankle = keypoints[15]
    right_ankle = keypoints[16]
    if not (_keypoint_valid(left_ankle) and _keypoint_valid(right_ankle)):
        return _invalid(state)

    state.setdefault("start_ankle_x", None)
    state.setdefault("floor_y", None)
    state.setdefault("airborne", False)
    state.setdefault("attempt_distance_px", 0.0)
    state.setdefault("best_distance_px", 0.0)
    state.setdefault("valid_attempts", 0)

    ankle_x = (float(left_ankle[0]) + float(right_ankle[0])) / 2
    ankle_y = (float(left_ankle[1]) + float(right_ankle[1])) / 2
    if state["floor_y"] is None:
        state["floor_y"] = ankle_y
        state["start_ankle_x"] = ankle_x
        return _result(True, 0.0, 0.0, "px", "READY", state)

    if not state["airborne"]:
        both_feet_airborne = (
            state["floor_y"] - float(left_ankle[1])
            >= BROAD_JUMP_TAKEOFF_DELTA_PX
            and state["floor_y"] - float(right_ankle[1])
            >= BROAD_JUMP_TAKEOFF_DELTA_PX
        )
        if both_feet_airborne:
            state["airborne"] = True
            state["attempt_distance_px"] = 0.0
            return _result(
                True,
                state["best_distance_px"],
                state["best_distance_px"],
                "px",
                "AIRBORNE",
                state,
            )
        return _result(
            True,
            state["best_distance_px"],
            state["best_distance_px"],
            "px",
            "READY",
            state,
        )

    state["attempt_distance_px"] = abs(ankle_x - state["start_ankle_x"])
    landed = all(
        abs(float(point[1]) - state["floor_y"])
        <= BROAD_JUMP_LANDING_TOLERANCE_PX
        for point in (left_ankle, right_ankle)
    )
    if landed:
        distance = round(float(state["attempt_distance_px"]), 1)
        if distance > 0:
            state["valid_attempts"] += 1
            state["best_distance_px"] = max(state["best_distance_px"], distance)
        state["airborne"] = False
        state["attempt_distance_px"] = 0.0
        label = "LANDING RECORDED" if distance > 0 else "INVALID LANDING"
    else:
        label = "AIRBORNE"

    current_distance = (
        float(state["attempt_distance_px"])
        if state["airborne"]
        else float(state["best_distance_px"])
    )
    pixels_per_cm = state.get("pixels_per_cm")
    if pixels_per_cm and state.get("calibration_status") == "estimated":
        best_distance_cm = round(
            float(state["best_distance_px"]) / pixels_per_cm, 1)
        state["best_distance_cm"] = best_distance_cm
        return _result(
            True,
            round(current_distance / pixels_per_cm, 1),
            best_distance_cm,
            "cm",
            label,
            state,
        )
    return _result(
        True,
        round(current_distance, 1),
        round(float(state["best_distance_px"]), 1),
        "px",
        label,
        state,
    )


def _analyze_situps(keypoints, state):
    """Reps counted from the torso angle: shoulder(5/6) - hip(11/12) - knee(13/14)."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    try:
        state["reps"] = max(0, int(state.get("reps", 0)))
        state["completed_cycles"] = max(
            0, int(state.get("completed_cycles", 0))
        )
    except (TypeError, ValueError):
        return _invalid(state)
    if state.get("situp_phase") not in {"seeking_bottom", "bottom", "top"}:
        state["situp_phase"] = "seeking_bottom"

    valid_sides = []
    for shoulder_index, hip_index, knee_index in (
        (5, 11, 13),
        (6, 12, 14),
    ):
        side = (
            keypoints[shoulder_index],
            keypoints[hip_index],
            keypoints[knee_index],
        )
        if all(_keypoint_valid(point) for point in side):
            valid_sides.append(side)
    if not valid_sides:
        return _invalid(state)

    shoulder, hip, knee = max(
        valid_sides,
        key=lambda side: sum(float(point[2]) for point in side),
    )
    angle = _calculate_angle(shoulder, hip, knee)
    if angle is None:
        return _invalid(state)

    raw_history = state.get("situp_angle_history", [])
    history = []
    if isinstance(raw_history, list):
        for value in raw_history:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
            if np.isfinite(value) and 0 <= value <= 180:
                history.append(value)
    history = (history + [angle])[-SITUP_ANGLE_HISTORY_SIZE:]
    state["situp_angle_history"] = history
    angle = round(float(np.median(history)), 1)
    phase = state["situp_phase"]

    if phase == "seeking_bottom" and angle >= SITUP_DOWN_ANGLE:
        phase = "bottom"
    elif phase == "bottom" and angle <= SITUP_UP_ANGLE:
        phase = "top"
        state["reps"] += 1
    elif phase == "top" and angle >= SITUP_DOWN_ANGLE:
        phase = "bottom"
        state["completed_cycles"] = state.get("completed_cycles", 0) + 1

    state["situp_phase"] = phase
    label = {
        "seeking_bottom": "READY",
        "bottom": "DOWN",
        "top": "UP",
    }[phase]
    return _result(
        True,
        angle,
        state["reps"],
        "reps",
        label,
        state,
        current_unit="°",
        max_unit="reps",
    )


def _analyze_sit_reach(keypoints, state):
    """Furthest wrist(9/10) X reach to the right of the starting position."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("start_x", None)
    state.setdefault("reach_px", 0.0)
    state.setdefault("max_reach_px", 0.0)

    wrist = _pick_keypoint(keypoints[9], keypoints[10])
    if wrist is None:
        return _invalid(state)

    wrist_x = float(wrist[0])
    if state["start_x"] is None:
        state["start_x"] = wrist_x
        return _result(True, 0.0, 0.0, "px", "READY", state)

    current_px = max(0.0, wrist_x - state["start_x"])
    state["reach_px"] = round(current_px, 1)
    state["max_reach_px"] = max(state["max_reach_px"], state["reach_px"])

    return _result(True, state["reach_px"], round(state["max_reach_px"], 1),
                   "px", "REACHING", state)


def _analyze_sprint(keypoints, state):
    """Time a 2-meter sprint after movement starts, preserving JSON state."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("pixels_per_cm", None)
    state.setdefault("start_x", None)
    state.setdefault("start_position_x", None)
    state.setdefault("start_time", None)
    state.setdefault("elapsed_sec", None)
    state.setdefault("finished", False)

    ankle = _pick_keypoint(keypoints[15], keypoints[16])
    if ankle is None:
        return _invalid(state)
    if not state["pixels_per_cm"]:
        return _result(False, None, None, "sec", "CALIBRATION REQUIRED", state)

    ankle_x = float(ankle[0])
    now = state.get("now")
    if now is None:
        return _invalid(state)

    if state["start_time"] is None:
        if state["start_x"] is None:
            state["start_x"] = ankle_x
        pixels_per_cm = state["pixels_per_cm"]
        displacement_cm = (
            abs(ankle_x - state["start_x"]) / pixels_per_cm
            if pixels_per_cm else 0.0
        )
        if displacement_cm < 20:
            return _result(True, 0.0, 0.0, "sec", "READY", state)
        state["start_position_x"] = ankle_x
        state["start_time"] = float(now)
        return _result(True, 0.0, 0.0, "sec", "RUNNING", state)

    pixels_per_cm = state["pixels_per_cm"]
    displacement_cm = (
        abs(ankle_x - state["start_position_x"]) / pixels_per_cm
        if pixels_per_cm else 0.0
    )
    elapsed = round(max(0.0, float(now) - state["start_time"]), 2)
    if displacement_cm >= 200 and not state["finished"]:
        state["finished"] = True
        state["elapsed_sec"] = elapsed
        return _result(True, elapsed, elapsed, "sec", "FINISHED", state)

    if state["finished"]:
        elapsed = state["elapsed_sec"]
    return _result(True, elapsed, elapsed, "sec",
                   "FINISHED" if state["finished"] else "RUNNING", state)


def _analyze_medicine_ball(keypoints, state):
    """Wrist(9/10) X displacement from the start of the throw."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("start_x", None)
    state.setdefault("max_throw_px", 0.0)
    state.setdefault("max_throw_cm", None)

    wrist = _pick_keypoint(keypoints[9], keypoints[10])
    if wrist is None:
        return _invalid(state)

    wrist_x = float(wrist[0])
    if state["start_x"] is None:
        state["start_x"] = wrist_x
        return _result(True, 0.0, 0.0, "px", "READY", state)

    current_px = max(0.0, wrist_x - state["start_x"])
    state["max_throw_px"] = max(state["max_throw_px"], current_px)

    return _result(
        True,
        round(current_px, 1),
        round(state["max_throw_px"], 1),
        "px",
        "THROWING",
        state,
    )


def _analyze_shuttle_run(keypoints, state):
    """Each side change of the hip centre counts as one line crossing."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("center_x", None)
    state.setdefault("last_side", None)
    state.setdefault("crossings", 0)

    hip = _pick_keypoint(keypoints[11], keypoints[12])
    if hip is None:
        return _invalid(state)

    hip_x = float(hip[0])
    if state["center_x"] is None:
        state["center_x"] = hip_x
        state["last_side"] = "right"
        return _result(True, 0.0, 0.0, "laps", "READY", state)

    side = (
        "right" if hip_x > state["center_x"] + CROSSING_HYSTERESIS_PX
        else "left" if hip_x < state["center_x"] - CROSSING_HYSTERESIS_PX
        else None
    )
    if side is None:
        return _result(
            True, state["crossings"], state["crossings"],
            "crossings", "RUNNING", state,
        )
    if state["last_side"] is None:
        state["last_side"] = side
    elif side != state["last_side"]:
        state["crossings"] += 1
        state["last_side"] = side

    crossings = state["crossings"]
    return _result(True, crossings, crossings, "crossings", "RUNNING", state)


def _analyze_endurance_run(keypoints, state):
    """A lap is a full round trip, so two crossings make one lap."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("center_x", None)
    state.setdefault("last_side", None)
    state.setdefault("crossings", 0)
    state.setdefault("laps", 0)

    hip = _pick_keypoint(keypoints[11], keypoints[12])
    if hip is None:
        return _invalid(state)

    hip_x = float(hip[0])
    if state["center_x"] is None:
        state["center_x"] = hip_x
        state["last_side"] = "right"
        return _result(True, 0.0, 0.0, "laps", "READY", state)

    side = (
        "right" if hip_x > state["center_x"] + CROSSING_HYSTERESIS_PX
        else "left" if hip_x < state["center_x"] - CROSSING_HYSTERESIS_PX
        else None
    )
    if side is None:
        return _result(
            True, state["laps"], state["laps"],
            "round trips", "RUNNING", state,
        )
    if state["last_side"] is None:
        state["last_side"] = side
    elif side != state["last_side"]:
        state["crossings"] += 1
        state["laps"] = state["crossings"] // 2
        state["last_side"] = side

    laps = state["laps"]
    return _result(True, laps, laps, "round trips", "RUNNING", state)


ANALYZERS = {
    "vertical-jump": _analyze_vertical_jump,
    "broad-jump": _analyze_broad_jump,
    "sit-ups": _analyze_situps,
    "sit-reach": _analyze_sit_reach,
    "sprint": _analyze_sprint,
    "medicine-ball": _analyze_medicine_ball,
    "shuttle-run": _analyze_shuttle_run,
    "endurance-run": _analyze_endurance_run,
}


def analyze_exercise(exercise, keypoints, state):
    analyzer = ANALYZERS.get(exercise)
    if analyzer is None:
        return _invalid(state)
    return analyzer(keypoints, state)


def build_assessment_record(exercise, state):
    if exercise == "sprint" and not state.get("pixels_per_cm"):
        return None
    return _build_assessment_record(exercise, state)
