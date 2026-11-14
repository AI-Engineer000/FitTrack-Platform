import csv
import json as json_module
import logging
import math
import secrets
import string
from io import BytesIO
from django.contrib.auth.models import User
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse, Http404, HttpResponseServerError
from django.contrib.auth.views import PasswordChangeDoneView, PasswordChangeView
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Avg, Q
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils import timezone
from athletes.models import Athlete
from assessments.models import Assessment
from trainers.models import Trainer
from assessments.scoring import (
    REFERENCE_SCORING_METHOD_VERSION,
    apply_provisional_reference_rating,
    build_body_measurement_record,
)
from xhtml2pdf import pisa


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


class AthletePasswordChangeView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    PasswordChangeView,
):
    template_name = "dashboard/athlete_password_change.html"
    success_url = reverse_lazy("dashboard:athlete_password_change_done")

    def test_func(self):
        try:
            return self.request.user.athlete is not None
        except Athlete.DoesNotExist:
            return False


class AthletePasswordChangeDoneView(
    LoginRequiredMixin,
    UserPassesTestMixin,
    PasswordChangeDoneView,
):
    def test_func(self):
        try:
            return self.request.user.athlete is not None
        except Athlete.DoesNotExist:
            return False

    def get(self, request, *args, **kwargs):
        messages.success(request, "Password changed successfully!")
        return redirect("dashboard:athlete_dashboard")


@login_required
def profile(request):
    return redirect("accounts:profile_edit")


@login_required
def athlete_dashboard(request):
    try:
        athlete = request.user.athlete
    except Athlete.DoesNotExist:
        return redirect("dashboard:trainer_dashboard")

    assessments = list(
        Assessment.objects.filter(athlete=athlete).order_by("-created_at", "-pk")
    )
    valid_scores = [
        assessment for assessment in assessments
        if _has_provisional_score(assessment)
    ]
    average_score = (
        sum(assessment.score for assessment in valid_scores) / len(valid_scores)
        if valid_scores else None
    )

    exercise_score_totals = {}
    for assessment in valid_scores:
        exercise_score_totals.setdefault(assessment.exercise, []).append(
            assessment.score
        )
    exercise_averages = [
        {
            "exercise": exercise,
            "average_score": sum(scores) / len(scores),
        }
        for exercise, scores in exercise_score_totals.items()
    ]
    best_exercises = []
    weakest_exercises = []
    if exercise_averages:
        best_score = max(item["average_score"] for item in exercise_averages)
        weakest_score = min(item["average_score"] for item in exercise_averages)
        best_exercises = [
            item for item in exercise_averages
            if item["average_score"] == best_score
        ]
        weakest_exercises = [
            item for item in exercise_averages
            if item["average_score"] == weakest_score
        ]

    latest_measurements = {}
    for assessment in assessments:
        expected_unit = {"Height": "cm", "Weight": "kg"}.get(
            assessment.exercise
        )
        if (
            assessment.exercise in {"Height", "Weight"}
            and assessment.exercise not in latest_measurements
            and assessment.measurement_status == "valid"
            and assessment.measurement_unit == expected_unit
            and math.isfinite(assessment.measurement)
            and assessment.measurement > 0
        ):
            latest_measurements[assessment.exercise] = assessment.measurement

    bmi = None
    if {"Height", "Weight"} <= latest_measurements.keys():
        height_m = latest_measurements["Height"] / 100
        bmi = latest_measurements["Weight"] / (height_m * height_m)

    leaderboard = []
    leaderboard_rank = None
    leaderboard_tie_count = 0
    if athlete.trainer_id is not None:
        peer_averages = (
            Athlete.objects.filter(trainer_id=athlete.trainer_id)
            .annotate(
                average_score=Avg(
                    "assessments__score",
                    filter=Q(
                        assessments__score__isnull=False,
                        assessments__score__gt=-float("inf"),
                        assessments__score__lt=float("inf"),
                        assessments__measurement_status__in={"valid", "legacy"},
                        assessments__benchmark_status="available",
                        assessments__scoring_method_version=(
                            REFERENCE_SCORING_METHOD_VERSION
                        ),
                        assessments__benchmark_rating__gt="",
                    ),
                )
            )
            .values("id", "name", "average_score")
        )
        for peer in peer_averages:
            peer_average = peer["average_score"]
            if peer["id"] == athlete.id:
                peer_average = average_score
            if peer_average is not None and math.isfinite(peer_average):
                leaderboard.append({
                    "athlete_id": peer["id"],
                    "name": peer["name"],
                    "average_score": peer_average,
                    "ranking_score": round(peer_average, 2),
                })

        leaderboard.sort(
            key=lambda item: (-item["ranking_score"], item["name"].lower())
        )
        if average_score is not None:
            own_ranking_score = round(average_score, 2)
            leaderboard_rank = 1 + sum(
                item["ranking_score"] > own_ranking_score
                for item in leaderboard
            )
            leaderboard_tie_count = sum(
                item["ranking_score"] == own_ranking_score
                for item in leaderboard
            )
            for item in leaderboard:
                item["rank"] = 1 + sum(
                    other["ranking_score"] > item["ranking_score"]
                    for other in leaderboard
                )

    if valid_scores:
        latest_score = valid_scores[0].score
        coaching_insight = f"Your latest score is {latest_score:g}/100."
        if len(valid_scores) > 1 and latest_score < valid_scores[1].score:
            coaching_insight = (
                "Your latest score dropped compared to your previous assessment."
            )
    else:
        latest_score = None
        coaching_insight = "No valid scores are available yet."

    context = {
        "athlete": athlete,
        "assessments": assessments,
        "total_assessments": len(assessments),
        "average_score": average_score,
        "bmi": bmi,
        "exercise_averages": exercise_averages,
        "best_exercises": best_exercises,
        "weakest_exercises": weakest_exercises,
        "leaderboard": leaderboard,
        "leaderboard_rank": leaderboard_rank,
        "leaderboard_tie_count": leaderboard_tie_count,
        "leaderboard_athlete_count": len(leaderboard),
        "latest_score": latest_score,
        "coaching_insight": coaching_insight,
    }
    return render(request, "dashboard/athlete_dashboard.html", context)


@login_required
def download_athlete_pdf(request, athlete_id):
    try:
        athlete = request.user.athlete
    except Athlete.DoesNotExist:
        try:
            trainer = request.user.trainer
        except Trainer.DoesNotExist:
            return redirect("dashboard:trainer_dashboard")
        athlete = get_object_or_404(
            Athlete,
            id=athlete_id,
            trainer=trainer,
        )

    assessments = list(
        Assessment.objects.filter(athlete=athlete).order_by("-created_at", "-pk")
    )
    assessments = [
        assessment for assessment in assessments
        if not str(assessment.measurement).strip().lower().endswith("px")
        and not assessment.measurement_unit.strip().lower().endswith("px")
        and assessment.score is not None
        and math.isfinite(assessment.score)
        and assessment.benchmark_rating.strip().lower() not in {"", "not rated"}
    ]
    valid_scores = [
        assessment for assessment in assessments
        if _has_provisional_score(assessment)
    ]
    average_score = (
        sum(assessment.score for assessment in valid_scores) / len(valid_scores)
        if valid_scores else None
    )
    if valid_scores:
        latest_score = valid_scores[0].score
        coaching_insight = f"Your latest score is {latest_score:g}/100."
        if len(valid_scores) > 1 and latest_score < valid_scores[1].score:
            coaching_insight = (
                "Your latest score dropped compared to your previous assessment."
            )
    else:
        coaching_insight = "No valid scores are available yet."
    logo_url = request.build_absolute_uri(static("dashboard/images/logo.png"))
    logo_path = finders.find("dashboard/images/logo.png")
    if not logo_path:
        logger.error("PDF logo asset could not be found")
        return HttpResponseServerError("Unable to load the athlete report logo.")

    def pdf_link_callback(uri, rel):
        return logo_path if uri == logo_url else uri

    html = render(
        request,
        "dashboard/athlete_report_pdf.html",
        {
            "athlete": athlete,
            "assessments": assessments[:5],
            "assessment_count": len(assessments),
            "average_score": average_score,
            "coaching_insight": coaching_insight,
            "logo_url": logo_url,
            "generated_at": timezone.now(),
        },
    ).content.decode("utf-8")
    pdf_buffer = BytesIO()
    pdf_status = pisa.CreatePDF(
        html,
        dest=pdf_buffer,
        link_callback=pdf_link_callback,
    )
    if pdf_status.err:
        logger.error("PDF generation failed for athlete %s", athlete.pk)
        return HttpResponseServerError("Unable to generate the athlete report.")

    response = HttpResponse(pdf_buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="athlete-report-{athlete.athlete_id}.pdf"'
    )
    return response


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
            alphabet = string.ascii_letters + string.digits
            temporary_password = "".join(
                secrets.choice(alphabet) for _ in range(8)
            )
            try:
                with transaction.atomic():
                    athlete = Athlete.objects.create(
                        trainer=_trainer_for(request),
                        name=name,
                        athlete_id=athlete_id,
                        age=int(age),
                        gender=gender,
                        sport=sport,
                        email=email,
                    )
                    athlete_user = User.objects.create_user(
                        username=athlete.athlete_id,
                        email=f"{athlete.athlete_id}@fittrack.local",
                    )
                    athlete_user.set_password(temporary_password)
                    athlete_user.save(update_fields=["password"])
                    athlete.user = athlete_user
                    athlete.save(update_fields=["user"])
            except (IntegrityError, ValueError):
                messages.error(
                    request,
                    "Could not add the athlete. Check the athlete ID and age, "
                    "then try again.",
                )
                return redirect("dashboard:add_athlete")

            messages.success(
                request,
                f"Athlete Added! Login Username: {athlete.athlete_id} | "
                f"Temporary Password: {temporary_password}. Please save this "
                "now; it will not be shown again.",
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
    athletes = list(
        Athlete.objects.filter(trainer=trainer).order_by("name", "athlete_id")
    )
    athlete_reports = {
        athlete.pk: {
            "athlete": athlete,
            "total_assessments": 0,
            "valid_scores": [],
        }
        for athlete in athletes
    }
    assessments = Assessment.objects.filter(
        athlete__trainer=trainer
    ).iterator()
    valid_scores = []
    total_assessments = 0
    for assessment in assessments:
        report = athlete_reports[assessment.athlete_id]
        report["total_assessments"] += 1
        total_assessments += 1
        if _has_provisional_score(assessment):
            report["valid_scores"].append(assessment.score)
            valid_scores.append(assessment.score)

    overall_average = (
        sum(valid_scores) / len(valid_scores) if valid_scores else None
    )
    for report in athlete_reports.values():
        scores = report.pop("valid_scores")
        report["avg_score"] = (
            round(sum(scores) / len(scores), 1) if scores else None
        )

    exercise_stats = []
    top_athletes = []
    weakest_exercises = []

    return render(request, "trainers/reports.html", {
        "athlete_reports": list(athlete_reports.values()),
        "total_athletes": len(athletes),
        "total_assessments": total_assessments,
        "overall_average": (
            round(overall_average, 1)
            if overall_average is not None else None
        ),
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
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Login required"}, status=401)

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    try:
        frame_data = request.POST.get("frame", "")
        exercise = request.POST.get("exercise", "")
        state_raw = request.POST.get("state", "{}")
        athlete_height_cm = 170.0
        athlete_id = request.POST.get("athlete_id", "").strip()
        if athlete_id:
            athlete = get_object_or_404(
                Athlete,
                id=athlete_id,
                trainer=_trainer_for(request),
            )
            saved_height = athlete.assessments.filter(
                exercise="Height",
                measurement_unit="cm",
                measurement_status="valid",
            ).order_by("-created_at").values_list(
                "measurement", flat=True,
            ).first()
            if (
                saved_height is not None
                and math.isfinite(saved_height)
                and 100 <= saved_height <= 250
            ):
                athlete_height_cm = float(saved_height)

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

    except Http404:
        return JsonResponse({"error": "Athlete not found"}, status=404)
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
