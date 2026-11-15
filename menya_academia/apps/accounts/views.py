from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.core import signing
from django.core.mail import send_mail
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.utils.http import url_has_allowed_host_and_scheme
from allauth.account.models import EmailAddress

from apps.teachers.models import TeacherProfile

from .forms import EmailAuthenticationForm, ProfileForm, RegistrationForm
from .models import User
from .templatetags.ui_translations import translate_ui


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
        token = signing.TimestampSigner(salt="accounts.email-verification").sign(
            str(user.pk)
        )
        verify_url = request.build_absolute_uri(
            reverse("accounts:verify_email", args=(token,))
        )
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
