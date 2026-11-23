
import os

from .base import *


DEBUG = False

# Production secret key
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

if len(SECRET_KEY) < 50 or SECRET_KEY == "unsafe-development-key-change-before-deploy":
    raise RuntimeError("Set DJANGO_SECRET_KEY to a strong production secret.")


# PostgreSQL database configuration
if not DATABASE_URL.startswith(("postgres://", "postgresql://")):
    raise RuntimeError(
        "Production requires DATABASE_URL configured for PostgreSQL."
    )

DATABASES["default"]["OPTIONS"]["sslmode"] = os.environ.get(
    "DATABASE_SSLMODE", "require"
)


# Allowed hosts
if not os.environ.get("DJANGO_ALLOWED_HOSTS"):
    raise RuntimeError(
        "Set DJANGO_ALLOWED_HOSTS for the production domain."
    )


# Brevo transactional email HTTP API configuration
EMAIL_BACKEND = "apps.notifications.email_backends.BrevoEmailBackend"

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "").strip()
if not BREVO_API_KEY:
    raise RuntimeError("Set BREVO_API_KEY in production environment.")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", DEFAULT_FROM_EMAIL).strip()
DEFAULT_FROM_NAME = os.environ.get("DEFAULT_FROM_NAME", DEFAULT_FROM_NAME).strip() or "MENYA ACADEMIA"

if not DEFAULT_FROM_EMAIL:
    raise RuntimeError("Set DEFAULT_FROM_EMAIL to your verified Brevo sender address.")


# HTTPS and security settings
SECURE_SSL_REDIRECT = True

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = int(
    os.environ.get("SECURE_HSTS_SECONDS", "31536000")
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
