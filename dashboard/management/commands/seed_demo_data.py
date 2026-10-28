import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from trainers.models import Trainer
from athletes.models import Athlete
from assessments.models import Assessment


class Command(BaseCommand):
    help = "Seed realistic fitness assessment data across all 8 exercises plus height/weight for demo purposes."

    def handle(self, *args, **options):
        trainers = Trainer.objects.all()
        if not trainers.exists():
            self.stdout.write(self.style.ERROR("No trainers found. Please register or create a trainer first."))
            return

        # Target trainers
        target_trainers = []
        for t in trainers:
            uname = (t.user.username or "").lower()
            if any(k in uname for k in ["aakanksha", "btai", "admin", "trainer_a", "trainer_b"]):
                target_trainers.append(t)
        if not target_trainers:
            target_trainers = list(trainers)

        demo_athletes_spec = [
            {
                "name": "Rahul Sharma",
                "id_prefix": "RS",
                "age": 20,
                "gender": "male",
                "sport": "Athletics",
                "email": "rahul.sharma@mitsgwalior.in",
            },
            {
                "name": "Sneha Verma",
                "id_prefix": "SV",
                "age": 19,
                "gender": "female",
                "sport": "Badminton",
                "email": "sneha.verma@mitsgwalior.in",
            },
            {
                "name": "Aman Patel",
                "id_prefix": "AP",
                "age": 21,
                "gender": "male",
                "sport": "Football",
                "email": "aman.patel@mitsgwalior.in",
            },
        ]

        exercise_templates = {
            "Height": [(178.0, 90.0, "Excellent"), (178.0, 90.0, "Excellent")],
            "Weight": [(72.0, 90.0, "Excellent"), (70.5, 90.0, "Excellent")],
            "Vertical Jump": [(44.5, 76.0, "Good"), (49.2, 84.0, "Excellent"), (53.0, 92.0, "Excellent")],
            "Broad Jump": [(195.0, 72.0, "Good"), (212.0, 80.0, "Excellent"), (224.0, 86.0, "Excellent")],
            "Sit-ups": [(28.0, 68.0, "Good"), (36.0, 80.0, "Excellent"), (42.0, 90.0, "Excellent")],
            "Sit & Reach": [(22.5, 72.0, "Good"), (26.0, 80.0, "Excellent"), (29.5, 88.0, "Excellent")],
            "Sprint": [(12.8, 71.0, "Good"), (11.9, 78.0, "Good"), (11.2, 85.0, "Excellent")],
            "Medicine Ball Throw": [(310.0, 74.0, "Good"), (345.0, 82.0, "Excellent"), (370.0, 88.0, "Excellent")],
            "Shuttle Run": [(10.0, 68.0, "Good"), (14.0, 78.0, "Good"), (16.0, 84.0, "Excellent")],
            "Endurance Run": [(5.0, 65.0, "Good"), (7.0, 76.0, "Good"), (9.0, 85.0, "Excellent")],
        }

        now = timezone.now()
        date_offsets = [
            datetime.timedelta(days=14),
            datetime.timedelta(days=7),
            datetime.timedelta(days=1),
        ]

        total_assessments_created = 0

        for trainer in target_trainers:
            self.stdout.write(f"Seeding athletes & assessments for trainer: {trainer.full_name} ({trainer.user.username})")

            trainer_athletes = list(Athlete.objects.filter(trainer=trainer))

            # Create specific demo athletes for this trainer if not enough
            for idx, spec in enumerate(demo_athletes_spec):
                ath_id = f"MITS-{trainer.id:02d}-{spec['id_prefix']}{idx+1:02d}"
                # Check if exists anywhere
                existing_ath = Athlete.objects.filter(athlete_id=ath_id).first()
                if not existing_ath:
                    athlete = Athlete.objects.create(
                        trainer=trainer,
                        athlete_id=ath_id,
                        name=spec["name"],
                        age=spec["age"],
                        gender=spec["gender"],
                        sport=spec["sport"],
                        email=spec["email"],
                    )
                    trainer_athletes.append(athlete)
                elif existing_ath.trainer == trainer and existing_ath not in trainer_athletes:
                    trainer_athletes.append(existing_ath)

            for athlete in trainer_athletes:
                for exercise, records in exercise_templates.items():
                    existing_count = Assessment.objects.filter(athlete=athlete, exercise=exercise).count()
                    if existing_count < len(records):
                        for idx, (meas, score, res) in enumerate(records):
                            # Add natural variation
                            factor = 1.0 + (((athlete.id * 7 + idx) % 7) - 3) * 0.025
                            mod_meas = round(meas * factor, 1)
                            mod_score = round(min(98.0, max(45.0, score + (((athlete.id * 3 + idx) % 5) - 2) * 2.5)), 1)
                            created_time = now - date_offsets[idx % len(date_offsets)]

                            ass = Assessment.objects.create(
                                athlete=athlete,
                                exercise=exercise,
                                measurement=mod_meas,
                                score=mod_score,
                                result=res,
                            )
                            Assessment.objects.filter(id=ass.id).update(created_at=created_time)
                            total_assessments_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Successfully seeded demo data! Created {total_assessments_created} new assessments across {len(target_trainers)} trainers."
        ))
