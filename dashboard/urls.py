from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    # existing URLs (same rakho)
    path("", views.trainer_dashboard, name="trainer_dashboard"),
    path("athlete/add/", views.add_athlete, name="add_athlete"),
    path("athlete/<int:athlete_id>/", views.athlete_detail, name="athlete_detail"),
    path("athlete/<int:athlete_id>/edit/",
         views.edit_athlete, name="edit_athlete"),
    path("athlete/<int:athlete_id>/delete/",
         views.delete_athlete, name="delete_athlete"),
    path("athlete/<int:athlete_id>/exercises/",
         views.exercise_selection, name="exercise_selection"),
    path("athlete/<int:athlete_id>/measurements/",
         views.add_body_measurements, name="add_body_measurements"),
    path("history/", views.history, name="history"),
    path("reports/", views.reports, name="reports"),
    path("export/csv/", views.export_csv, name="export_csv"),
    path("profile/", views.profile, name="profile"),

    # NEW — live assessment URLs
    path("athlete/<int:athlete_id>/live/<str:exercise_slug>/",
         views.live_assessment, name="live_assessment"),
    path("analyze-frame/", views.analyze_frame, name="analyze_frame"),
    path("check-task/<str:task_id>/", views.check_task, name="check_task"),
    path("save-live-assessment/", views.save_live_assessment,
         name="save_live_assessment"),
]
