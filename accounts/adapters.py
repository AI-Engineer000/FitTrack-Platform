from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        if not user.username:
            email = (data.get('email') or '').strip()
            base = (data.get('first_name') or data.get('name')
                    or email.split('@')[0] or 'user').lower()
            base = ''.join(ch for ch in base if ch.isalnum()
                           or ch in ['_', '-'])
            base = base[:30] or 'user'
            username = base
            counter = 1
            User = get_user_model()
            while User.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            user.username = username

        return user
