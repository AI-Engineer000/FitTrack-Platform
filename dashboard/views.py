import csv
import json as json_module
from django.conf import settings
from django.http import JsonResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q
from athletes.models import Athlete
from assessments.models import Assessment
from trainers.models import Trainer
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
        assessments = Assessment.objects.filter(
            athlete=athlete
        ).order_by("-created_at")

        # Exercise-wise latest score
        exercise_scores = {}
        for a in assessments:
            if a.exercise not in exercise_scores:
                exercise_scores[a.exercise] = a

        # Average score
        if exercise_scores:
            avg_score = round(
                sum(a.score for a in exercise_scores.values()) /
                len(exercise_scores)
            )
        else:
            avg_score = None

        # Latest date
        latest_date = assessments.first().created_at if assessments else None

        athlete_summary.append({
            "athlete": athlete,
            "avg_score": avg_score,
            "completed": len(exercise_scores),
            "total_exercises": len(EXERCISE_LIST),
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
    assessments = athlete.assessments.all().order_by("-created_at")

    # Exercise-wise latest score
    exercise_scores = {}
    for a in assessments:
        if a.exercise not in exercise_scores:
            exercise_scores[a.exercise] = a

    # Overall score
    if exercise_scores:
        overall_score = round(
            sum(a.score for a in exercise_scores.values()) / len(exercise_scores)
        )
    else:
        overall_score = 0

    # Ring offset for SVG
    ring_offset = 301.6 - (301.6 * overall_score / 100)

    # Best and weakest
    best_exercise = None
    weakest_exercise = None

    if exercise_scores:
        best_name = max(exercise_scores,
                        key=lambda k: exercise_scores[k].score)
        best_exercise = exercise_scores[best_name]

        weak_name = min(exercise_scores,
                        key=lambda k: exercise_scores[k].score)
        weakest_exercise = exercise_scores[weak_name]

    # Exercise rows — completed vs pending
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

    exercise_rows = []
    for ex in EXERCISE_LIST:
        if ex in exercise_scores:
            exercise_rows.append({
                "name": ex,
                "assessment": exercise_scores[ex],
                "completed": True,
            })
        else:
            exercise_rows.append({
                "name": ex,
                "assessment": None,
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
        ex_assessments = chart_assessments[ex_name]
        if len(ex_assessments) < 2:
            continue

        svg_points = []
        num_points = len(ex_assessments)
        for i, assessment in enumerate(ex_assessments):
            score = round(assessment.score, 1)
            x = padding_x + (i * usable_width / (num_points - 1))
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
        "overall_score": overall_score,
        "ring_offset": round(ring_offset, 2),
        "best_exercise": best_exercise,
        "weakest_exercise": weakest_exercise,
        "completed_count": len(exercise_scores),
        "total_exercises": len(EXERCISE_LIST),
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
                if (height is not None and height <= 0) or (weight is not None and weight <= 0):
                    raise ValueError
            except ValueError:
                messages.error(
                    request, "Enter valid positive numbers for each measurement.")
            else:
                if height is not None:
                    if 150 <= height <= 200:
                        height_score, height_result = 90, "Excellent"
                    elif 140 <= height < 150 or 200 < height <= 210:
                        height_score, height_result = 70, "Good"
                    else:
                        height_score, height_result = 50, "Average"
                    measurements.append(
                        ("Height", height, height_score, height_result))

                if weight is not None:
                    height_assessment = None
                    if height is None:
                        height_assessment = athlete.assessments.filter(
                            exercise="Height").order_by("-created_at").first()
                    bmi_height = height if height is not None else (
                        height_assessment.measurement if height_assessment else None)
                    if bmi_height:
                        bmi = weight / ((bmi_height / 100) ** 2)
                        if 18.5 <= bmi < 25:
                            weight_score, weight_result = 90, "Excellent"
                        elif 25 <= bmi < 30:
                            weight_score, weight_result = 70, "Good"
                        elif bmi >= 30:
                            weight_score, weight_result = 50, "Average"
                        else:
                            weight_score, weight_result = 40, "Needs Improvement"
                    else:
                        weight_score, weight_result = 50, "Recorded"
                    measurements.append(
                        ("Weight", weight, weight_score, weight_result))

                for exercise, measurement, score, result in measurements:
                    Assessment.objects.create(
                        athlete=athlete,
                        exercise=exercise,
                        measurement=measurement,
                        score=score,
                        result=result,
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

    overall_average = assessments.aggregate(value=Avg("score"))["value"]
    exercise_stats = []
    for item in assessments.values("exercise").annotate(
            count=Count("id"), avg_score=Avg("score")).order_by("-avg_score"):
        average = round(item["avg_score"], 1)
        exercise_stats.append({
            "name": item["exercise"],
            "count": item["count"],
            "avg_score": average,
            "chart_width": max(0, min(100, average)),
        })

    top_athletes = list(athletes.annotate(
        avg_score=Avg("assessments__score"),
        assessment_count=Count("assessments"),
    ).filter(assessment_count__gt=0).order_by(
        "-avg_score", "name")[:5])
    weakest_exercises = sorted(
        exercise_stats, key=lambda item: item["avg_score"])

    return render(request, "trainers/reports.html", {
        "total_athletes": athletes.count(),
        "total_assessments": assessments.count(),
        "overall_avg": round(overall_average, 1) if overall_average is not None else 0,
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
        "Exercise", "Measurement", "Score", "Result",
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
            round(assessment.score, 1),
            assessment.result,
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


def _analyze_frame_sync(frame_data, exercise, state):
    from dashboard.frame_processing import process_frame

    try:
        return JsonResponse(process_frame(frame_data, exercise, state))
    except Exception as error:
        return JsonResponse({"error": str(error)})


@csrf_exempt
def analyze_frame(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        frame_data = request.POST.get("frame", "")
        exercise = request.POST.get("exercise", "")
        state_raw = request.POST.get("state", "{}")

        try:
            from dashboard.tasks import analyze_frame_task
            use_celery = getattr(settings, "USE_CELERY", False)
            if use_celery:
                task = analyze_frame_task.apply_async(args=[frame_data, exercise, state_raw], retry=False)
                return JsonResponse({"task_id": task.id})
            raise RuntimeError("Celery disabled")
        except Exception:
            state = json_module.loads(state_raw or "{}")
            return _analyze_frame_sync(frame_data, exercise, state)

    except Exception as error:
        return JsonResponse({"error": str(error)})


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
                    "error": str(task_result.result),
                })
            return JsonResponse({
                "status": "complete",
                "result": task_result.result,
            })
        return JsonResponse({"status": "pending"})
    except Exception as error:
        return JsonResponse({"status": "error", "error": str(error)}, status=503)


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
            return JsonResponse({"error": "Unknown exercise"})

        from dashboard.live_analysis import build_assessment_record
        record = build_assessment_record(exercise, state)

        if not record:
            return JsonResponse({
                "error": "Insufficient data to save. Complete the assessment first."
            })

        Assessment.objects.create(
            athlete=athlete,
            exercise=exercise_info["name"],
            measurement=record["measurement"],
            score=record["score"],
            result=record["result"],
        )

        return JsonResponse({
            "success": True,
            "redirect_url": f"/trainer/athlete/{athlete.id}/",
        })

    except Http404:
        return JsonResponse({"error": "Athlete not found"}, status=404)
    except Exception as e:
        return JsonResponse({"error": str(e)})
