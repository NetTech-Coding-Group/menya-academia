from django.conf import settings


def social_login_options(request):
    return {
        "social_login_google_enabled": settings.SOCIAL_LOGIN_GOOGLE_ENABLED,
        "social_login_facebook_enabled": settings.SOCIAL_LOGIN_FACEBOOK_ENABLED,
    }
