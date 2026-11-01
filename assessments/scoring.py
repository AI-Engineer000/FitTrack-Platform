"""Assessment measurement definitions and benchmark availability."""

import math

from assessments.benchmarks import BENCHMARKS, BENCHMARK_SOURCE

SCORING_METHOD_VERSION = "fittrack-unbenchmarked-v1"
REFERENCE_SCORING_METHOD_VERSION = "general-reference-provisional-v1"
PROTOCOL_VERSION = "video-protocol-v1"

EXERCISE_SLUGS = {
    "Vertical Jump": "vertical_jump",
    "Broad Jump": "broad_jump",
    "Sit-ups": "sit_ups",
    "Sit & Reach": "sit_and_reach",
    "Sprint": "sprint",
    "Medicine Ball Throw": "medicine_ball",
    "Shuttle Run": "shuttle_run",
    "Endurance Run": "endurance_run",
}


def calculate_exercise_score(exercise_slug, value, gender, unit):
    """Return a provisional reference score only for a matching unit/gender."""
    benchmark = BENCHMARKS.get(exercise_slug)
    if benchmark is None:
        return {
            "score": None,
            "rating": "Unavailable",
            "source": "Not configured",
            "reference": "",
            "is_provisional": True,
            "disclaimer": "No configured reference is available for this exercise.",
        }

    normalized_unit = {"s": "sec", "seconds": "sec"}.get(
        (unit or "").strip().lower(),
        (unit or "").strip().lower(),
    )
    normalized_gender = (gender or "").strip().lower()
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        numeric_value = None

    result = {
        "score": None,
        "rating": "Unavailable",
        "source": BENCHMARK_SOURCE,
        "reference": benchmark["reference"],
        "is_provisional": True,
        "disclaimer": (
            "Rating unavailable: a compatible measurement unit and supported "
            "gender are required."
        ),
    }
    if (
        normalized_gender not in {"male", "female"}
        or normalized_unit != benchmark["unit"]
        or numeric_value is None
        or not math.isfinite(numeric_value)
        or numeric_value <= 0
    ):
        return result

    limits = benchmark[normalized_gender]
    if benchmark["higher_is_better"]:
        if numeric_value >= limits[3]:
            rating, score = "Excellent", 95
        elif numeric_value >= limits[2]:
            rating, score = "Good", 80
        elif numeric_value >= limits[1]:
            rating, score = "Average", 60
        elif numeric_value >= limits[0]:
            rating, score = "Poor", 35
        else:
            rating, score = "Very Poor", 15
    else:
        if numeric_value <= limits[3]:
            rating, score = "Excellent", 95
        elif numeric_value <= limits[2]:
            rating, score = "Good", 80
        elif numeric_value <= limits[1]:
            rating, score = "Average", 60
        elif numeric_value <= limits[0]:
            rating, score = "Poor", 35
        else:
            rating, score = "Very Poor", 15

    result.update(
        score=score,
        rating=rating,
        disclaimer=(
            "Reference-based rating from general fitness ranges. Requires "
            "clinical validation for diagnostic use; not a medical diagnosis."
        ),
    )
    return result


def apply_provisional_reference_rating(
    record, exercise, gender, allow_legacy=False,
):
    """Attach a provisional rating only when measurement provenance permits."""
    allowed_statuses = {"valid"}
    if allow_legacy:
        allowed_statuses.add("legacy")
    if record.get("measurement_status") not in allowed_statuses:
        return record

    exercise_slug = EXERCISE_SLUGS.get(exercise)
    result = calculate_exercise_score(
        exercise_slug,
        record.get("measurement"),
        gender,
        record.get("measurement_unit"),
    ) if exercise_slug else {
        "score": None,
        "rating": "Unavailable",
        "source": "Not configured",
        "reference": "",
        "is_provisional": True,
        "disclaimer": "No configured reference is available for this exercise.",
    }
    if result["score"] is None:
        return record

    details = dict(record.get("details") or {})
    if record.get("measurement_status") == "legacy":
        disclaimer = (
            "Provisional reference-based score from a historical measurement; "
            "its original measurement method is unknown. Not a medical "
            "diagnosis."
        )
    else:
        disclaimer = (
            "General reference-based rating. Not a medical diagnosis; "
            "not age-adjusted or validated for this assessment protocol."
        )
    details["reference_rating"] = {
        "basis": result["reference"],
        "classification": "Provisional / Reference-Based",
        "is_provisional": result["is_provisional"],
        "disclaimer": disclaimer,
    }
    record.update({
        "score": result["score"],
        "result": f"{result['rating']} (Provisional)",
        "benchmark_status": "available",
        "benchmark_rating": result["rating"],
        "benchmark_source": result["source"],
        "scoring_method_version": REFERENCE_SCORING_METHOD_VERSION,
        "details": details,
    })
    return record


EXERCISE_DEFINITIONS = {
    "vertical-jump": {
        "exercise": "Vertical Jump",
        "unit": "px",
        "measurement": "Maximum vertical ankle displacement from the first valid frame.",
        "protocol": "Side-on fixed-camera observation; no physical scale calibration is available.",
        "value_key": "max_jump_px",
        "status": "uncalibrated",
    },
    "broad-jump": {
        "exercise": "Broad Jump",
        "unit": "px",
        "measurement": "Best horizontal ankle-centre displacement for a detected two-foot take-off and landing.",
        "protocol": "Side-on fixed-camera observation; no physical scale calibration is available.",
        "value_key": "best_distance_px",
        "status": "uncalibrated",
    },
    "sit-ups": {
        "exercise": "Sit-ups",
        "unit": "reps",
        "measurement": "Valid transitions from a lower/start position to the configured upper torso-angle position.",
        "protocol": "One repetition is recorded at the upper transition; returning to the lower position completes and re-arms the cycle.",
        "value_key": "reps",
        "status": "valid",
    },
    "sit-reach": {
        "exercise": "Sit & Reach",
        "unit": "px",
        "measurement": "Maximum horizontal wrist displacement from the first valid frame.",
        "protocol": "Video displacement only; no reach-box or physical-scale calibration is available.",
        "value_key": "max_reach_px",
        "status": "uncalibrated",
    },
    "sprint": {
        "exercise": "Sprint",
        "unit": "s",
        "measurement": "Elapsed time to a calibrated 2 m displacement.",
        "protocol": "Requires a known physical scale and a fixed 2 m course.",
        "value_key": "elapsed_sec",
        "status": "valid",
    },
    "medicine-ball": {
        "exercise": "Medicine Ball Throw",
        "unit": "px",
        "measurement": "Maximum horizontal wrist displacement; the ball itself is not tracked.",
        "protocol": "Video displacement only; no ball flight or physical-scale measurement.",
        "value_key": "max_throw_px",
        "status": "uncalibrated",
    },
    "shuttle-run": {
        "exercise": "Shuttle Run",
        "unit": "crossings",
        "measurement": "Observed hip-centre crossings of the initial image-space line.",
        "protocol": "Image-space crossing count only; no measured shuttle-course distance.",
        "value_key": "crossings",
        "status": "unvalidated",
    },
    "endurance-run": {
        "exercise": "Endurance Run",
        "unit": "round trips",
        "measurement": "Observed pairs of hip-centre crossings of the initial image-space line.",
        "protocol": "Image-space crossing count only; no measured course distance or duration.",
        "value_key": "laps",
        "status": "unvalidated",
    },
}


def build_assessment_record(exercise, state):
    """Build a reproducible raw record; no compatible reference is shipped."""
    definition = EXERCISE_DEFINITIONS.get(exercise)
    if definition is None:
        return None

    value_key = definition["value_key"]
    measurement_unit = definition["unit"]
    measurement_status = definition["status"]
    measurement_definition = definition["measurement"]
    protocol = definition["protocol"]
    estimated_scale = (
        state.get("calibration_method") == "nose_to_ankle_height"
        and state.get("calibration_status") == "estimated"
        and exercise in {"sprint", "vertical-jump", "broad-jump"}
    )
    if estimated_scale:
        measurement_status = "unvalidated"
        protocol += (
            " An estimated nose-to-ankle scale based on entered athlete "
            "height was used; camera perspective and the nose landmark "
            "prevent this from being a physical calibration."
        )
        if exercise == "vertical-jump" and state.get("max_jump_cm") is not None:
            value_key = "max_jump_cm"
            measurement_unit = "cm"
            measurement_definition = (
                "Estimated maximum vertical ankle displacement using the "
                "nose-to-ankle height scale proxy."
            )
        elif exercise == "broad-jump" and state.get("best_distance_cm") is not None:
            value_key = "best_distance_cm"
            measurement_unit = "cm"
            measurement_definition = (
                "Estimated best horizontal ankle-centre displacement using "
                "the nose-to-ankle height scale proxy."
            )

    measurement = state.get(value_key)
    if measurement is None:
        return None
    try:
        measurement = float(measurement)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(measurement) or measurement <= 0:
        return None

    details = {
        "measurement_definition": measurement_definition,
        "protocol": protocol,
    }
    if estimated_scale:
        details["scale_calibration"] = {
            "status": "estimated",
            "method": "nose_to_ankle_height",
            "athlete_height_cm": state.get("athlete_height_cm"),
            "pixels_per_cm": state.get("pixels_per_cm"),
        }
    if exercise == "sit-ups":
        try:
            reps = int(state.get("reps", 0))
            completed_cycles = int(state.get("completed_cycles", 0))
        except (TypeError, ValueError):
            return None
        if (
            reps <= 0
            or completed_cycles < 0
            or completed_cycles > reps
            or not measurement.is_integer()
            or reps != int(measurement)
        ):
            return None
        details.update({
            "detected_upper_repetitions": reps,
            "completed_cycles": completed_cycles,
            "upper_positions_not_yet_completed": max(
                0, reps - completed_cycles,
            ),
        })
    elif exercise == "broad-jump":
        try:
            valid_attempts = int(state.get("valid_attempts", 0))
        except (TypeError, ValueError):
            return None
        if valid_attempts <= 0:
            return None
        details["valid_attempts"] = valid_attempts

    return {
        "measurement": round(measurement, 2),
        "measurement_unit": measurement_unit,
        "measurement_status": measurement_status,
        "score": None,
        "result": "Benchmark unavailable",
        "benchmark_status": "unavailable",
        "benchmark_rating": "",
        "benchmark_source": "",
        "scoring_method_version": SCORING_METHOD_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "details": details,
    }


def build_body_measurement_record(exercise, measurement):
    """Body measurements are recorded as measurements, never fitness scores."""
    units = {"Height": "cm", "Weight": "kg"}
    if exercise not in units:
        raise ValueError(f"Unsupported body measurement: {exercise}")
    value = float(measurement)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Body measurements must be positive.")
    return {
        "measurement": round(value, 2),
        "measurement_unit": units[exercise],
        "measurement_status": "valid",
        "score": None,
        "result": "Measurement only",
        "benchmark_status": "not_applicable",
        "benchmark_rating": "",
        "benchmark_source": "",
        "scoring_method_version": SCORING_METHOD_VERSION,
        "protocol_version": "manual-measurement-v1",
        "details": {"measurement_definition": f"Manually recorded {exercise.lower()}."},
    }


def build_unbenchmarked_record(measurement, unit, definition, protocol):
    """Represent a raw observation without inventing a rating or score."""
    try:
        value = float(measurement)
    except (TypeError, ValueError):
        raise ValueError("Assessment measurement must be numeric.")
    if not math.isfinite(value) or value <= 0:
        raise ValueError("Assessment measurement must be finite and positive.")
    return {
        "measurement": round(value, 2),
        "measurement_unit": unit,
        "measurement_status": "unvalidated",
        "score": None,
        "result": "Benchmark unavailable",
        "benchmark_status": "unavailable",
        "benchmark_rating": "",
        "benchmark_source": "",
        "scoring_method_version": SCORING_METHOD_VERSION,
        "protocol_version": PROTOCOL_VERSION,
        "details": {
            "measurement_definition": definition,
            "protocol": protocol,
        },
    }
