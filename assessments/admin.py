from django.contrib import admin
from .models import Assessment
# Register your models here.


@admin.register(Assessment)
class AssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "athlete",
        "exercise",
        "measurement",
        "measurement_unit",
        "measurement_status",
        "score",
        "result",
        "benchmark_status",
        "scoring_method_version",
        "created_at",
    )

    list_filter = (
        "exercise",
        "result",
        "measurement_status",
        "benchmark_status",
    )
    search_fields = (
        "athlete__name",
        "athlete__athlete_id",
    )
