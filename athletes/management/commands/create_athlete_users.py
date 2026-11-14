import os
import secrets
import string
from pathlib import Path
from tempfile import NamedTemporaryFile

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from athletes.models import Athlete


class Command(BaseCommand):
    help = "Create missing athlete accounts and write temporary credentials."

    def handle(self, *args, **options):
        credentials_path = Path(settings.BASE_DIR) / "athlete_credentials.txt"
        previous_credentials = {}

        if credentials_path.exists():
            with credentials_path.open(encoding="utf-8") as credentials_file:
                for line in credentials_file.readlines()[1:]:
                    parts = line.rstrip("\r\n").split(" | ", 2)
                    if len(parts) == 3 and parts[1] and parts[2]:
                        previous_credentials[parts[1]] = line.rstrip("\r\n")

        alphabet = string.ascii_letters + string.digits
        created_count = 0
        skipped_count = 0
        temporary_path = None

        try:
            with transaction.atomic():
                new_credentials = {}
                unchanged_usernames = set()
                athletes = Athlete.objects.select_related("user").order_by("pk")
                for athlete in athletes.iterator():
                    user = athlete.user
                    if user is None:
                        temp_password = "".join(
                            secrets.choice(alphabet) for _ in range(8)
                        )
                        user = User(
                            username=athlete.athlete_id,
                            email=f"{athlete.athlete_id}@fittrack.local",
                        )
                        user.set_password(temp_password)
                        user.save()
                        athlete.user = user
                        athlete.save(update_fields=["user"])
                        created_count += 1
                        new_credentials[user.username] = (
                            f"{athlete.name} | {user.username} | {temp_password}"
                        )
                    else:
                        skipped_count += 1
                        unchanged_usernames.add(user.username)

                retained_credentials = [
                    previous_credentials[username]
                    for username in unchanged_usernames
                    if username in previous_credentials
                ]
                with NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="",
                    dir=credentials_path.parent,
                    prefix=f"{credentials_path.name}.",
                    suffix=".tmp",
                    delete=False,
                ) as credentials_file:
                    temporary_path = Path(credentials_file.name)
                    credentials_file.write(
                        "Athlete Name | Username | Temporary Password\n"
                    )
                    for credential in retained_credentials:
                        credentials_file.write(f"{credential}\n")
                    for credential in new_credentials.values():
                        credentials_file.write(f"{credential}\n")

            os.replace(temporary_path, credentials_path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink()

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_count} and skipped {skipped_count} "
                f"athlete user(s). Temporary credentials saved to "
                f"{credentials_path}."
            )
        )
