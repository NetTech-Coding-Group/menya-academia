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
