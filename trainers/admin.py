from django.contrib import admin
from .models import Trainer


@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "organization", "created_at")
    search_fields = ("full_name", "user__email", "organization")
