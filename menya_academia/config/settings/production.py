import os

from .base import *


DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
if len(SECRET_KEY) < 50 or SECRET_KEY == "unsafe-development-key-change-before-deploy":
    raise RuntimeError("Set DJANGO_SECRET_KEY to a strong production secret.")

if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
    raise RuntimeError("Production requires DATABASE_URL configured for PostgreSQL.")

DATABASES["default"]["OPTIONS"]["sslmode"] = os.environ.get(
    "DATABASE_SSLMODE", "require"
)

if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise RuntimeError("Set DJANGO_ALLOWED_HOSTS for the production domain.")

EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
if not EMAIL_HOST:
    raise RuntimeError("Set EMAIL_HOST to a production SMTP service.")
if not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
    raise RuntimeError(
        "Set EMAIL_HOST_USER and EMAIL_HOST_PASSWORD to Gmail SMTP credentials."
    )
if DEFAULT_FROM_EMAIL == "your-email@gmail.com":
    raise RuntimeError("Set DEFAULT_FROM_EMAIL to your verified Gmail address.")

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True