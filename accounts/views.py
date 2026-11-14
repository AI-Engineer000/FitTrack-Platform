from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout
from django.contrib import messages

from accounts.forms import ProfileEditForm
from athletes.models import Athlete
from trainers.models import Trainer


@login_required
def post_login_redirect(request):
    try:
        request.user.athlete
    except Athlete.DoesNotExist:
        pass
    else:
        return redirect("dashboard:athlete_dashboard")

    try:
        request.user.trainer
    except Trainer.DoesNotExist:
        profile = request.user.profile
        if not profile.profile_completed:
            return redirect("accounts:profile_setup")
    else:
        return redirect("dashboard:trainer_dashboard")

    return redirect("dashboard:trainer_dashboard")


@login_required
def profile_setup(request):
    """Naya user — extra info lega"""
    profile = request.user.profile

    if request.method == "POST":
        # Form data process karo
        request.user.first_name = request.POST.get("first_name", "")
        request.user.last_name = request.POST.get("last_name", "")
        request.user.save()

        profile.phone = request.POST.get("phone", "")
        profile.organization = request.POST.get("organization", "")
        profile.profile_completed = True
        profile.save()

        return redirect("/trainer/")

    return render(request, "accounts/profile_setup.html")


@login_required
def profile_edit(request):
    """Profile edit page"""
    profile = request.user.profile

    if request.method == "POST":
        form = ProfileEditForm(
            request.POST,
            request.FILES,
            instance=profile,
            user=request.user,
        )
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated.")
            return redirect("accounts:profile_edit")
    else:
        form = ProfileEditForm(instance=profile, user=request.user)

    return render(
        request,
        "accounts/profile_edit.html",
        {"form": form},
    )


def custom_logout_confirm(request):
    if request.method == "POST":
        auth_logout(request)
        return redirect("/accounts/login/")
    return render(request, "account/logout.html")
