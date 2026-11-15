from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .forms import TeacherRegistrationForm
from .models import TeacherProfile
from .services import notify_teacher_application_received


def register_teacher(request):
    if request.user.is_authenticated:
        return redirect("teachers:application_status")
    form = TeacherRegistrationForm(
        request.POST or None,
        files=request.FILES if request.method == "POST" else None,
    )
    if request.method == "POST" and form.is_valid():
        profile = form.save()
        # Send the existing signed email-verification message to the new account.
        from django.conf import settings
        from django.core import signing
        from django.core.mail import send_mail
        from django.urls import reverse

        from apps.accounts.templatetags.ui_translations import translate_ui
        from allauth.account.models import EmailAddress

        EmailAddress.objects.update_or_create(
            user=profile.user,
            email=profile.user.email,
            defaults={"primary": True, "verified": False},
        )
        token = signing.TimestampSigner(salt="accounts.email-verification").sign(
            str(profile.user.pk)
        )
        verify_url = request.build_absolute_uri(
            reverse("accounts:verify_email", args=(token,))
        )
        send_mail(
            translate_ui("Verify your MENYA ACADEMIA account", request.LANGUAGE_CODE),
            (
                f"{translate_ui('Hello', request.LANGUAGE_CODE)} {profile.user.full_name}, "
                f"{translate_ui('verify your email address using this link:', request.LANGUAGE_CODE)} "
                f"{verify_url}"
            ),
            settings.DEFAULT_FROM_EMAIL,
            [profile.user.email],
            fail_silently=False,
        )
        notify_teacher_application_received(profile)
        messages.success(
            request,
            "Your teacher application was submitted. Verify your email, then sign in to check its status.",
        )
        return redirect("accounts:login")
    return render(request, "teachers/register.html", {"form": form})


@login_required(login_url="accounts:login")
def application_status(request):
    if not request.user.is_active:
        raise PermissionDenied("This account is inactive.")
    try:
        profile = request.user.teacher_profile
    except TeacherProfile.DoesNotExist:
        return redirect("home")
    if request.user.role != request.user.Role.TEACHER:
        return redirect("home")
    return render(
        request,
        "teachers/application_status.html",
        {"profile": profile},
    )
