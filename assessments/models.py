from django.db import models
from athletes.models import Athlete


class Assessment(models.Model):

    EXERCISE_CHOICES = [
        ("Vertical Jump", "Vertical Jump"),
        ("Broad Jump", "Broad Jump"),
        ("Sit-ups", "Sit-ups"),
        ("Sit & Reach", "Sit & Reach"),
        ("Sprint", "Sprint"),
        ("Height", "Height"),
        ("Weight", "Weight"),
        ("Shuttle Run", "Shuttle Run"),
        ("Endurance Run", "Endurance Run"),
        ("Medicine Ball Throw", "Medicine Ball Throw"),
    ]
    MEASUREMENT_STATUS_CHOICES = [
        ("valid", "Valid"),
        ("uncalibrated", "Uncalibrated"),
        ("unvalidated", "Unvalidated"),
        ("incomplete", "Incomplete"),
        ("invalid", "Invalid"),
        ("legacy", "Historical record; method unknown"),
    ]
    BENCHMARK_STATUS_CHOICES = [
        ("available", "Available"),
        ("unavailable", "Unavailable"),
        ("not_applicable", "Not applicable"),
        ("legacy", "Historical record; method unknown"),
    ]
    athlete = models.ForeignKey(
        Athlete,
        on_delete=models.CASCADE,
        related_name="assessments"
    )
    exercise = models.CharField(
        max_length=50,
        choices=EXERCISE_CHOICES
    )
    measurement = models.FloatField()
    measurement_unit = models.CharField(max_length=16, blank=True, default="")
    measurement_status = models.CharField(
        max_length=16,
        choices=MEASUREMENT_STATUS_CHOICES,
        default="legacy",
    )
    score = models.FloatField(null=True, blank=True)
    result = models.CharField(max_length=50)
    benchmark_status = models.CharField(
        max_length=16,
        choices=BENCHMARK_STATUS_CHOICES,
        default="legacy",
    )
    benchmark_rating = models.CharField(max_length=50, blank=True, default="")
    benchmark_source = models.CharField(max_length=255, blank=True, default="")
    scoring_method_version = models.CharField(
        max_length=64, blank=True, default="legacy"
    )
    protocol_version = models.CharField(max_length=64, blank=True, default="legacy")
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.athlete.name} - {self.exercise} - {self.score}"
