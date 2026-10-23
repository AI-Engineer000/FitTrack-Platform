from django.contrib import admin
from .models import Assessment
# Register your models here.


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "athlete",
        "exercise",
        "measurement",
        "score",
        "result",
        "created_at",
    )

    list_filter = (
        "exercise",
        "result",
    )
    search_fields = (
        "athlete_name",
        "athlete_athlete_id",
    )
