from allauth.socialaccount.models import SocialApp
from django.conf import settings


def google_oauth(request):
    provider_settings = settings.SOCIALACCOUNT_PROVIDERS.get('google', {})
    app_settings = provider_settings.get('APP', {})
    if app_settings.get('client_id') and app_settings.get('secret'):
        return {'google_oauth_enabled': True}
    try:
        enabled = SocialApp.objects.filter(
            provider='google', sites__id=settings.SITE_ID
        ).exists()
    except Exception:
        enabled = False
    return {'google_oauth_enabled': enabled}