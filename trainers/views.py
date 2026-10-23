from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Avg, Max
from .forms import TrainerSignupForm, TrainerLoginForm
from .models import Trainer
from athletes.models import Athlete
from assessments.models import Assessment


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("trainer_dashboard")

    if request.method == "POST":
        form = TrainerSignupForm(request.POST)

        if form.is_valid():
            user = form.save(commit=False)
            user.email = form.cleaned_data["email"]
            user.save()

            Trainer.objects.create(
                user=user,
                full_name=form.cleaned_data["full_name"],
                organization=form.cleaned_data.get("organization", ""),
                phone=form.cleaned_data.get("phone", ""),
            )

            messages.success(request, "Account created. Please login.")
            return redirect("login")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = TrainerSignupForm()

    return render(request, "trainers/signup.html", {"form": form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect("trainer_dashboard")

    if request.method == "POST":
        form = TrainerLoginForm(request.POST)

        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                return redirect("trainer_dashboard")
            else:
                messages.error(request, "Invalid username or password")
    else:
        form = TrainerLoginForm()

    return render(request, "trainers/login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.success(request, "Logged out successfully")
    return redirect("login")


@login_required
def trainer_dashboard(request):
    """Trainer ka dashboard — saare athletes ki list + stats"""

    try:
        trainer = request.user.trainer
    except Trainer.DoesNotExist:
        messages.error(request, "Trainer profile not found")
        return redirect("logout")

    # Saare athletes with assessment count
    athletes = Athlete.objects.filter(trainer=trainer).annotate(
        assessment_count=Count("assessments"),
        latest_score=Max("assessments__score"),
    ).order_by("-created_at")

    # Overall stats
    total_athletes = athletes.count()

    total_assessments = Assessment.objects.filter(
        athlete__trainer=trainer
    ).count()

    # Har athlete ka average score
    athlete_summary = []
    for athlete in athletes:
        assessments = Assessment.objects.filter(
            athlete=athlete).order_by("-created_at")

        if assessments.exists():
            # Latest assessment per exercise
            latest_per_exercise = {}
            for a in assessments:
                if a.exercise not in latest_per_exercise:
                    latest_per_exercise[a.exercise] = a

            avg_score = round(
                sum(a.score for a in latest_per_exercise.values()) /
                len(latest_per_exercise)
            ) if latest_per_exercise else 0

            latest_date = assessments.first().created_at
            completed = len(latest_per_exercise)
        else:
            avg_score = 0
            latest_date = None
            completed = 0

        athlete_summary.append({
            "athlete": athlete,
            "avg_score": avg_score,
            "latest_date": latest_date,
            "completed": completed,
            "total_exercises": 10,
        })

    # Sort by avg score (highest first)
    athlete_summary.sort(key=lambda x: x["avg_score"], reverse=True)

    context = {
        "trainer": trainer,
        "athlete_summary": athlete_summary,
        "total_athletes": total_athletes,
        "total_assessments": total_assessments,
    }

    return render(request, "trainers/dashboard.html", context)
