import numpy as np


CONFIDENCE_THRESHOLD = 0.5
KNEE_STRAIGHT_THRESHOLD = 160
JUMP_START_THRESHOLD_PX = 15
SITUP_UP_ANGLE = 100.0
SITUP_DOWN_ANGLE = 140.0


def _result(valid, current_value, max_value, unit, state_label, state):
    return {
        "valid": valid,
        "current_value": current_value,
        "max_value": max_value,
        "unit": unit,
        "state_label": state_label,
        "state": state,
    }


def _invalid(state):
    return _result(False, None, None, None, "NO DATA", state)


def _keypoint_valid(kp):
    return bool(kp) and len(kp) >= 3 and kp[2] >= CONFIDENCE_THRESHOLD


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


def _calculate_score(value, worst, best):
    if best == worst:
        return 100.0
    score = ((value - worst) / (best - worst)) * 100
    return round(float(np.clip(score, 0, 100)), 2)


def _get_result(score):
    if score >= 80:
        return "Excellent"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Average"
    return "Needs Improvement"


def _analyze_vertical_jump(keypoints, state):
    """
    State keys: pixels_per_cm, standing_y, max_jump_px, max_jump_cm
    """
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("pixels_per_cm", None)
    state.setdefault("standing_y", None)
    state.setdefault("max_jump_px", 0.0)
    state.setdefault("max_jump_cm", None)

    ankle = _pick_keypoint(keypoints[15], keypoints[16])
    if ankle is None:
        return _invalid(state)

    ankle_y = float(ankle[1])
    if state["standing_y"] is None:
        state["standing_y"] = ankle_y

    current_px = max(0.0, state["standing_y"] - ankle_y)
    state["max_jump_px"] = max(state["max_jump_px"], current_px)

    label = "JUMPING" if current_px >= JUMP_START_THRESHOLD_PX else "READY"
    pixels_per_cm = state["pixels_per_cm"]

    if pixels_per_cm:
        current_cm = round(current_px / pixels_per_cm, 2)
        state["max_jump_cm"] = round(state["max_jump_px"] / pixels_per_cm, 2)
        return _result(True, current_cm, state["max_jump_cm"], "cm", label, state)

    return _result(True, round(current_px, 1), round(state["max_jump_px"], 1),
                   "px", label, state)


def _analyze_broad_jump(keypoints, state):
    """Horizontal ankle (15/16) displacement from the takeoff position."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("pixels_per_cm", None)
    state.setdefault("takeoff_x", None)
    state.setdefault("max_jump_px", 0.0)
    state.setdefault("max_jump_cm", None)

    ankle = _pick_keypoint(keypoints[15], keypoints[16])
    if ankle is None:
        return _invalid(state)

    ankle_x = float(ankle[0])
    if state["takeoff_x"] is None:
        state["takeoff_x"] = ankle_x
        return _result(True, 0.0, 0.0, "px", "READY", state)

    current_px = max(0.0, ankle_x - state["takeoff_x"])
    state["max_jump_px"] = max(state["max_jump_px"], current_px)

    pixels_per_cm = state["pixels_per_cm"]
    if pixels_per_cm:
        current_cm = round(current_px / pixels_per_cm, 2)
        state["max_jump_cm"] = round(state["max_jump_px"] / pixels_per_cm, 2)
        return _result(True, current_cm, state["max_jump_cm"], "cm", "JUMPING", state)

    return _result(True, round(current_px, 1), round(state["max_jump_px"], 1),
                   "px", "JUMPING", state)


def _analyze_situps(keypoints, state):
    """Reps counted from the torso angle: shoulder(5/6) - hip(11/12) - knee(13/14)."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("reps", 0)
    state.setdefault("phase", "down")

    shoulder = _pick_keypoint(keypoints[5], keypoints[6])
    hip = _pick_keypoint(keypoints[11], keypoints[12])
    knee = _pick_keypoint(keypoints[13], keypoints[14])

    if shoulder is None or hip is None or knee is None:
        return _invalid(state)

    angle = _calculate_angle(shoulder, hip, knee)
    if angle is None:
        return _invalid(state)

    angle = round(angle, 1)
    phase = state["phase"]

    if phase == "down" and angle <= SITUP_UP_ANGLE:
        phase = "up"
    elif phase == "up" and angle >= SITUP_DOWN_ANGLE:
        phase = "down"
        state["reps"] += 1

    state["phase"] = phase
    return _result(True, angle, state["reps"], "deg",
                   "UP" if phase == "up" else "DOWN", state)


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
    """Time from the first detected hip frame to the stop timestamp in state['now']."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("start_time", None)
    state.setdefault("elapsed_sec", None)

    hip = _pick_keypoint(keypoints[11], keypoints[12])
    if hip is None:
        return _invalid(state)

    now = state.get("now")
    if now is None:
        return _invalid(state)

    if state["start_time"] is None:
        state["start_time"] = now
        return _result(True, 0.0, 0.0, "sec", "RUNNING", state)

    if state["elapsed_sec"] is None:
        state["elapsed_sec"] = round(max(0.0, now - state["start_time"]), 2)

    return _result(True, state["elapsed_sec"], state["elapsed_sec"], "sec",
                   "RUNNING", state)


def _analyze_medicine_ball(keypoints, state):
    """Wrist(9/10) X displacement from the start of the throw."""
    if not keypoints or len(keypoints) < 17:
        return _invalid(state)

    state.setdefault("pixels_per_cm", None)
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

    pixels_per_cm = state["pixels_per_cm"]
    if pixels_per_cm:
        current_cm = round(current_px / pixels_per_cm, 2)
        state["max_throw_cm"] = round(state["max_throw_px"] / pixels_per_cm, 2)
        return _result(True, current_cm, state["max_throw_cm"], "cm", "THROWING", state)

    return _result(True, round(current_px, 1), round(state["max_throw_px"], 1),
                   "px", "THROWING", state)


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

    side = "right" if hip_x > state["center_x"] else "left"
    if state["last_side"] is None:
        state["last_side"] = side
    elif side != state["last_side"]:
        state["crossings"] += 1
        state["last_side"] = side

    crossings = state["crossings"]
    return _result(True, crossings, crossings, "laps", "RUNNING", state)


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

    side = "right" if hip_x > state["center_x"] else "left"
    if state["last_side"] is None:
        state["last_side"] = side
    elif side != state["last_side"]:
        state["crossings"] += 1
        state["laps"] = state["crossings"] // 2
        state["last_side"] = side

    laps = state["laps"]
    return _result(True, laps, laps, "laps", "RUNNING", state)


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


def _record(measurement, worst, best):
    score = _calculate_score(measurement, worst, best)
    return {
        "measurement": round(float(measurement), 2),
        "score": score,
        "result": _get_result(score),
    }


def _seconds_record(seconds):
    """Lower is better, so the score is computed on the negated time."""
    if not seconds or seconds <= 0:
        return None
    score = _calculate_score(-seconds, -30.0, -6.0)
    return {
        "measurement": round(float(seconds), 2),
        "score": score,
        "result": _get_result(score),
    }


def build_assessment_record(exercise, state):
    if exercise == "vertical-jump":
        jump_cm = state.get("max_jump_cm")
        if not jump_cm or jump_cm <= 0:
            return None
        return _record(jump_cm, 0, 60)

    if exercise == "broad-jump":
        jump_cm = state.get("max_jump_cm")
        if not jump_cm or jump_cm <= 0:
            return None
        return _record(jump_cm, 100, 260)

    if exercise == "sit-ups":
        reps = state.get("reps") or 0
        if reps <= 0:
            return None
        return _record(reps, 10, 50)

    if exercise == "sit-reach":
        reach_px = state.get("max_reach_px") or 0
        if reach_px <= 0:
            return None
        return _record(reach_px, 0, 300)

    if exercise == "sprint":
        return _seconds_record(state.get("elapsed_sec"))

    if exercise == "medicine-ball":
        throw_cm = state.get("max_throw_cm")
        if not throw_cm or throw_cm <= 0:
            return None
        return _record(throw_cm, 100, 400)

    if exercise == "shuttle-run":
        crossings = state.get("crossings") or 0
        if crossings <= 0:
            return None
        return _record(crossings, 4, 20)

    if exercise == "endurance-run":
        laps = state.get("laps") or 0
        if laps <= 0:
            return None
        return _record(laps, 2, 12)

    return None
