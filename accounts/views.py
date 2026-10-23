from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout as auth_logout


@login_required
def post_login_redirect(request):
    """Login ke baad — naya user hai toh profile setup pe bhejo"""
    profile = request.user.profile

    if not profile.profile_completed:
        return redirect("accounts:profile_setup")

    return redirect("/trainer/")


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
        # Update user fields
        request.user.first_name = request.POST.get("first_name", "")
        request.user.last_name = request.POST.get("last_name", "")
        request.user.email = request.POST.get("email", "")
        request.user.save()

        # Update profile fields
        profile.phone = request.POST.get("phone", "")
        profile.organization = request.POST.get("organization", "")
        profile.save()

        # Password change
        new_password = request.POST.get("new_password")
        if new_password:
            request.user.set_password(new_password)
            request.user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)

        return redirect("dashboard:profile")

    return render(request, "accounts/profile_edit.html")


def custom_logout_confirm(request):
    if request.method == "POST":
        auth_logout(request)
        return redirect("/accounts/login/")
    return render(request, "account/logout.html")
