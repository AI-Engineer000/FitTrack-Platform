import csv
import json as json_module
import logging
import math
from django.conf import settings
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from athletes.models import Athlete
from assessments.models import Assessment
from trainers.models import Trainer
from assessments.scoring import (
    REFERENCE_SCORING_METHOD_VERSION,
    apply_provisional_reference_rating,
    build_body_measurement_record,
)


logger = logging.getLogger(__name__)
EXERCISE_LIST = [
    "Vertical Jump",
    "Broad Jump",
    "Sit-ups",
    "Sit & Reach",
    "Sprint",
    "Height",
    "Weight",
    "Medicine Ball Throw",
    "Shuttle Run",
    "Endurance Run",
]
RECORDED_MEASUREMENT_STATUSES = {
    "valid",
    "uncalibrated",
    "unvalidated",
    "legacy",
}


def _is_recorded_exercise_assessment(assessment):
    """Include recorded measurements, but exclude failed/incomplete attempts."""
    return (
        assessment.exercise in EXERCISE_LIST
        and assessment.measurement_status in RECORDED_MEASUREMENT_STATUSES
        and assessment.measurement is not None
        and math.isfinite(assessment.measurement)
        and assessment.measurement > 0
    )


def _has_provisional_score(assessment):
    return (
        assessment.score is not None
        and math.isfinite(assessment.score)
        and assessment.measurement_status in {"valid", "legacy"}
        and assessment.benchmark_status == "available"
        and assessment.scoring_method_version
        == REFERENCE_SCORING_METHOD_VERSION
        and bool(assessment.benchmark_rating.strip())
    )


def _trainer_for(request):
    """Return a trainer profile, including for pre-existing user accounts."""
    trainer, _ = Trainer.objects.get_or_create(
        user=request.user,
        defaults={'full_name': request.user.get_full_name()
                  or request.user.username},
    )
    return trainer


@login_required
def profile(request):
    return redirect("accounts:profile_edit")


@login_required
def history(request):
    assessments = Assessment.objects.filter(
        athlete__trainer=_trainer_for(request)
    ).order_by("-created_at")
    context = {
        "assessments": assessments,
        "total_count": assessments.count(),
    }
    return render(request, "dashboard/history.html", context)


@login_required
def trainer_dashboard(request):

    trainer = _trainer_for(request)
    athletes = Athlete.objects.filter(trainer=trainer).order_by("-created_at")
    search_query = request.GET.get("q", "").strip()
    sport_filter = request.GET.get("sport", "").strip()

    if search_query:
        athletes = athletes.filter(
            Q(name__icontains=search_query)
            | Q(athlete_id__icontains=search_query)
        )

    if sport_filter:
        athletes = athletes.filter(sport__iexact=sport_filter)

    total_athletes = Athlete.objects.filter(trainer=trainer).count()
    total_assessments = Assessment.objects.filter(
        athlete__trainer=trainer).count()

    athlete_summary = []

    for athlete in athletes:
        assessments = list(
            Assessment.objects.filter(athlete=athlete).order_by("-created_at")
        )

        exercise_scores = {}
        for a in assessments:
            if (
                a.exercise not in exercise_scores
                and _is_recorded_exercise_assessment(a)
            ):
                exercise_scores[a.exercise] = a

        latest_date = assessments[0].created_at if assessments else None

        athlete_summary.append({
            "athlete": athlete,
            "completed": len(exercise_scores),
            "total_exercises": len(EXERCISE_LIST),
            "assessment_count": len(assessments),
            "latest_date": latest_date,
        })

    sports = Athlete.objects.filter(
        trainer=trainer
    ).values_list("sport", flat=True).distinct()
    sports = [sport for sport in sports if sport]

    context = {
        "athletes": athletes,
        "athlete_summary": athlete_summary,
        "total_athletes": total_athletes,
        "total_assessments": total_assessments,
        "search_query": search_query,
        "sport_filter": sport_filter,
        "sports": sports,
        "has_filters": bool(search_query or sport_filter),
        "filtered_count": athletes.count(),
    }

    return render(request, "trainers/dashboard.html", context)


@login_required
def add_athlete(request):
    if request.method == "POST":
        name = request.POST.get("name")
        athlete_id = request.POST.get("athlete_id")
        age = request.POST.get("age")
        gender = request.POST.get("gender")
        sport = request.POST.get("sport", "")
        email = request.POST.get("email", "")

        if name and athlete_id and age and gender:
            Athlete.objects.create(
                trainer=_trainer_for(request),
                name=name,
                athlete_id=athlete_id,
                age=int(age),
                gender=gender,
                sport=sport,
                email=email,
            )
            return redirect("dashboard:trainer_dashboard")

    return render(request, "dashboard/add_athlete.html")


@login_required
def athlete_detail(request, athlete_id):
    from django.shortcuts import get_object_or_404

    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request))
    assessments = list(athlete.assessments.all().order_by("-created_at"))

    exercise_scores = {}
    latest_by_exercise = {}
    for a in assessments:
        if a.exercise in EXERCISE_LIST and a.exercise not in latest_by_exercise:
            latest_by_exercise[a.exercise] = a
        if (
            a.exercise not in exercise_scores
            and _is_recorded_exercise_assessment(a)
        ):
            exercise_scores[a.exercise] = a

    exercise_rows = []
    for ex in EXERCISE_LIST:
        assessment = exercise_scores.get(ex)
        if assessment:
            exercise_rows.append({
                "name": ex,
                "assessment": assessment,
                "score_is_provisional": _has_provisional_score(assessment),
                "score_disclaimer": (
                    (assessment.details or {})
                    .get("reference_rating", {})
                    .get("disclaimer", "")
                ),
                "completed": True,
            })
        else:
            exercise_rows.append({
                "name": ex,
                "assessment": None,
                "latest_record": latest_by_exercise.get(ex),
                "completed": False,
            })

    # Build one chronological score chart for each exercise with comparisons.
    chart_assessments = {exercise: [] for exercise in EXERCISE_LIST}
    for assessment in reversed(list(assessments)):
        if assessment.exercise in chart_assessments:
            chart_assessments[assessment.exercise].append(assessment)

    exercise_charts = []
    svg_width = 500
    svg_height = 140
    padding_x = 40
    padding_y = 20
    usable_width = svg_width - (padding_x * 2)
    usable_height = svg_height - (padding_y * 2)

    for ex_name in EXERCISE_LIST:
        ex_assessments = [
            assessment
            for assessment in chart_assessments[ex_name]
            if (
                assessment.measurement_status == "valid"
                and _has_provisional_score(assessment)
            )
        ]
        if not ex_assessments:
            continue

        svg_points = []
        num_points = len(ex_assessments)
        for i, assessment in enumerate(ex_assessments):
            score = round(assessment.score, 1)
            if num_points > 1:
                x = padding_x + (i * usable_width / (num_points - 1))
            else:
                x = padding_x + (usable_width / 2)
            bounded_score = max(0, min(100, score))
            y = padding_y + usable_height - \
                (bounded_score / 100 * usable_height)
            svg_points.append({
                "x": round(x, 1),
                "y": round(y, 1),
                "date": assessment.created_at.strftime("%d %b"),
                "score": score,
            })

        polyline = " ".join(
            f"{point['x']},{point['y']}" for point in svg_points
        )
        polygon = (
            polyline
            + f" {svg_points[-1]['x']},{svg_height}"
            + f" {svg_points[0]['x']},{svg_height}"
        )
        exercise_charts.append({
            "exercise": ex_name,
            "points": svg_points,
            "polyline": polyline,
            "polygon": polygon,
            "count": num_points,
        })

    context = {
        "athlete": athlete,
        "assessments": assessments,
        "exercise_scores": exercise_scores,
        "exercise_rows": exercise_rows,
        "exercise_charts": exercise_charts,
        "completed_count": len(exercise_scores),
        "total_exercises": len(EXERCISE_LIST),
        "assessment_count": len(assessments),
        "latest_assessment_date": (
            assessments[0].created_at if assessments else None
        ),
    }
    return render(request, "dashboard/athlete_detail.html", context)


@login_required
def add_body_measurements(request, athlete_id):
    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request))

    if request.method == "POST":
        height_value = request.POST.get("height", "").strip()
        weight_value = request.POST.get("weight", "").strip()
        measurements = []

        if not height_value and not weight_value:
            messages.error(request, "Enter a height, a weight, or both.")
        else:
            try:
                height = float(height_value) if height_value else None
                weight = float(weight_value) if weight_value else None
                if (
                    (height is not None and (not math.isfinite(height) or height <= 0))
                    or (weight is not None and (not math.isfinite(weight) or weight <= 0))
                ):
                    raise ValueError
            except ValueError:
                messages.error(
                    request, "Enter valid positive numbers for each measurement.")
            else:
                if height is not None:
                    measurements.append(("Height", height))
                if weight is not None:
                    measurements.append(("Weight", weight))

                for exercise, measurement in measurements:
                    record = build_body_measurement_record(exercise, measurement)
                    Assessment.objects.create(
                        athlete=athlete,
                        exercise=exercise,
                        **record,
                    )
                return redirect("dashboard:athlete_detail", athlete_id=athlete.id)

    latest_height = athlete.assessments.filter(
        exercise="Height").order_by("-created_at").first()
    latest_weight = athlete.assessments.filter(
        exercise="Weight").order_by("-created_at").first()
    return render(request, "dashboard/add_body_measurements.html", {
        "athlete": athlete,
        "latest_height": latest_height,
        "latest_weight": latest_weight,
    })


@login_required
def exercise_selection(request, athlete_id):
    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request))

    EXERCISE_LIST = [
        {"name": "Vertical Jump", "command": "run_vertical_jump",
            "slug": "vertical-jump"},
        {"name": "Broad Jump", "command": "run_broad_jump", "slug": "broad-jump"},
        {"name": "Sit-ups", "command": "run_situps", "slug": "sit-ups"},
        {"name": "Sit & Reach", "command": "run_sit_reach", "slug": "sit-reach"},
        {"name": "Sprint", "command": "run_sprint", "slug": "sprint"},
        {"name": "Height", "command": None, "slug": None},
        {"name": "Weight", "command": None, "slug": None},
        {"name": "Medicine Ball Throw",
            "command": "run_medicine_ball", "slug": "medicine-ball"},
        {"name": "Shuttle Run", "command": "run_shuttle_run", "slug": "shuttle-run"},
        {"name": "Endurance Run", "command": "run_endurance", "slug": "endurance-run"},
    ]

    # Latest score per exercise — YEH LINE MISSING THI
    exercise_scores = {}
    for a in athlete.assessments.all():
        if a.exercise not in exercise_scores:
            exercise_scores[a.exercise] = a

    exercises = []
    for ex in EXERCISE_LIST:
        latest = exercise_scores.get(ex["name"])
        exercises.append({
            "name": ex["name"],
            "command": ex["command"],
            "slug": ex["slug"],
            "latest": latest,
            "available": ex["command"] is not None,
            "manual_measurement": ex["name"] in ("Height", "Weight"),
        })

    return render(request, "trainers/exercise_selection.html", {
        "athlete": athlete,
        "exercises": exercises,
    })


@login_required
def reports(request):
    trainer = _trainer_for(request)
    athletes = Athlete.objects.filter(trainer=trainer)
    assessments = Assessment.objects.filter(athlete__trainer=trainer)

    overall_average = None
    exercise_stats = []
    top_athletes = []
    weakest_exercises = []

    return render(request, "trainers/reports.html", {
        "total_athletes": athletes.count(),
        "total_assessments": assessments.count(),
        "overall_avg": (
            round(overall_average, 1)
            if overall_average is not None else None
        ),
        "exercise_count": len(exercise_stats),
        "exercise_stats": exercise_stats,
        "top_athletes": top_athletes,
        "weakest_exercises": weakest_exercises[:3], })


@login_required
def export_csv(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
    response["Content-Disposition"] = (
        'attachment; filename="fittrack_assessments.csv"'
    )

    writer = csv.writer(response)
    writer.writerow([
        "Date", "Athlete", "Athlete ID",
        "Exercise", "Measurement", "Unit", "Measurement Status",
        "Score", "Result", "Benchmark Status", "Benchmark Rating",
        "Benchmark Source", "Scoring Method Version", "Protocol Version",
        "Context",
    ])

    trainer = _trainer_for(request)
    assessments = Assessment.objects.filter(
        athlete__trainer=trainer
    ).select_related("athlete").order_by("-created_at")

    for assessment in assessments:
        writer.writerow([
            assessment.created_at.strftime("%Y-%m-%d %H:%M"),
            assessment.athlete.name,
            assessment.athlete.athlete_id,
            assessment.exercise,
            assessment.measurement,
            assessment.measurement_unit,
            assessment.measurement_status,
            round(assessment.score, 1) if assessment.score is not None else "",
            assessment.result,
            assessment.benchmark_status,
            assessment.benchmark_rating,
            assessment.benchmark_source,
            assessment.scoring_method_version,
            assessment.protocol_version,
            json_module.dumps(assessment.details, sort_keys=True),
        ])

    return response


@login_required
def edit_athlete(request, athlete_id):
    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request)
    )

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        age_value = request.POST.get("age", "").strip()
        gender = request.POST.get("gender", "").strip()
        sport = request.POST.get("sport", "").strip()
        email = request.POST.get("email", "").strip()

        try:
            age = int(age_value)
            if age < 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Enter a valid non-negative age.")
        else:
            valid_genders = {choice[0] for choice in Athlete.GENDER_CHOICES}
            if not name:
                messages.error(request, "Name is required.")
            elif gender not in valid_genders:
                messages.error(request, "Select a valid gender.")
            else:
                athlete.name = name
                athlete.age = age
                athlete.gender = gender
                athlete.sport = sport
                athlete.email = email or None
                athlete.save()
                return redirect(
                    "dashboard:athlete_detail", athlete_id=athlete.id
                )

    return render(request, "dashboard/edit_athlete.html", {
        "athlete": athlete,
    })


@login_required
def delete_athlete(request, athlete_id):
    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request)
    )

    if request.method == "POST":
        athlete.delete()
        return redirect("dashboard:trainer_dashboard")

    return render(request, "dashboard/delete_athlete.html", {
        "athlete": athlete,
    })


EXERCISE_SLUG_MAP = {
    "vertical-jump": {"name": "Vertical Jump", "command": "run_vertical_jump"},
    "broad-jump": {"name": "Broad Jump", "command": "run_broad_jump"},
    "sit-ups": {"name": "Sit-ups", "command": "run_situps"},
    "sit-reach": {"name": "Sit & Reach", "command": "run_sit_reach"},
    "sprint": {"name": "Sprint", "command": "run_sprint"},
    "medicine-ball": {"name": "Medicine Ball Throw", "command": "run_medicine_ball"},
    "shuttle-run": {"name": "Shuttle Run", "command": "run_shuttle_run"},
    "endurance-run": {"name": "Endurance Run", "command": "run_endurance"},
}


@login_required
def live_assessment(request, athlete_id, exercise_slug):
    athlete = get_object_or_404(
        Athlete, id=athlete_id, trainer=_trainer_for(request))
    exercise = EXERCISE_SLUG_MAP.get(exercise_slug)

    if not exercise:
        messages.error(request, "Unknown exercise.")
        return redirect("dashboard:exercise_selection", athlete_id=athlete.id)

    return render(request, "dashboard/live_assessment.html", {
        "athlete": athlete,
        "exercise_name": exercise["name"],
        "exercise_slug": exercise_slug,
    })


def _analyze_frame_sync(frame_data, exercise, state, athlete_height_cm=None):
    from dashboard.frame_processing import process_frame

    try:
        return JsonResponse(process_frame(
            frame_data, exercise, state, athlete_height_cm))
    except Exception as error:
        logger.exception("Frame analysis failed")
        return JsonResponse({"error": "Frame analysis failed"}, status=500)


@csrf_exempt
def analyze_frame(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        frame_data = request.POST.get("frame", "")
        exercise = request.POST.get("exercise", "")
        state_raw = request.POST.get("state", "{}")
        height_raw = request.POST.get("athlete_height_cm", "").strip()
        try:
            athlete_height_cm = float(height_raw) if height_raw else None
        except ValueError:
            return JsonResponse(
                {"error": "Athlete height must be a number in centimeters."},
                status=400,
            )
        if athlete_height_cm is not None and (
            not math.isfinite(athlete_height_cm)
            or not 100 <= athlete_height_cm <= 250
        ):
            return JsonResponse(
                {"error": "Athlete height must be between 100 and 250 cm."},
                status=400,
            )

        try:
            from dashboard.tasks import analyze_frame_task
            use_celery = getattr(settings, "USE_CELERY", False)
            if use_celery:
                task = analyze_frame_task.apply_async(
                    args=[
                        frame_data,
                        exercise,
                        state_raw,
                        athlete_height_cm,
                    ],
                    retry=False,
                )
                return JsonResponse({"task_id": task.id})
            raise RuntimeError("Celery disabled")
        except Exception:
            state = json_module.loads(state_raw or "{}")
            return _analyze_frame_sync(
                frame_data, exercise, state, athlete_height_cm)

    except Exception:
        logger.exception("Frame analysis request failed")
        return JsonResponse({"error": "Frame analysis failed"}, status=500)


def check_task(request, task_id):
    if request.method != "GET":
        return JsonResponse({"error": "GET required"}, status=405)

    try:
        from celery.result import AsyncResult

        task_result = AsyncResult(task_id)
        if task_result.ready():
            if task_result.failed():
                return JsonResponse({
                    "status": "error",
                    "error": "Frame analysis failed",
                })
            return JsonResponse({
                "status": "complete",
                "result": task_result.result,
            })
        return JsonResponse({"status": "pending"})
    except Exception:
        logger.exception("Frame analysis task lookup failed")
        return JsonResponse({
            "status": "error",
            "error": "Frame analysis service unavailable",
        }, status=503)


@csrf_exempt
def save_live_assessment(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        athlete_id = request.POST.get("athlete_id")
        exercise = request.POST.get("exercise", "")
        state_raw = request.POST.get("state", "{}")
        state = json_module.loads(state_raw or "{}")

        athlete = get_object_or_404(
            Athlete, athlete_id=athlete_id, trainer=_trainer_for(request))
        exercise_info = EXERCISE_SLUG_MAP.get(exercise)

        if not exercise_info:
            return JsonResponse({"error": "Unknown exercise"}, status=400)

        from dashboard.live_analysis import build_assessment_record
        record = build_assessment_record(exercise, state)

        if not record:
            return JsonResponse({
                "error": "Insufficient data to save. Complete the assessment first."
            }, status=422)

        record = apply_provisional_reference_rating(
            record,
            exercise_info["name"],
            athlete.gender,
        )
        assessment = Assessment.objects.create(
            athlete=athlete,
            exercise=exercise_info["name"],
            **record,
        )

        return JsonResponse({
            "success": True,
            "redirect_url": f"/trainer/athlete/{athlete.id}/",
            "assessment": {
                "measurement": assessment.measurement,
                "measurement_unit": assessment.measurement_unit,
                "measurement_status": assessment.measurement_status,
                "score": assessment.score,
                "result": assessment.result,
                "benchmark_status": assessment.benchmark_status,
                "benchmark_rating": assessment.benchmark_rating,
                "benchmark_source": assessment.benchmark_source,
                "scoring_method_version": assessment.scoring_method_version,
                "is_provisional": _has_provisional_score(assessment),
                "disclaimer": (
                    (assessment.details or {})
                    .get("reference_rating", {})
                    .get("disclaimer", "")
                ),
                "details": assessment.details,
            },
        })

    except Http404:
        return JsonResponse({"error": "Athlete not found"}, status=404)
    except Exception:
        logger.exception("Assessment save failed")
        return JsonResponse({"error": "Assessment could not be saved"}, status=500)
