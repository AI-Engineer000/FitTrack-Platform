from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
import csv
from io import StringIO

from athletes.models import Athlete
from assessments.models import Assessment
from assessments.scoring import calculate_exercise_score
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

    def test_dashboard_progress_counts_distinct_recorded_valid_exercises(self):
        Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Sit-ups",
            measurement=30,
            measurement_unit="reps",
            measurement_status="valid",
            result="Benchmark unavailable",
        )
        Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Sit & Reach",
            measurement=24,
            measurement_unit="cm",
            measurement_status="uncalibrated",
            result="Benchmark unavailable",
        )
        Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Broad Jump",
            measurement=180,
            measurement_unit="cm",
            measurement_status="invalid",
            result="Invalid",
        )

        overview = self.client_a.get(reverse("dashboard:trainer_dashboard"))
        detail = self.client_a.get(
            reverse(
                "dashboard:athlete_detail",
                kwargs={"athlete_id": self.athlete_a.id},
            )
        )
        summary = overview.context["athlete_summary"][0]
        rows = {
            row["name"]: row for row in detail.context["exercise_rows"]
        }

        self.assertEqual(summary["completed"], 3)
        self.assertEqual(summary["assessment_count"], 4)
        self.assertEqual(detail.context["completed_count"], 3)
        self.assertEqual(detail.context["assessment_count"], 4)
        self.assertTrue(rows["Vertical Jump"]["completed"])
        self.assertTrue(rows["Sit-ups"]["completed"])
        self.assertTrue(rows["Sit & Reach"]["completed"])
        self.assertFalse(rows["Broad Jump"]["completed"])
        self.assertContains(detail, "Latest attempt not counted (Invalid)")
        self.assertContains(detail, "42.0")
        self.assertContains(detail, "Historical score unverified:")
        self.assertContains(detail, "81/100")
        self.assertNotContains(detail, 'class="mini-ring"')
        self.assertNotContains(detail, "Composite Score")
        self.assertNotContains(detail, "Validated rating")
        self.assertNotContains(detail, "Benchmark source")
        self.assertNotContains(overview, "Composite score")
        self.assertContains(overview, "Assessment records")

    def test_single_provisional_score_renders_without_chart_division_error(self):
        Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Sit-ups",
            measurement=30,
            measurement_unit="reps",
            measurement_status="valid",
            score=60,
            result="Average (Provisional)",
            benchmark_status="available",
            benchmark_rating="Average",
            benchmark_source="General Fitness Reference",
            scoring_method_version="general-reference-provisional-v1",
            details={
                "reference_rating": {
                    "disclaimer": (
                        "General reference-based rating. "
                        "Not a medical diagnosis."
                    ),
                },
            },
        )

        response = self.client_a.get(
            reverse(
                "dashboard:athlete_detail",
                kwargs={"athlete_id": self.athlete_a.id},
            )
        )

        self.assertEqual(response.status_code, 200)
        chart = response.context["exercise_charts"][0]
        self.assertEqual(chart["count"], 1)
        self.assertEqual(chart["points"][0]["x"], 250.0)
        self.assertContains(response, "Average · Reference-Based Rating")
        self.assertContains(response, "General Fitness Reference")
        self.assertContains(response, "Not a medical diagnosis")
        self.assertContains(
            response,
            "Requires clinical validation for diagnostic use",
        )

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
        self.assertEqual(response_a.context["top_athletes"], [])
        self.assertEqual(response_b.context["top_athletes"], [])
        self.assertIsNone(response_a.context["overall_avg"])

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
        self.assertEqual(assessment.measurement_unit, "reps")
        self.assertEqual(assessment.score, 60)
        self.assertEqual(assessment.benchmark_rating, "Average")
        self.assertEqual(assessment.benchmark_source, "General Fitness Reference")
        self.assertEqual(assessment.benchmark_status, "available")
        self.assertEqual(
            assessment.scoring_method_version,
            "general-reference-provisional-v1",
        )
        self.assertIn(
            "Not a medical diagnosis",
            assessment.details["reference_rating"]["disclaimer"],
        )

    def test_reference_score_requires_supported_gender_and_matching_unit(self):
        matching = calculate_exercise_score("sit_ups", 30, "Male", "reps")
        unsupported_gender = calculate_exercise_score(
            "sit_ups", 30, "Other", "reps")
        mismatched_unit = calculate_exercise_score(
            "sit_ups", 30, "Male", "cm")

        self.assertEqual(
            (matching["score"], matching["rating"]),
            (60, "Average"),
        )
        self.assertTrue(matching["is_provisional"])
        self.assertIn("not a medical diagnosis", matching["disclaimer"])
        self.assertIsNone(unsupported_gender["score"])
        self.assertEqual(unsupported_gender["rating"], "Unavailable")
        self.assertTrue(unsupported_gender["is_provisional"])
        self.assertIsNone(mismatched_unit["score"])
        self.assertEqual(mismatched_unit["rating"], "Unavailable")
        unavailable = calculate_exercise_score(
            "unknown_exercise", 30, "Male", "reps")
        self.assertIsNone(unavailable["score"])
        self.assertEqual(unavailable["rating"], "Unavailable")
        self.assertTrue(unavailable["is_provisional"])

    def test_save_live_assessment_persists_final_situp_count(self):
        response = self.client_a.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": '{"reps": 5, "completed_cycles": 4, "situp_phase": "top"}',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json().get("success"))
        assessment = Assessment.objects.get(
            athlete=self.athlete_a, exercise="Sit-ups")
        self.assertEqual(assessment.measurement, 5.0)
        self.assertEqual(assessment.details["completed_cycles"], 4)
        self.assertEqual(
            response.json()["assessment"]["measurement"],
            assessment.measurement,
        )
        self.assertEqual(response.json()["assessment"]["score"], 15)

    def test_save_live_assessment_rejects_empty_data(self):
        response = self.client_a.post(
            reverse("dashboard:save_live_assessment"),
            {
                "athlete_id": self.athlete_a.athlete_id,
                "exercise": "sit-ups",
                "state": "{}",
            },
        )
        self.assertEqual(response.status_code, 422)
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

    def test_body_measurements_are_saved_without_fitness_scores(self):
        response = self.client_a.post(
            reverse(
                "dashboard:add_body_measurements",
                kwargs={"athlete_id": self.athlete_a.id},
            ),
            {"height": "175", "weight": "70"},
        )

        self.assertEqual(response.status_code, 302)
        height = Assessment.objects.get(
            athlete=self.athlete_a, exercise="Height")
        weight = Assessment.objects.get(
            athlete=self.athlete_a, exercise="Weight")
        self.assertEqual((height.measurement, height.measurement_unit), (175, "cm"))
        self.assertEqual((weight.measurement, weight.measurement_unit), (70, "kg"))
        self.assertIsNone(height.score)
        self.assertIsNone(weight.score)
        self.assertEqual(height.result, "Measurement only")
        self.assertEqual(weight.result, "Measurement only")

    def test_history_detail_and_csv_display_saved_unavailable_score_consistently(self):
        Assessment.objects.create(
            athlete=self.athlete_a,
            exercise="Sit-ups",
            measurement=3,
            measurement_unit="reps",
            measurement_status="valid",
            score=None,
            result="Benchmark unavailable",
            benchmark_status="unavailable",
        )

        history = self.client_a.get(reverse("dashboard:history"))
        detail = self.client_a.get(
            reverse(
                "dashboard:athlete_detail",
                kwargs={"athlete_id": self.athlete_a.id},
            )
        )
        export = self.client_a.get(reverse("dashboard:export_csv"))

        self.assertEqual(history.status_code, 200)
        self.assertContains(history, "3.0 reps")
        self.assertContains(history, "Benchmark unavailable")
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, "3.0 reps")
        self.assertContains(detail, "Assessment records")
        self.assertContains(detail, "Exercises assessed")
        self.assertNotContains(detail, "Composite Score")
        rows = list(csv.reader(StringIO(export.content.decode("utf-8-sig"))))
        self.assertIn("Unit", rows[0])
        self.assertIn("Benchmark Status", rows[0])
        self.assertEqual(rows[1][4:8], ["3.0", "reps", "valid", ""])
