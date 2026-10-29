from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import csv
from io import StringIO

from athletes.models import Athlete
from assessments.models import Assessment
from trainers.models import Trainer


class DashboardFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="trainer1",
            email="trainer1@example.com",
            password="testpass123",
        )
        self.trainer, _ = Trainer.objects.get_or_create(
            user=self.user,
            defaults={
                "full_name": "Test Trainer",
                "organization": "FitTrack",
            },
        )
        self.client.force_login(self.user)

    def test_add_athlete_creates_athlete_for_trainer(self):
        response = self.client.post(
            reverse("dashboard:add_athlete"),
            {
                "name": "John Athlete",
                "athlete_id": "A-1001",
                "age": 21,
                "gender": "Male",
                "sport": "Football",
                "email": "john@example.com",
            },
        )

        self.assertEqual(response.status_code, 302)
        athlete = Athlete.objects.get(athlete_id="A-1001")
        self.assertEqual(athlete.trainer, self.trainer)

    def test_dashboard_profile_and_history_routes_exist(self):
        self.assertTrue(reverse("dashboard:profile"))
        self.assertTrue(reverse("dashboard:history"))


class TrainerAccessControlTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user_a = user_model.objects.create_user(
            username="trainer_a",
            password="testpass123",
        )
        self.user_b = user_model.objects.create_user(
            username="trainer_b",
            password="testpass123",
        )
        self.trainer_a = Trainer.objects.get(user=self.user_a)
        self.trainer_a.full_name = "Trainer A"
        self.trainer_a.save(update_fields=["full_name"])
        self.trainer_b = Trainer.objects.get(user=self.user_b)
        self.trainer_b.full_name = "Trainer B"
        self.trainer_b.save(update_fields=["full_name"])
        self.athlete_a = Athlete.objects.create(
            trainer=self.trainer_a,
            name="Athlete A Only",
            athlete_id="TP001",
            age=20,
            gender="Other",
            sport="Test Sport A",
        )
        self.athlete_b = Athlete.objects.create(
            trainer=self.trainer_b,
            name="Athlete B Only",
            athlete_id="TA001",
            age=21,
            gender="Other",
            sport="Test Sport B",
        )
        self.assessment_a = Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Vertical Jump",
            measurement=42,
            score=81,
            result="Good A",
        )
        self.assessment_b = Assessment.objects.create(
            athlete=self.athlete_b,
            exercise="Vertical Jump",
            measurement=19,
            score=32,
            result="Needs Improvement B",
        )
        self.client_a = self.client_class()
        self.client_b = self.client_class()
        self.client_a.force_login(self.user_a)
        self.client_b.force_login(self.user_b)

    def test_trainer_a_dashboard_lists_only_own_athletes(self):
        response = self.client_a.get(reverse("dashboard:trainer_dashboard"))

        self.assertEqual(response.status_code, 200)
        athlete_ids = {
            item["athlete"].pk for item in response.context["athlete_summary"]}
        self.assertEqual(athlete_ids, {self.athlete_a.pk})

    def test_trainer_b_dashboard_lists_only_own_athletes(self):
        response = self.client_b.get(reverse("dashboard:trainer_dashboard"))

        self.assertEqual(response.status_code, 200)
        athlete_ids = {
            item["athlete"].pk for item in response.context["athlete_summary"]}
        self.assertEqual(athlete_ids, {self.athlete_b.pk})

    def test_cross_access_athlete_detail_returns_404(self):
        self.assert_cross_access_404("athlete_detail")

    def test_cross_access_edit_returns_404(self):
        self.assert_cross_access_404("edit_athlete")

    def test_cross_access_delete_returns_404(self):
        self.assert_cross_access_404("delete_athlete")

    def test_cross_access_exercise_selection_returns_404(self):
        self.assert_cross_access_404("exercise_selection")

    def test_cross_access_live_assessment_returns_404(self):
        self.assert_cross_access_404(
            "live_assessment",
            kwargs={"exercise_slug": "vertical-jump"},
        )

    def test_cross_access_body_measurements_returns_404(self):
        self.assert_cross_access_404("add_body_measurements")

    def test_reports_are_isolated_by_trainer(self):
        response_a = self.client_a.get(reverse("dashboard:reports"))
        response_b = self.client_b.get(reverse("dashboard:reports"))

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_a.context["total_athletes"], 1)
        self.assertEqual(response_a.context["total_assessments"], 1)
        self.assertEqual(response_b.context["total_athletes"], 1)
        self.assertEqual(response_b.context["total_assessments"], 1)
        self.assertEqual(
            [athlete.pk for athlete in response_a.context["top_athletes"]],
            [self.athlete_a.pk],
        )
        self.assertEqual(
            [athlete.pk for athlete in response_b.context["top_athletes"]],
            [self.athlete_b.pk],
        )

    def test_csv_export_contains_only_own_assessments(self):
        response_a = self.client_a.get(reverse("dashboard:export_csv"))
        response_b = self.client_b.get(reverse("dashboard:export_csv"))
        rows_a = list(csv.reader(
            StringIO(response_a.content.decode("utf-8-sig"))))
        rows_b = list(csv.reader(
            StringIO(response_b.content.decode("utf-8-sig"))))

        self.assertEqual(response_a.status_code, 200)
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual([row[1] for row in rows_a[1:]], ["Athlete A Only"])
        self.assertEqual([row[1] for row in rows_b[1:]], ["Athlete B Only"])
        self.assertNotIn("Athlete B Only",
                         response_a.content.decode("utf-8-sig"))
        self.assertNotIn("Athlete A Only",
                         response_b.content.decode("utf-8-sig"))

    def assert_cross_access_404(self, view_name, kwargs=None):
        route_kwargs = {"athlete_id": self.athlete_a.pk}
        if kwargs:
            route_kwargs.update(kwargs)
        response = self.client_b.get(
            reverse(f"dashboard:{view_name}", kwargs=route_kwargs))
        self.assertEqual(response.status_code, 404)


class LiveAssessmentEndpointTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user_a = user_model.objects.create_user(
            username="trainer_live_a",
            password="testpass123",
        )
        self.user_b = user_model.objects.create_user(
            username="trainer_live_b",
            password="testpass123",
        )
        self.trainer_a = Trainer.objects.get(user=self.user_a)
        self.trainer_a.full_name = "Trainer Live A"
        self.trainer_a.save(update_fields=["full_name"])
        self.trainer_b = Trainer.objects.get(user=self.user_b)
        self.trainer_b.full_name = "Trainer Live B"
        self.trainer_b.save(update_fields=["full_name"])

        self.athlete_a = Athlete.objects.create(
            trainer=self.trainer_a,
            name="Live Athlete A",
            athlete_id="LA001",
            age=22,
            gender="Male",
            sport="Running",
        )
        self.client_a = self.client_class()
        self.client_b = self.client_class()
        self.client_a.force_login(self.user_a)
        self.client_b.force_login(self.user_b)

    def test_analyze_frame_rejects_non_post(self):
        response = self.client_a.get(reverse("dashboard:analyze_frame"))
        self.assertEqual(response.status_code, 405)

    def test_save_live_assessment_requires_auth(self):
        anonymous_client = self.client_class()
        response = anonymous_client.post(
            reverse("dashboard:save_live_assessment"))
        self.assertEqual(response.status_code, 401)

    def test_save_live_assessment_saves_valid_record(self):
        response = self.client_a.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": '{"reps": 30}',
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("success"))
        assessment = Assessment.objects.filter(
            athlete=self.athlete_a, exercise="Sit-ups").first()
        self.assertIsNotNone(assessment)
        self.assertEqual(assessment.measurement, 30.0)

    def test_save_live_assessment_persists_final_situp_count(self):
        response = self.client_a.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": '{"reps": 5, "situp_phase": "bottom"}',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        assessment = Assessment.objects.get(
            athlete=self.athlete_a, exercise="Sit-ups")
        self.assertEqual(assessment.measurement, 5.0)

    def test_save_live_assessment_rejects_empty_data(self):
        response = self.client_a.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": "{}",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("error", data)

    def test_save_live_assessment_blocks_cross_trainer(self):
        response = self.client_b.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": '{"reps": 30}',
            },
        )
        self.assertEqual(response.status_code, 404)
