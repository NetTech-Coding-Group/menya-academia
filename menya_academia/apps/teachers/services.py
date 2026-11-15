from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.activity_logs.models import ActivityLog

from .models import TeacherProfile, TeacherSupportingDocument


def _unique_username(email):
    User = get_user_model()
    base = slugify(email.split("@", 1)[0])[:40] or "teacher"
    username = base
    suffix = 1
    while User.objects.filter(username=username).exists():
        suffix_text = str(suffix)
        username = f"{base[:50 - len(suffix_text)]}{suffix_text}"
        suffix += 1
    return username


@transaction.atomic
def create_teacher_application(*, data, documents):
    User = get_user_model()
    user = User.objects.create_user(
        email=data["email"],
        username=_unique_username(data["email"]),
        full_name=data["full_name"],
        phone_number=data["phone_number"],
        password=data["password1"],
        role=User.Role.TEACHER,
        preferred_language="en",
    )
    profile = TeacherProfile.objects.create(
        user=user,
        teaching_subject=data["teaching_subject"],
        qualifications=data["qualifications"],
        teaching_experience=data.get("teaching_experience", ""),
        institution=data.get("institution", ""),
        profile_photo=data.get("profile_photo"),
        terms_accepted_at=timezone.now(),
    )
    for uploaded_file in documents:
        TeacherSupportingDocument.objects.create(
            application=profile,
            file=uploaded_file,
            original_name=Path(uploaded_file.name).name[:255],
        )
    ActivityLog.objects.create(
        actor=user,
        actor_name=user.full_name,
        actor_email=user.email,
        actor_role=user.role,
        action="teacher.application_submitted",
        description=f"Submitted a teacher application for {profile.get_teaching_subject_display()}.",
    )
    return profile


def notify_teacher_application_received(profile):
    send_mail(
        "Teacher application received",
        (
            f"Hello {profile.user.full_name},\n\n"
            "We received your MENYA ACADEMIA teacher application. "
            "Please verify your email address and wait for an administrator to review it."
        ),
        None,
        [profile.user.email],
        fail_silently=False,
    )

    User = get_user_model()
    admin_emails = list(
        User.objects.filter(
            is_active=True,
            is_staff=True,
            role=User.Role.ADMIN,
        )
        .exclude(email="")
        .values_list("email", flat=True)
    )
    if admin_emails:
        send_mail(
            "New MENYA ACADEMIA teacher application",
            (
                f"{profile.user.full_name} ({profile.user.email}) submitted a "
                "teacher application. Review it in the admin panel."
            ),
            None,
            admin_emails,
            fail_silently=False,
        )


def notify_teacher_application_decision(profile):
    if profile.application_status == TeacherProfile.ApplicationStatus.APPROVED:
        subject = "Your MENYA ACADEMIA teacher application was approved"
        body = (
            f"Hello {profile.user.full_name},\n\n"
            "Your teacher application has been approved. You can now sign in and "
            "open your teacher workspace."
        )
    else:
        if profile.application_status == TeacherProfile.ApplicationStatus.SUSPENDED:
            subject = "Your MENYA ACADEMIA teacher account is suspended"
            body = (
                f"Hello {profile.user.full_name},\n\n"
                "Your teacher account has been suspended and its teacher permissions "
                "have been revoked. Contact the platform administrator for details."
            )
        else:
            subject = "Update about your MENYA ACADEMIA teacher application"
            body = (
                f"Hello {profile.user.full_name},\n\n"
                "Your teacher application was not approved.\n\n"
                f"Reason: {profile.rejection_reason}\n\n"
                "You can sign in to view your application status."
            )
    send_mail(subject, body, None, [profile.user.email], fail_silently=False)
