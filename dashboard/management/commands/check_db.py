from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    """Verify Django can connect to the configured PostgreSQL database."""

    help = "Check PostgreSQL connectivity for the Django project."

    def handle(self, *args, **options):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT version();")
                version = cursor.fetchone()[0]

            db_name = connection.settings_dict.get("NAME")

            self.stdout.write(self.style.SUCCESS("Connected to PostgreSQL successfully."))
            self.stdout.write(f"Database name: {db_name}")
            self.stdout.write(f"Server version: {version}")

        except Exception as exc:
            self.stdout.write(self.style.ERROR("Could not connect to the PostgreSQL database."))
            self.stdout.write(self.style.ERROR(str(exc)))
            raise
