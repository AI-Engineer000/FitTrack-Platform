from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from assessments.models import Assessment
from assessments.scoring import REFERENCE_SCORING_METHOD_VERSION
from athletes.models import Athlete
from trainers.models import Trainer


class AthleteDashboardTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        trainer_user = user_model.objects.create_user(username="coach")
        self.trainer, _ = Trainer.objects.get_or_create(
            user=trainer_user,
            defaults={"full_name": "Coach"},
        )
        athlete_user = user_model.objects.create_user(username="runner")
        self.athlete = Athlete.objects.create(
            trainer=self.trainer,
            user=athlete_user,
            name="Runner",
            athlete_id="RUN-001",
            age=20,
            gender="Other",
            sport="Track",
        )
        self.client.force_login(athlete_user)

    def add_assessment(
        self,
        athlete,
        exercise,
        score=None,
        measurement=1,
        unit="",
        status="valid",
        scored=False,
    ):
        return Assessment.objects.create(
            athlete=athlete,
            exercise=exercise,
            measurement=measurement,
            measurement_unit=unit,
            measurement_status=status,
            score=score,
            result="Recorded",
            benchmark_status="available" if scored else "not_applicable",
            benchmark_rating="Average" if scored else "",
            scoring_method_version=(
                REFERENCE_SCORING_METHOD_VERSION if scored else "legacy"
            ),
        )

    def test_dashboard_calculates_metrics_and_trainer_scoped_leaderboard(self):
        self.add_assessment(self.athlete, "Sit-ups", 90, scored=True)
        self.add_assessment(self.athlete, "Sit-ups", 90, scored=True)
        self.add_assessment(self.athlete, "Sprint", 85, scored=True)
        self.add_assessment(self.athlete, "Sprint", 70, scored=True)
        self.add_assessment(
            self.athlete, "Height", measurement=180, unit="cm"
        )
        self.add_assessment(
            self.athlete, "Weight", measurement=72, unit="kg"
        )

        tied_athlete = Athlete.objects.create(
            trainer=self.trainer,
            name="Tied Athlete",
            athlete_id="RUN-002",
            age=20,
            gender="Other",
            sport="Track",
        )
        self.add_assessment(tied_athlete, "Sit-ups", 83.75, scored=True)
        higher_athlete = Athlete.objects.create(
            trainer=self.trainer,
            name="Higher Athlete",
            athlete_id="RUN-003",
            age=20,
            gender="Other",
            sport="Track",
        )
        self.add_assessment(higher_athlete, "Sit-ups", 90, scored=True)
        Athlete.objects.create(
            trainer=self.trainer,
            name="Unscored Athlete",
            athlete_id="RUN-004",
            age=20,
            gender="Other",
            sport="Track",
        )

        other_trainer_user = get_user_model().objects.create_user(
            username="other-coach"
        )
        other_trainer, _ = Trainer.objects.get_or_create(
            user=other_trainer_user,
            defaults={"full_name": "Other Coach"},
        )
        other_athlete = Athlete.objects.create(
            trainer=other_trainer,
            name="Outside Athlete",
            athlete_id="RUN-005",
            age=20,
            gender="Other",
            sport="Track",
        )
        self.add_assessment(other_athlete, "Sit-ups", 100, scored=True)

        response = self.client.get(reverse("dashboard:athlete_dashboard"))

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertEqual(context["total_assessments"], 6)
        self.assertEqual(context["average_score"], 83.75)
        self.assertAlmostEqual(context["bmi"], 72 / (1.8**2))
        self.assertEqual(context["leaderboard_rank"], 2)
        self.assertEqual(context["leaderboard_tie_count"], 2)
        self.assertEqual(context["leaderboard_athlete_count"], 3)
        self.assertEqual(
            [item["exercise"] for item in context["best_exercises"]],
            ["Sit-ups"],
        )
        self.assertEqual(
            [item["exercise"] for item in context["weakest_exercises"]],
            ["Sprint"],
        )
        self.assertIn(
            "Your latest score dropped compared to your previous assessment.",
            context["coaching_insight"],
        )
        self.assertNotIn(
            "Outside Athlete",
            [item["name"] for item in context["leaderboard"]],
        )

    def test_athlete_without_assessments_has_graceful_empty_metrics(self):
        response = self.client.get(reverse("dashboard:athlete_dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_assessments"], 0)
        self.assertIsNone(response.context["average_score"])
        self.assertIsNone(response.context["bmi"])
        self.assertIsNone(response.context["leaderboard_rank"])
        self.assertEqual(response.context["leaderboard"], [])
        self.assertEqual(
            response.context["coaching_insight"],
            "No valid scores are available yet.",
        )

    def test_user_without_athlete_profile_is_redirected(self):
        user = get_user_model().objects.create_user(username="not-an-athlete")
        self.client.force_login(user)

        response = self.client.get(reverse("dashboard:athlete_dashboard"))

        self.assertRedirects(
            response,
            reverse("dashboard:trainer_dashboard"),
            fetch_redirect_response=False,
        )

    def test_post_login_redirect_sends_athlete_to_athlete_dashboard(self):
        response = self.client.get(reverse("accounts:post_login"))

        self.assertRedirects(
            response,
            reverse("dashboard:athlete_dashboard"),
            fetch_redirect_response=False,
        )

    def test_athlete_can_change_password_and_gets_dashboard_success_message(self):
        athlete_user = self.athlete.user
        athlete_user.set_password("OldAthletePassword123!")
        athlete_user.save(update_fields=["password"])
        self.client.force_login(athlete_user)

        page = self.client.get(reverse("dashboard:athlete_password_change"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Change Password")
        self.assertContains(page, "Athlete Account")
        self.assertContains(page, "data-password-toggle")

        response = self.client.post(
            reverse("dashboard:athlete_password_change"),
            {
                "old_password": "OldAthletePassword123!",
                "new_password1": "NewAthletePassword789!",
                "new_password2": "NewAthletePassword789!",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertRedirects(response, reverse("dashboard:athlete_dashboard"))
        self.assertContains(response, "Password changed successfully!")
        athlete_user.refresh_from_db()
        self.assertTrue(athlete_user.check_password("NewAthletePassword789!"))

    def test_trainer_cannot_use_athlete_password_change_page(self):
        self.client.force_login(self.trainer.user)

        response = self.client.get(reverse("dashboard:athlete_password_change"))

        self.assertEqual(response.status_code, 403)

    def test_post_login_redirect_keeps_trainer_on_trainer_dashboard(self):
        self.client.force_login(self.trainer.user)

        response = self.client.get(reverse("accounts:post_login"))

        self.assertRedirects(
            response,
            reverse("dashboard:trainer_dashboard"),
            fetch_redirect_response=False,
        )

    def test_athlete_pdf_ignores_requested_athlete_id(self):
        other_athlete = Athlete.objects.create(
            trainer=self.trainer,
            name="Other Runner",
            athlete_id="RUN-OTHER",
            age=21,
            gender="Other",
            sport="Track",
        )
        rendered = {}

        def fake_create_pdf(source, dest, **kwargs):
            rendered["source"] = source
            dest.write(b"%PDF-test")
            return SimpleNamespace(err=0)

        with patch("dashboard.views.pisa.CreatePDF", side_effect=fake_create_pdf):
            response = self.client.get(
                reverse(
                    "dashboard:download_athlete_pdf",
                    args=(other_athlete.id,),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Runner", rendered["source"])
        self.assertNotIn("Other Runner", rendered["source"])

    def test_trainer_can_download_own_athlete_pdf(self):
        trainer_user = self.trainer.user
        self.client.force_login(trainer_user)

        def fake_create_pdf(source, dest, **kwargs):
            dest.write(b"%PDF-test")
            return SimpleNamespace(err=0)

        with patch("dashboard.views.pisa.CreatePDF", side_effect=fake_create_pdf):
            response = self.client.get(
                reverse(
                    "dashboard:download_athlete_pdf",
                    args=(self.athlete.id,),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_trainer_cannot_download_another_trainers_athlete_pdf(self):
        other_trainer_user = get_user_model().objects.create_user(
            username="other-coach"
        )
        other_trainer, _ = Trainer.objects.get_or_create(
            user=other_trainer_user,
            defaults={"full_name": "Other Coach"},
        )
        other_athlete = Athlete.objects.create(
            trainer=other_trainer,
            name="Outside Runner",
            athlete_id="RUN-OUTSIDE",
            age=21,
            gender="Other",
            sport="Track",
        )
        self.client.force_login(self.trainer.user)

        response = self.client.get(
            reverse(
                "dashboard:download_athlete_pdf",
                args=(other_athlete.id,),
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_pdf_endpoint_renders_a_pdf_document(self):
        response = self.client.get(
            reverse(
                "dashboard:download_athlete_pdf",
                args=(self.athlete.id,),
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF-"))
        self.assertIn(b"/Subtype /Image", response.content)

    def test_pdf_includes_only_processed_assessments_and_absolute_logo_url(self):
        self.add_assessment(
            self.athlete, "Sprint", 90, measurement=18.5, unit="cm", scored=True
        )
        self.add_assessment(
            self.athlete, "Vertical Jump", 85, measurement=20, unit="px",
            scored=True,
        )
        self.add_assessment(self.athlete, "Sit-ups")
        not_rated = self.add_assessment(
            self.athlete, "Broad Jump", 75, scored=True
        )
        not_rated.benchmark_rating = "Not Rated"
        not_rated.save(update_fields=["benchmark_rating"])
        rendered = {}

        def fake_create_pdf(source, dest, link_callback):
            rendered["source"] = source
            rendered["logo_path"] = link_callback(
                "http://testserver/static/dashboard/images/logo.png", None
            )
            dest.write(b"%PDF-test")
            return SimpleNamespace(err=0)

        with patch("dashboard.views.pisa.CreatePDF", side_effect=fake_create_pdf):
            response = self.client.get(
                reverse(
                    "dashboard:download_athlete_pdf",
                    args=(self.athlete.id,),
                )
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            'src="http://testserver/static/dashboard/images/logo.png"',
            rendered["source"],
        )
        self.assertTrue(rendered["logo_path"].endswith("logo.png"))
        self.assertIn("Sprint", rendered["source"])
        self.assertNotIn("Vertical Jump", rendered["source"])
        self.assertNotIn("Sit-ups", rendered["source"])
        self.assertNotIn("Broad Jump", rendered["source"])
