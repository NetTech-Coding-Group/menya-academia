import os
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "unsafe-development-key-change-before-deploy")
DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.contrib.sites",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "apps.accounts.apps.AccountsConfig",
    "apps.students.apps.StudentsConfig",
    "apps.teachers.apps.TeachersConfig",
    "apps.administrators.apps.AdministratorsConfig",
    "apps.permissions.apps.PermissionsConfig",
    "apps.courses.apps.CoursesConfig",
    "apps.lessons.apps.LessonsConfig",
    "apps.teacher_workspace.apps.TeacherWorkspaceConfig",
    "apps.examinations.apps.ExaminationsConfig",
    "apps.provisual.apps.ProvisualConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.activation_codes.apps.ActivationCodesConfig",
    "apps.enrollments.apps.EnrollmentsConfig",
    "apps.results.apps.ResultsConfig",
    "apps.notifications.apps.NotificationsConfig",
    "apps.messaging.apps.MessagingConfig",
    "apps.activity_logs.apps.ActivityLogsConfig",
    "apps.reports.apps.ReportsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ForcePasswordChangeMiddleware",
    "apps.accounts.middleware.PreferredLanguageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "apps.activity_logs.middleware.ActivityLogMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    
]

ROOT_URLCONF = "config.urls"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.accounts.context_processors.social_login_options",
                "apps.notifications.context_processors.messaging_notifications",
            ],
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
    raise RuntimeError(
        "Set DATABASE_URL to a PostgreSQL connection before starting Django."
    )

parsed_database = urlparse(DATABASE_URL)
database_name = unquote(parsed_database.path.lstrip("/"))
if not database_name:
    raise RuntimeError("DATABASE_URL must include a PostgreSQL database name.")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": database_name,
        "USER": unquote(parsed_database.username or ""),
        "PASSWORD": unquote(parsed_database.password or ""),
        "HOST": parsed_database.hostname or "",
        "PORT": parsed_database.port or "",
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"sslmode": os.environ.get("DATABASE_SSLMODE", "prefer")},
    }
}

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
SITE_ID = 1
SITE_DOMAIN = os.environ.get("SITE_DOMAIN", "127.0.0.1:8000").strip()
SITE_NAME = os.environ.get("SITE_NAME", "MENYA ACADEMIA").strip() or "MENYA ACADEMIA"
SITE_SCHEME = os.environ.get("SITE_SCHEME", "http").strip().lower() or "http"
if SITE_SCHEME not in {"http", "https"}:
    raise ValueError("SITE_SCHEME must be http or https.")
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
SOCIALACCOUNT_ADAPTER = "apps.accounts.adapters.MenyaSocialAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_STORE_TOKENS = False

GOOGLE_OAUTH_CLIENT_ID = (
    os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
    or os.environ.get("GOOGLE_CLIENT_ID", "")
).strip()
GOOGLE_OAUTH_CLIENT_SECRET = (
    os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
    or os.environ.get("GOOGLE_CLIENT_SECRET", "")
).strip()
FACEBOOK_OAUTH_CLIENT_ID = os.environ.get("FACEBOOK_OAUTH_CLIENT_ID", "").strip()
FACEBOOK_OAUTH_CLIENT_SECRET = os.environ.get("FACEBOOK_OAUTH_CLIENT_SECRET", "").strip()

SOCIAL_LOGIN_GOOGLE_ENABLED = bool(
    GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET
)
SOCIAL_LOGIN_FACEBOOK_ENABLED = bool(
    FACEBOOK_OAUTH_CLIENT_ID and FACEBOOK_OAUTH_CLIENT_SECRET
)
SOCIALACCOUNT_PROVIDERS = {}
if SOCIAL_LOGIN_GOOGLE_ENABLED:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"prompt": "select_account"},
        "OAUTH_PKCE_ENABLED": True,
        "VERIFIED_EMAIL": True,
        "EMAIL_AUTHENTICATION": True,
    }
if SOCIAL_LOGIN_FACEBOOK_ENABLED:
    SOCIALACCOUNT_PROVIDERS["facebook"] = {
        "APP": {
            "client_id": FACEBOOK_OAUTH_CLIENT_ID,
            "secret": FACEBOOK_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "METHOD": "oauth2",
        "SCOPE": ["email"],
        "FIELDS": ["id", "email", "name", "first_name", "last_name"],
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("fr", "Français"), ("rw", "Kinyarwanda")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Africa/Kigali"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"
# Email delivery: prefer HTTP API backends over SMTP.
# Set EMAIL_BACKEND explicitly to override. Examples:
#   apps.notifications.email_backends.ResendEmailBackend  (RESEND_API_KEY)
#   apps.notifications.email_backends.BrevoEmailBackend   (BREVO_API_KEY)
#   django.core.mail.backends.console.EmailBackend        (dev)
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@menyaacademia.com")
DEFAULT_FROM_NAME = os.environ.get("DEFAULT_FROM_NAME", "MENYA ACADEMIA")
_email_backend_default = "apps.notifications.email_backends.ResendEmailBackend"
if not os.environ.get("EMAIL_BACKEND"):
    if RESEND_API_KEY:
        _email_backend_default = "apps.notifications.email_backends.ResendEmailBackend"
    elif BREVO_API_KEY:
        _email_backend_default = "apps.notifications.email_backends.BrevoEmailBackend"
    elif DEBUG:
        _email_backend_default = "django.core.mail.backends.console.EmailBackend"
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", _email_backend_default)
# SMTP settings kept for optional compatibility when EMAIL_BACKEND is explicitly set to SMTP.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"

# SMS delivery (Pindo). Keep disabled when SMS_PROVIDER_URL is not configured.
SMS_PROVIDER_URL = os.environ.get("SMS_PROVIDER_URL", "").strip()
SMS_API_KEY = os.environ.get("SMS_API_KEY", "").strip()
SMS_SENDER_ID = os.environ.get("SMS_SENDER_ID", "MENYA").strip() or "MENYA"

PAYMENTS_ENABLED = os.environ.get("PAYMENTS_ENABLED", "false").lower() == "true"
EXAM_QUESTION_COUNT = int(os.environ.get("EXAM_QUESTION_COUNT", "30"))
EXAM_DURATION_MINUTES = int(os.environ.get("EXAM_DURATION_MINUTES", "30"))
EXAM_PASS_MARK = int(os.environ.get("EXAM_PASS_MARK", "70"))
if not 1 <= EXAM_QUESTION_COUNT <= 100:
    raise ValueError("EXAM_QUESTION_COUNT must be between 1 and 100.")
if not 1 <= EXAM_DURATION_MINUTES <= 180:
    raise ValueError("EXAM_DURATION_MINUTES must be between 1 and 180.")
if not 1 <= EXAM_PASS_MARK <= 100:
    raise ValueError("EXAM_PASS_MARK must be between 1 and 100.")

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_NAME = "menya_csrftoken"
CSRF_COOKIE_SAMESITE = "Lax"
