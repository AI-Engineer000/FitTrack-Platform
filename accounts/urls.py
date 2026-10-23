from django.urls import path
from . import views
app_name = "accounts"
urlpatterns = [
    path("post-login/", views.post_login_redirect, name="post_login"),
    path("profile/setup/", views.profile_setup, name="profile_setup"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("logout/", views.custom_logout_confirm, name="custom_logout"),
]
