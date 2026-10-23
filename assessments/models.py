from django.db import models
from athletes.models import Athlete


class Assessment(models.Model):

    EXERCISE_CHOICES = [
        ("Vertical Jump", "Vertical Jump"),
        ("Broad Jump", "Broad Jump"),
        ("Sit-ups", "Sit-ups"),
        ("Sit & Reach", "Sit & Reach"),
        ("Sprint", "Sprint"),
        ("Shuttle Run", "Shuttle Run"),
        ("Endurance Run", "Endurance Run"),
        ("Medicine Ball Throw", "Medicine Ball Throw"),
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
    score = models.FloatField()
    result = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.athlete.name} - {self.exercise} - {self.score}"
