from django.contrib import admin
from .models import Athlete
# Register your models here.


@admin.register(Athlete)
class AthleteAdmin(admin.ModelAdmin):
    list_display = (
        "athlete_id",
        "name",
        "age",
        "gender",
        "sport",
        "email",
        "created_at",
    )
    search_fields = (
        "athlete_id",
        "name",
        "sport",
        "email",
    )
