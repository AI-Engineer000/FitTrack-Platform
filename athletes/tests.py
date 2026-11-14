from io import StringIO
from pathlib import Path
import re
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.test.utils import override_settings

from athletes.models import Athlete


class CreateAthleteUsersCommandTests(TestCase):
    def create_athlete(self, athlete_id):
        return Athlete.objects.create(
            name=f"Athlete {athlete_id}",
            athlete_id=athlete_id,
            age=18,
            gender="Other",
            sport="Track",
        )

    def test_creates_only_missing_accounts_and_skips_linked_users(self):
        unlinked_athlete = self.create_athlete("FT-001")
        linked_user = User.objects.create_user(
            username="FT-002",
            email="FT-002@fittrack.local",
            password="ExistingPassword123!",
        )
        linked_athlete = self.create_athlete("FT-002")
        linked_athlete.user = linked_user
        linked_athlete.save(update_fields=["user"])
        output = StringIO()

        with TemporaryDirectory() as temp_dir:
            with override_settings(BASE_DIR=temp_dir):
                call_command("create_athlete_users", stdout=output)
                credentials_path = Path(temp_dir) / "athlete_credentials.txt"
                credentials = credentials_path.read_text(encoding="utf-8")

        unlinked_athlete.refresh_from_db()
        linked_athlete.refresh_from_db()
        self.assertEqual(unlinked_athlete.user.username, "FT-001")
        self.assertEqual(unlinked_athlete.user.email, "FT-001@fittrack.local")
        self.assertTrue(linked_athlete.user.check_password("ExistingPassword123!"))
        credential_rows = [
            line.split(" | ", 2) for line in credentials.splitlines()[1:]
        ]
        self.assertEqual(len(credential_rows), 1)
        name, username, password = credential_rows[0]
        self.assertEqual((name, username), ("Athlete FT-001", "FT-001"))
        self.assertRegex(password, re.compile(r"^[A-Za-z0-9]{8}$"))
        self.assertTrue(unlinked_athlete.user.check_password(password))
        self.assertEqual(linked_athlete.user_id, linked_user.id)
        self.assertEqual(User.objects.count(), 2)
        self.assertIn("Created 1 and skipped 1 athlete user(s).", output.getvalue())

        with TemporaryDirectory() as temp_dir:
            with override_settings(BASE_DIR=temp_dir):
                credentials_path = Path(temp_dir) / "athlete_credentials.txt"
                credentials_path.write_text(credentials, encoding="utf-8")
                output = StringIO()
                call_command("create_athlete_users", stdout=output)
                rerun_credentials = credentials_path.read_text(encoding="utf-8")

        self.assertEqual(rerun_credentials, credentials)
        self.assertIn("Created 0 and skipped 2 athlete user(s).", output.getvalue())

    def test_skips_existing_link_even_when_its_password_is_unusable(self):
        athlete = self.create_athlete("FT-003")
        user = User.objects.create_user(
            username="FT-003",
            email="old@example.com",
            password="ExistingPassword123!",
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        athlete.user = user
        athlete.save(update_fields=["user"])
        output = StringIO()

        with TemporaryDirectory() as temp_dir:
            with override_settings(BASE_DIR=temp_dir):
                call_command("create_athlete_users", stdout=output)
                credentials = (
                    Path(temp_dir) / "athlete_credentials.txt"
                ).read_text(encoding="utf-8").splitlines()

        athlete.refresh_from_db()
        self.assertEqual(athlete.user.email, "old@example.com")
        self.assertFalse(athlete.user.has_usable_password())
        self.assertEqual(
            credentials,
            ["Athlete Name | Username | Temporary Password"],
        )
        self.assertIn("Created 0 and skipped 1 athlete user(s).", output.getvalue())
