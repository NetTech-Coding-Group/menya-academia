from django.conf import settings
from django.utils import translation


class PreferredLanguageMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language_cookie = request.COOKIES.get(settings.LANGUAGE_COOKIE_NAME)
        supported_languages = dict(settings.LANGUAGES)
        if language_cookie in supported_languages:
            request.LANGUAGE_CODE = language_cookie
            translation.activate(request.LANGUAGE_CODE)
        elif (
            not language_cookie
            and request.user.is_authenticated
            and request.user.preferred_language in supported_languages
        ):
            request.LANGUAGE_CODE = request.user.preferred_language
            translation.activate(request.LANGUAGE_CODE)
        response = self.get_response(request)
        return response


class ForcePasswordChangeMiddleware:
    """Redirect authenticated users who must change their password."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated and getattr(user, "must_change_password", False):
            allowed_prefixes = (
                "/accounts/force-password-change/",
                "/accounts/logout/",
                "/accounts/password-change/",
                "/i18n/setlang/",
                "/static/",
                "/media/",
                "/admin/logout/",
            )
            path = request.path
            if not any(path.startswith(prefix) for prefix in allowed_prefixes):
                from django.shortcuts import redirect

                return redirect("accounts:force_password_change")
        return self.get_response(request)
