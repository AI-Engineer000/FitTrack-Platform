from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views
app_name = "accounts"
urlpatterns = [
    path("post-login/", views.post_login_redirect, name="post_login"),
    path("profile/setup/", views.profile_setup, name="profile_setup"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path(
        "password/update/",
        auth_views.PasswordChangeView.as_view(
            template_name="registration/password_change_form.html",
            success_url=reverse_lazy("accounts:password_change_done"),
        ),
        name="password_change",
    ),
    path(
        "password/update/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="registration/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("logout/", views.custom_logout_confirm, name="custom_logout"),
]
