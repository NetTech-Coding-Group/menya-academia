import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core import signing
from django.core.cache import cache
from django.core.mail import send_mail
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from allauth.account.models import EmailAddress

from apps.teachers.models import TeacherProfile

from django.contrib.auth import views as auth_views

from .forms import (
    EmailAuthenticationForm,
    ProfileForm,
    RegistrationForm,
    ResendVerificationForm,
)
from .models import User
from .templatetags.ui_translations import translate_ui

logger = logging.getLogger(__name__)


class PasswordResetView(auth_views.PasswordResetView):
    def form_valid(self, form):
        opts = {
            "use_https": getattr(settings, "SITE_SCHEME", "http") == "https",
            "token_generator": self.token_generator,
            "from_email": self.from_email,
            "email_template_name": self.email_template_name,
            "subject_template_name": self.subject_template_name,
            "request": self.request,
            "html_email_template_name": self.html_email_template_name,
            "extra_email_context": self.extra_email_context,
            "domain_override": getattr(settings, "SITE_DOMAIN", "").strip() or None,
        }
        form.save(**opts)
        return redirect(self.get_success_url())


def _build_site_url(path):
    scheme = getattr(settings, "SITE_SCHEME", "http").strip() or "http"
    domain = getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000").strip().strip("/")
    return f"{scheme}://{domain}{path}"


def _send_verification_email(request, user):
    token = signing.TimestampSigner(salt="accounts.email-verification").sign(str(user.pk))
    verify_url = _build_site_url(reverse("accounts:verify_email", args=(token,)))
    send_mail(
        translate_ui("Verify your MENYA ACADEMIA account", request.LANGUAGE_CODE),
        (
            f"{translate_ui('Hello', request.LANGUAGE_CODE)} {user.full_name}, "
            f"{translate_ui('verify your email address using this link:', request.LANGUAGE_CODE)} "
            f"{verify_url}"
        ),
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def set_language(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    language = request.POST.get("language")
    if language not in dict(settings.LANGUAGES):
        return redirect("home")

    next_url = request.POST.get("next") or request.META.get("HTTP_REFERER", "")
    if not url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("home")

    translation.activate(language)
    request.LANGUAGE_CODE = language
    if request.user.is_authenticated and getattr(request.user, "preferred_language", None) != language:
        request.user.preferred_language = language
        request.user.save(update_fields=["preferred_language"])

    response = redirect(next_url)
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME,
        language,
        max_age=settings.LANGUAGE_COOKIE_AGE,
        path=settings.LANGUAGE_COOKIE_PATH,
        domain=settings.LANGUAGE_COOKIE_DOMAIN,
        secure=settings.LANGUAGE_COOKIE_SECURE,
        httponly=settings.LANGUAGE_COOKIE_HTTPONLY,
        samesite=settings.LANGUAGE_COOKIE_SAMESITE,
    )
    return response


def register(request):
    if request.user.is_authenticated:
        return redirect("home")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"primary": True, "verified": False},
        )
        _send_verification_email(request, user)
        messages.success(
            request,
            translate_ui(
                "Account created. Use the verification link sent to your email before signing in.",
                request.LANGUAGE_CODE,
            ),
        )
        return redirect("accounts:login")
    return render(request, "accounts/register.html", {"form": form})


def verify_email(request, token):
    try:
        user_id = signing.TimestampSigner(
            salt="accounts.email-verification"
        ).unsign(token, max_age=60 * 60 * 24)
    except signing.BadSignature:
        messages.error(
            request,
            translate_ui(
                "That verification link is invalid or has expired.",
                request.LANGUAGE_CODE,
            ),
        )
        return redirect("accounts:register")

    user = get_object_or_404(User, pk=user_id)
    if not user.is_email_verified:
        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])
    EmailAddress.objects.update_or_create(
        user=user,
        email=user.email,
        defaults={"primary": True, "verified": True},
    )
    messages.success(
        request,
        translate_ui("Your email is verified. You can now sign in.", request.LANGUAGE_CODE),
    )
    return redirect("accounts:login")


def sign_in(request):
    form = EmailAuthenticationForm(
        request=request,
        data=request.POST or None,
    )
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        login(request, user)
        if request.POST.get("remember_me") == "1":
            request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            request.session.set_expiry(0)
        next_url = request.POST.get("next") or request.GET.get("next", "")
        if user.role == User.Role.TEACHER:
            try:
                teacher_profile = user.teacher_profile
            except TeacherProfile.DoesNotExist:
                return redirect("teachers:application_status")
            if not teacher_profile.is_verified_teacher:
                return redirect("teachers:application_status")
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect("teacher_workspace:workspace")
        if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            return redirect(next_url)
        if user.is_superuser or (user.is_staff and user.role == User.Role.ADMIN):
            return redirect("administrators:dashboard")
        return redirect("home")
    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next_url": request.POST.get("next") or request.GET.get("next", ""),
        },
    )


def profile(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    form = ProfileForm(
        request.POST or None,
        request.FILES or None,
        instance=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            translate_ui("Your profile has been updated.", request.LANGUAGE_CODE),
        )
        return redirect("accounts:profile")
    return render(request, "accounts/profile.html", {"form": form})


def force_password_change(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if not request.user.must_change_password:
        return redirect("home")

    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        update_session_auth_hash(request, user)
        messages.success(request, "Your password has been updated. You can now continue.")
        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url and url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return redirect(next_url)
        if user.role == User.Role.TEACHER:
            return redirect("teacher_workspace:workspace")
        if user.is_superuser or (user.is_staff and user.role == User.Role.ADMIN):
            return redirect("administrators:dashboard")
        return redirect("home")

    return render(
        request,
        "accounts/force_password_change.html",
        {"form": form, "next_url": request.POST.get("next") or request.GET.get("next", "")},
    )


def _resend_verification_rate_limited(request, email):
    window = int(getattr(settings, "RESEND_VERIFICATION_WINDOW_SECONDS", 600))
    email_limit = int(getattr(settings, "RESEND_VERIFICATION_EMAIL_LIMIT", 3))
    ip_limit = int(getattr(settings, "RESEND_VERIFICATION_IP_LIMIT", 5))
    ip = (
        request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
        or request.META.get("REMOTE_ADDR", "unknown").strip()
        or "unknown"
    )
    email_hash = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()
    ip_hash = hashlib.sha256(ip.encode("utf-8")).hexdigest()
    keys = [
        (f"accounts:resend-verification:email:{email_hash}", email_limit),
        (f"accounts:resend-verification:ip:{ip_hash}", ip_limit),
    ]

    for key, limit in keys:
        if int(cache.get(key, 0)) >= limit:
            return True

    for key, _ in keys:
        added = cache.add(key, 1, window)
        if not added:
            try:
                cache.incr(key)
            except ValueError:
                current = int(cache.get(key, 0))
                cache.set(key, current + 1, window)
    return False


def resend_verification_email(request):
    if request.user.is_authenticated:
        return redirect("home")

    form = ResendVerificationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data["email"]
        generic_message = translate_ui(
            "If an account with that email address needs verification, a new verification link has been sent.",
            request.LANGUAGE_CODE,
        )

        if _resend_verification_rate_limited(request, email):
            messages.success(request, generic_message)
            return redirect("accounts:login")

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and not user.is_email_verified:
            try:
                _send_verification_email(request, user)
            except Exception as exc:
                logger.error(
                    "Verification email delivery failed during resend request (%s).",
                    type(exc).__name__,
                )
        messages.success(request, generic_message)
        return redirect("accounts:login")

    return render(request, "accounts/resend_verification.html", {"form": form})
