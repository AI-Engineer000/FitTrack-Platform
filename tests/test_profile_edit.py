from io import BytesIO
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import Profile


class ProfileEditTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="coach",
            password="OriginalPassword123!",
            first_name="Taylor",
            last_name="Coach",
            email="coach@example.com",
        )
        self.client.force_login(self.user)
        self.profile = Profile.objects.get(user=self.user)
        self.media_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.media_dir.cleanup)
        self.media_settings = override_settings(MEDIA_ROOT=self.media_dir.name)
        self.media_settings.enable()
        self.addCleanup(self.media_settings.disable)

    def test_profile_page_displays_profile_cards_and_password_action(self):
        response = self.client.get(reverse("accounts:profile_edit"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Information")
        self.assertContains(response, "Professional Details")
        self.assertContains(response, "Account &amp; Security")
        self.assertContains(response, reverse("accounts:password_change"))

    def test_profile_post_updates_user_and_profile_fields(self):
        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": "Jordan",
                "last_name": "Trainer",
                "email": "jordan@example.com",
                "phone": "+1 555 0100",
                "organization": "FitTrack Academy",
                "specialization": "Athletics",
                "years_experience": "8",
                "bio": "Helping athletes build speed and strength.",
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_edit"))
        self.user.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(
            (self.user.first_name, self.user.last_name, self.user.email),
            ("Jordan", "Trainer", "coach@example.com"),
        )
        self.assertEqual(self.profile.phone, "+1 555 0100")
        self.assertEqual(self.profile.organization, "FitTrack Academy")
        self.assertEqual(self.profile.specialization, "Athletics")
        self.assertEqual(self.profile.years_experience, 8)
        self.assertEqual(
            self.profile.bio,
            "Helping athletes build speed and strength.",
        )

    def test_invalid_experience_keeps_profile_values_unchanged(self):
        self.profile.specialization = "Badminton"
        self.profile.save()

        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": "Jordan",
                "last_name": "Trainer",
                "email": self.user.email,
                "years_experience": "-1",
                "specialization": "Athletics",
                "phone": "",
                "organization": "",
                "bio": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.specialization, "Badminton")

    def test_standard_password_change_view_is_available(self):
        response = self.client.get(reverse("accounts:password_change"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "old_password")
        self.assertContains(response, "new_password1")
        self.assertContains(response, "data-password-toggle")

    def test_allauth_password_change_form_has_visibility_controls(self):
        response = self.client.get(reverse("account_change_password"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "password-visibility-toggle")
        self.assertContains(response, "Show password")

        updated_response = self.client.post(
            reverse("account_change_password"),
            {
                "oldpassword": "OriginalPassword123!",
                "password1": "NewPassword789!",
                "password2": "NewPassword789!",
            },
        )

        self.assertEqual(updated_response.status_code, 302)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewPassword789!"))

    def test_profile_picture_upload_saves_and_displays_image(self):
        image_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_bytes, format="PNG")
        upload = SimpleUploadedFile(
            "trainer.png",
            image_bytes.getvalue(),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "phone": "",
                "organization": "",
                "specialization": "",
                "years_experience": "0",
                "bio": "",
                "profile_picture": upload,
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_edit"))
        self.profile.refresh_from_db()
        self.assertTrue(self.profile.profile_picture.name.startswith("profile_pics/"))
        self.assertTrue(self.profile.profile_picture.storage.exists(
            self.profile.profile_picture.name
        ))
        page = self.client.get(reverse("accounts:profile_edit"))
        self.assertContains(page, self.profile.profile_picture.url)

    def test_invalid_profile_picture_does_not_replace_current_image(self):
        image_bytes = BytesIO()
        Image.new("RGB", (2, 2), color="green").save(image_bytes, format="PNG")
        self.profile.profile_picture.save(
            "existing.png",
            SimpleUploadedFile("existing.png", image_bytes.getvalue()),
        )
        original_name = self.profile.profile_picture.name

        response = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "first_name": self.user.first_name,
                "last_name": self.user.last_name,
                "email": self.user.email,
                "phone": "",
                "organization": "",
                "specialization": "",
                "years_experience": "0",
                "bio": "",
                "profile_picture": SimpleUploadedFile(
                    "not-an-image.txt",
                    b"not an image",
                    content_type="text/plain",
                ),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.profile_picture.name, original_name)
        self.assertContains(response, "Upload Photo")
