from pathlib import Path

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Q
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.activity_logs.models import ActivityLog
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.examinations.models import Exam
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile, TeacherSupportingDocument
from apps.teachers.services import notify_teacher_application_decision

from .forms import (
    ActivityLogFilterForm,
    PermissionAssignmentForm,
    TeacherAdminCreateForm,
    TeacherAdminEditForm,
    TeacherApplicationRejectionForm,
    UserEditForm,
)


User = get_user_model()
ADMIN_LOGIN_URL = "accounts:login"


def is_admin(user):
    return user.is_authenticated and user.is_active and (
        user.is_superuser or (user.is_staff and user.role == User.Role.ADMIN)
    )


admin_required = user_passes_test(is_admin, login_url=ADMIN_LOGIN_URL)


def record_activity(actor, action, description):
    ActivityLog.objects.create(
        actor=actor,
        actor_name=actor.full_name,
        actor_email=actor.email,
        actor_role=actor.role,
        action=action,
        description=description,
    )


@admin_required
def dashboard(request):
    context = {
        "total_students": User.objects.filter(role=User.Role.STUDENT).count(),
        "total_teachers": TeacherProfile.objects.filter(
            application_status=TeacherProfile.ApplicationStatus.APPROVED
        ).count(),
        "active_teachers": User.objects.filter(
            role=User.Role.TEACHER,
            is_active=True,
            teacher_profile__application_status=TeacherProfile.ApplicationStatus.APPROVED,
        ).count(),
        "total_courses": Course.objects.count(),
        "active_enrollments": CourseEnrollment.objects.filter(
            status=CourseEnrollment.Status.ACTIVE,
            payment__status="SUCCESSFUL",
            payment__course_id=F("course_id"),
            payment__user_id=F("student_id"),
        ).count(),
        "pending_teacher_applications": TeacherProfile.objects.filter(
            application_status=TeacherProfile.ApplicationStatus.PENDING
        ).count(),
        "total_exams": Exam.objects.count(),
        "recent_activities": ActivityLog.objects.select_related("actor")[:8],
    }
    return render(request, "administrators/dashboard.html", context)


@admin_required
def user_list(request):
    users = User.objects.all().order_by("-date_joined")
    search = request.GET.get("q", "").strip()
    role = request.GET.get("role", "")
    status = request.GET.get("status", "")

    if search:
        users = users.filter(
            Q(full_name__icontains=search)
            | Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(phone_number__icontains=search)
        )
    if role in User.Role.values:
        users = users.filter(role=role)
    if status == "active":
        users = users.filter(is_active=True)
    elif status == "inactive":
        users = users.filter(is_active=False)

    page = Paginator(users, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "administrators/user_list.html",
        {
            "page": page,
            "search": search,
            "selected_role": role,
            "selected_status": status,
            "role_choices": User.Role.choices,
        },
    )


@admin_required
def user_detail(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    teacher_profile = None
    assigned_classes = []
    if target.role == User.Role.TEACHER:
        teacher_profile = TeacherProfile.objects.filter(user=target).prefetch_related(
            "assigned_classes"
        ).first()
        if teacher_profile:
            assigned_classes = teacher_profile.assigned_classes.filter(is_archived=False)
    return render(
        request,
        "administrators/user_detail.html",
        {
            "target": target,
            "teacher_profile": teacher_profile,
            "assigned_classes": assigned_classes,
            "permissions": target.granted_permissions.all(),
            "activities": ActivityLog.objects.filter(actor=target)[:10],
            "protected_account": (
                target.is_staff
                or target.is_superuser
                or target.role == User.Role.ADMIN
            ),
        },
    )


def _permission_groups():
    return (
        ("Courses", ("can_create_course", "can_edit_course", "can_delete_course", "can_publish_course")),
        ("Lessons & materials", ("can_create_lesson", "can_edit_lesson", "can_delete_lesson", "can_upload_materials")),
        ("Students", ("can_view_students", "can_manage_students", "can_view_student_progress")),
        ("Exams", ("can_create_exams", "can_edit_exams", "can_delete_exams", "can_grade_exams")),
        ("Assignments", ("can_create_assignments", "can_grade_assignments", "can_create_quizzes")),
        ("Communication", ("can_send_messages", "can_send_announcements")),
        ("Attendance & marks", ("can_record_attendance", "can_enter_marks", "can_monitor_performance")),
        ("Reports", ("can_view_reports", "can_download_reports")),
    )


def _sync_teacher_permissions(teacher, selected_keys):
    selected_keys = set(selected_keys or [])
    existing_keys = set(
        TeacherPermission.objects.filter(teacher=teacher).values_list(
            "permission_key", flat=True
        )
    )
    revoked = existing_keys - selected_keys
    granted = selected_keys - existing_keys
    if revoked:
        TeacherPermission.objects.filter(
            teacher=teacher, permission_key__in=revoked
        ).delete()
    TeacherPermission.objects.bulk_create(
        [
            TeacherPermission(teacher=teacher, permission_key=key)
            for key in sorted(granted)
        ]
    )
    return granted, revoked


@admin_required
def user_edit(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.is_staff or target.is_superuser or target.role == User.Role.ADMIN:
        messages.error(request, "Staff accounts must be managed in Django admin.")
        return redirect("administrators:user_detail", user_id=target.pk)
    if target.role == User.Role.TEACHER:
        return redirect("administrators:teacher_edit", user_id=target.pk)

    form = UserEditForm(request.POST or None, instance=target)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["role"] == User.Role.TEACHER:
            form.add_error(
                "role",
                "Use 'Add teacher' or the teacher management form to create and manage teacher accounts.",
            )
            return render(
                request,
                "administrators/user_form.html",
                {"form": form, "target": target},
            )
        changed_fields = tuple(form.changed_data)
        with transaction.atomic():
            target = form.save()
            if changed_fields:
                record_activity(
                    request.user,
                    "user.updated",
                    f"Updated {target.full_name}'s account ({', '.join(changed_fields)}).",
                )
        if changed_fields:
            messages.success(request, "User information updated.")
        return redirect("administrators:user_detail", user_id=target.pk)

    return render(
        request,
        "administrators/user_form.html",
        {"form": form, "target": target},
    )


@admin_required
def teacher_create(request):
    form = TeacherAdminCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            teacher = User.objects.create_user(
                email=form.cleaned_data["email"],
                username=form.cleaned_data["username"],
                full_name=form.cleaned_data["full_name"],
                phone_number=form.cleaned_data["phone_number"],
                password=form.cleaned_data["password1"],
                role=User.Role.TEACHER,
                preferred_language=form.cleaned_data["preferred_language"],
                is_email_verified=form.cleaned_data["is_email_verified"],
                is_active=form.cleaned_data["is_active"],
                must_change_password=True,
            )
            teaching_category = form.cleaned_data["teaching_category"]
            teaching_level = form.cleaned_data.get("teaching_level") or TeacherProfile.TeachingLevel.NONE
            teaching_subject = (
                TeacherProfile.Subject.ROAD_TRAFFIC_RULES
                if teaching_category == TeacherProfile.TeachingCategory.TRAFFIC_RULES
                else TeacherProfile.Subject.OTHER
            )
            profile = TeacherProfile.objects.create(
                user=teacher,
                teaching_category=teaching_category,
                teaching_level=teaching_level,
                teaching_subject=teaching_subject,
                teacher_role_title=form.cleaned_data.get("teacher_role_title", ""),
                assigned_subjects=form.cleaned_data.get("assigned_subjects", ""),
                responsibilities=form.cleaned_data.get("responsibilities", ""),
                qualifications=form.cleaned_data.get("qualifications", "")
                or "Added by administrator.",
                teaching_experience=form.cleaned_data.get("teaching_experience", ""),
                institution=form.cleaned_data.get("institution", ""),
                terms_accepted_at=timezone.now(),
                application_status=TeacherProfile.ApplicationStatus.APPROVED,
                approved_by=request.user,
                approval_date=timezone.now(),
            )
            profile.assigned_classes.set(form.cleaned_data.get("assigned_classes") or [])
            granted, _ = _sync_teacher_permissions(
                teacher, form.cleaned_data.get("permissions") or []
            )
            record_activity(
                request.user,
                "teacher.created",
                f"Added teacher account for {teacher.full_name} ({profile.get_teaching_category_display()}, {profile.get_teaching_level_display()}) with {len(granted)} permissions and {profile.assigned_classes.count()} assigned classes.",
            )
        messages.success(
            request,
            "Teacher account created. Share the temporary password securely. The teacher will be required to change it on first login.",
        )
        return redirect("administrators:user_detail", user_id=teacher.pk)

    choices = dict(TeacherPermission.PERMISSION_KEYS)
    permission_groups = [
        {"title": title, "permissions": [(key, choices[key]) for key in keys if key in choices]}
        for title, keys in _permission_groups()
    ]
    return render(
        request,
        "administrators/teacher_form.html",
        {
            "form": form,
            "page_title": "Add teacher",
            "page_intro": "Create a teacher account, assign responsibilities, classes, and permissions.",
            "submit_label": "Create teacher account",
            "permission_groups": permission_groups,
        },
    )


@admin_required
def teacher_edit(request, user_id):
    teacher = get_object_or_404(User, pk=user_id, role=User.Role.TEACHER)
    if teacher.is_staff or teacher.is_superuser:
        messages.error(request, "Staff accounts must be managed in Django admin.")
        return redirect("administrators:user_detail", user_id=teacher.pk)
    profile, _ = TeacherProfile.objects.get_or_create(
        user=teacher,
        defaults={
            "teaching_subject": TeacherProfile.Subject.OTHER,
            "qualifications": "Added or recovered by administrator.",
            "application_status": TeacherProfile.ApplicationStatus.APPROVED,
            "approved_by": request.user,
            "approval_date": timezone.now(),
            "terms_accepted_at": timezone.now(),
        },
    )
    initial = {
        "full_name": teacher.full_name,
        "username": teacher.username,
        "email": teacher.email,
        "phone_number": teacher.phone_number,
        "preferred_language": teacher.preferred_language,
        "is_email_verified": teacher.is_email_verified,
        "is_active": teacher.is_active,
        "teaching_category": profile.teaching_category,
        "teaching_level": profile.teaching_level,
        "teacher_role_title": profile.teacher_role_title,
        "assigned_subjects": profile.assigned_subjects,
        "responsibilities": profile.responsibilities,
        "assigned_classes": profile.assigned_classes.all(),
        "qualifications": profile.qualifications,
        "teaching_experience": profile.teaching_experience,
        "institution": profile.institution,
        "permissions": list(
            TeacherPermission.objects.filter(teacher=teacher).values_list(
                "permission_key", flat=True
            )
        ),
    }
    form = TeacherAdminEditForm(
        request.POST or None,
        teacher=teacher,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            teacher.full_name = form.cleaned_data["full_name"]
            teacher.username = form.cleaned_data["username"]
            teacher.email = form.cleaned_data["email"].strip().lower()
            teacher.phone_number = form.cleaned_data["phone_number"]
            teacher.preferred_language = form.cleaned_data["preferred_language"]
            teacher.is_email_verified = form.cleaned_data["is_email_verified"]
            teacher.is_active = form.cleaned_data["is_active"]
            teacher.save()
            teaching_category = form.cleaned_data["teaching_category"]
            teaching_level = form.cleaned_data.get("teaching_level") or TeacherProfile.TeachingLevel.NONE
            profile.teaching_category = teaching_category
            profile.teaching_level = teaching_level
            profile.teaching_subject = (
                TeacherProfile.Subject.ROAD_TRAFFIC_RULES
                if teaching_category == TeacherProfile.TeachingCategory.TRAFFIC_RULES
                else TeacherProfile.Subject.OTHER
            )
            profile.teacher_role_title = form.cleaned_data.get("teacher_role_title", "")
            profile.assigned_subjects = form.cleaned_data.get("assigned_subjects", "")
            profile.responsibilities = form.cleaned_data.get("responsibilities", "")
            profile.qualifications = form.cleaned_data.get("qualifications", "") or profile.qualifications
            profile.teaching_experience = form.cleaned_data.get("teaching_experience", "")
            profile.institution = form.cleaned_data.get("institution", "")
            if teacher.is_active and profile.application_status == TeacherProfile.ApplicationStatus.SUSPENDED:
                profile.application_status = TeacherProfile.ApplicationStatus.APPROVED
                profile.approved_by = request.user
                profile.approval_date = timezone.now()
                profile.rejection_reason = ""
            elif not teacher.is_active and profile.application_status == TeacherProfile.ApplicationStatus.APPROVED:
                profile.application_status = TeacherProfile.ApplicationStatus.SUSPENDED
            profile.save()
            profile.assigned_classes.set(form.cleaned_data.get("assigned_classes") or [])
            granted, revoked = _sync_teacher_permissions(
                teacher, form.cleaned_data.get("permissions") or []
            )
            changes = []
            if granted:
                changes.append(f"granted {len(granted)} permissions")
            if revoked:
                changes.append(f"revoked {len(revoked)} permissions")
            record_activity(
                request.user,
                "teacher.updated",
                f"Updated teacher {teacher.full_name}: {profile.assigned_classes.count()} assigned classes"
                + (f", {', '.join(changes)}" if changes else "")
                + ".",
            )
        messages.success(request, "Teacher information, responsibilities, and access updated.")
        return redirect("administrators:user_detail", user_id=teacher.pk)

    choices = dict(TeacherPermission.PERMISSION_KEYS)
    permission_groups = [
        {"title": title, "permissions": [(key, choices[key]) for key in keys if key in choices]}
        for title, keys in _permission_groups()
    ]
    return render(
        request,
        "administrators/teacher_form.html",
        {
            "form": form,
            "teacher": teacher,
            "profile": profile,
            "page_title": "Edit teacher",
            "page_intro": "Update teacher information, responsibilities, assigned classes, and permissions.",
            "submit_label": "Save teacher changes",
            "permission_groups": permission_groups,
        },
    )


@admin_required
def teacher_application_list(request):
    applications = TeacherProfile.objects.select_related("user", "approved_by")
    status = request.GET.get("status", TeacherProfile.ApplicationStatus.PENDING)
    if status in TeacherProfile.ApplicationStatus.values:
        applications = applications.filter(application_status=status)
    else:
        status = ""
    search = request.GET.get("q", "").strip()
    if search:
        applications = applications.filter(
            Q(user__full_name__icontains=search)
            | Q(user__email__icontains=search)
            | Q(institution__icontains=search)
            | Q(teaching_subject__icontains=search)
        )
    page = Paginator(applications, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "administrators/teacher_applications.html",
        {
            "page": page,
            "search": search,
            "selected_status": status,
            "status_choices": TeacherProfile.ApplicationStatus.choices,
        },
    )


@admin_required
def teacher_application_detail(request, application_id):
    application = get_object_or_404(
        TeacherProfile.objects.select_related("user", "approved_by").prefetch_related(
            "supporting_documents"
        ),
        pk=application_id,
    )
    return render(
        request,
        "administrators/teacher_application_detail.html",
        {
            "application": application,
            "rejection_form": TeacherApplicationRejectionForm(),
        },
    )


@admin_required
@require_POST
def teacher_application_approve(request, application_id):
    with transaction.atomic():
        application = get_object_or_404(
            TeacherProfile.objects.select_for_update().select_related("user"),
            pk=application_id,
        )
        if application.application_status != TeacherProfile.ApplicationStatus.PENDING:
            messages.error(request, "Only pending applications can be approved.")
            return redirect(
                "administrators:teacher_application_detail",
                application_id=application.pk,
            )
        if not application.user.is_email_verified:
            messages.error(
                request,
                "The applicant must verify their email before approval.",
            )
            return redirect(
                "administrators:teacher_application_detail",
                application_id=application.pk,
            )
        if not application.user.is_active:
            messages.error(request, "Reactivate the applicant account before approval.")
            return redirect(
                "administrators:teacher_application_detail",
                application_id=application.pk,
            )
        application.application_status = TeacherProfile.ApplicationStatus.APPROVED
        application.approved_by = request.user
        application.approval_date = timezone.now()
        application.rejection_reason = ""
        application.user.role = User.Role.TEACHER
        application.user.save(update_fields=("role",))
        revoked_count, _ = TeacherPermission.objects.filter(
            teacher=application.user
        ).delete()
        if revoked_count:
            record_activity(
                request.user,
                "permissions.revoked",
                (
                    f"Cleared existing teacher permissions for "
                    f"{application.user.full_name} during application approval."
                ),
            )
        application.save(
            update_fields=(
                "application_status",
                "approved_by",
                "approval_date",
                "rejection_reason",
                "updated_at",
            )
        )
        record_activity(
            request.user,
            "teacher.application_approved",
            f"Approved teacher application for {application.user.full_name}.",
        )
    notify_teacher_application_decision(application)
    messages.success(request, "Teacher application approved.")
    return redirect(
        "administrators:teacher_application_detail",
        application_id=application.pk,
    )


@admin_required
@require_POST
def teacher_application_reject(request, application_id):
    application = get_object_or_404(
        TeacherProfile.objects.select_related("user"),
        pk=application_id,
    )
    form = TeacherApplicationRejectionForm(request.POST)
    if application.application_status != TeacherProfile.ApplicationStatus.PENDING:
        messages.error(request, "Only pending applications can be rejected.")
    elif form.is_valid():
        with transaction.atomic():
            application.application_status = TeacherProfile.ApplicationStatus.REJECTED
            application.rejection_reason = form.cleaned_data["rejection_reason"]
            application.approved_by = None
            application.approval_date = None
            application.save(
                update_fields=(
                    "application_status",
                    "rejection_reason",
                    "approved_by",
                    "approval_date",
                    "updated_at",
                )
            )
            TeacherPermission.objects.filter(teacher=application.user).delete()
            record_activity(
                request.user,
                "teacher.application_rejected",
                f"Rejected teacher application for {application.user.full_name}.",
            )
        notify_teacher_application_decision(application)
        messages.success(request, "Teacher application rejected and applicant notified.")
    else:
        return render(
            request,
            "administrators/teacher_application_detail.html",
            {
                "application": application,
                "rejection_form": form,
            },
        )
    return redirect(
        "administrators:teacher_application_detail",
        application_id=application.pk,
    )


@admin_required
@require_POST
def teacher_application_suspend(request, application_id):
    with transaction.atomic():
        application = get_object_or_404(
            TeacherProfile.objects.select_for_update().select_related("user"),
            pk=application_id,
        )
        if application.application_status != TeacherProfile.ApplicationStatus.APPROVED:
            messages.error(request, "Only approved teachers can be suspended.")
            return redirect(
                "administrators:teacher_application_detail",
                application_id=application.pk,
            )
        application.application_status = TeacherProfile.ApplicationStatus.SUSPENDED
        application.save(update_fields=("application_status", "updated_at"))
        TeacherPermission.objects.filter(teacher=application.user).delete()
        record_activity(
            request.user,
            "teacher.suspended",
            f"Suspended teacher account for {application.user.full_name}.",
        )
    notify_teacher_application_decision(application)
    messages.success(request, "Teacher account suspended and permissions revoked.")
    return redirect(
        "administrators:teacher_application_detail",
        application_id=application.pk,
    )


@admin_required
@require_GET
def teacher_application_document(request, document_id):
    document = get_object_or_404(
        TeacherSupportingDocument.objects.select_related("application__user"),
        pk=document_id,
    )
    response = FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.original_name,
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@admin_required
@require_GET
def teacher_application_photo(request, application_id):
    application = get_object_or_404(
        TeacherProfile.objects.select_related("user"),
        pk=application_id,
    )
    if not application.profile_photo:
        raise PermissionDenied("No profile photo was uploaded.")
    response = FileResponse(
        application.profile_photo.open("rb"),
        as_attachment=True,
        filename=f"teacher-{application.pk}-profile{Path(application.profile_photo.name).suffix}",
        content_type="application/octet-stream",
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@admin_required
@require_POST
def user_status(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if target.is_staff or target.is_superuser or target.role == User.Role.ADMIN:
        messages.error(request, "Staff accounts cannot be activated or deactivated here.")
        return redirect("administrators:user_detail", user_id=target.pk)

    with transaction.atomic():
        target.is_active = not target.is_active
        target.save(update_fields=("is_active",))
        state = "activated" if target.is_active else "deactivated"
        record_activity(
            request.user,
            f"user.{state}",
            f"{state.title()} {target.full_name}.",
        )
    messages.success(request, f"Account {state}.")
    return redirect("administrators:user_detail", user_id=target.pk)


@admin_required
def user_delete(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if (
        target.is_staff
        or target.is_superuser
        or target.role == User.Role.ADMIN
        or target.pk == request.user.pk
    ):
        messages.error(request, "This account cannot be deleted from the admin panel.")
        return redirect("administrators:user_detail", user_id=target.pk)
    if request.method == "POST":
        if request.POST.get("confirm") != "yes":
            return HttpResponseBadRequest("Confirm the account deletion to continue.")
        target_name = target.full_name
        target_email = target.email
        with transaction.atomic():
            record_activity(
                request.user,
                "user.deleted",
                f"Deleted {target_name} ({target_email}).",
            )
            target.delete()
        messages.success(request, "User account deleted.")
        return redirect("administrators:user_list")
    return render(
        request,
        "administrators/user_confirm_delete.html",
        {"target": target},
    )


@admin_required
@require_POST
def user_password_reset(request, user_id):
    target = get_object_or_404(User, pk=user_id)
    if not target.is_active or not target.has_usable_password():
        messages.error(
            request,
            "A password reset email cannot be sent for this inactive or passwordless account.",
        )
        return redirect("administrators:user_detail", user_id=target.pk)

    form = PasswordResetForm({"email": target.email})
    if not form.is_valid():
        messages.error(request, "The password reset request could not be validated.")
        return redirect("administrators:user_detail", user_id=target.pk)
    form.save(
        request=request,
        use_https=request.is_secure(),
        from_email=settings.DEFAULT_FROM_EMAIL,
        email_template_name="accounts/password_reset_email.html",
        subject_template_name="accounts/password_reset_subject.txt",
    )
    record_activity(
        request.user,
        "user.password_reset",
        f"Initiated a password reset for {target.full_name}.",
    )
    messages.success(request, "A password reset email has been sent to the user.")
    return redirect("administrators:user_detail", user_id=target.pk)


@admin_required
def teacher_permissions(request):
    form = PermissionAssignmentForm(request.POST or None)
    selected_teacher = None

    if request.method == "POST":
        if form.is_valid():
            selected_teacher = form.cleaned_data["teacher"]
            selected_keys = set(form.cleaned_data["permissions"])
            with transaction.atomic():
                granted, revoked = _sync_teacher_permissions(selected_teacher, selected_keys)
                if granted or revoked:
                    changes = []
                    if granted:
                        changes.append(f"granted {len(granted)}")
                    if revoked:
                        changes.append(f"revoked {len(revoked)}")
                    record_activity(
                        request.user,
                        "permissions.updated",
                        (
                            f"Updated {selected_teacher.full_name}'s teacher "
                            f"permissions: {', '.join(changes)}."
                        ),
                    )
            messages.success(request, "Teacher permissions saved.")
            return redirect(
                f"{reverse('administrators:teacher_permissions')}?teacher={selected_teacher.pk}"
            )
    else:
        teacher_id = request.GET.get("teacher")
        if teacher_id:
            selected_teacher = form.fields["teacher"].queryset.filter(
                pk=teacher_id
            ).first()
            if selected_teacher:
                form.initial["teacher"] = selected_teacher
                form.initial["permissions"] = list(
                    TeacherPermission.objects.filter(teacher=selected_teacher)
                    .values_list("permission_key", flat=True)
                )

    choices = dict(TeacherPermission.PERMISSION_KEYS)
    groups = [
        {
            "title": title,
            "permissions": [
                (key, choices[key]) for key in keys if key in choices
            ],
        }
        for title, keys in _permission_groups()
    ]
    selected_permission_count = len(form["permissions"].value() or [])
    return render(
        request,
        "administrators/teacher_permissions.html",
        {
            "form": form,
            "selected_teacher": selected_teacher,
            "permission_groups": groups,
            "selected_permission_count": selected_permission_count,
        },
    )


@admin_required
def activity_logs(request):
    form = ActivityLogFilterForm(request.GET or None)
    logs = ActivityLog.objects.select_related("actor")
    actions = ActivityLog.objects.order_by().values_list("action", flat=True).distinct()
    form.fields["action"].choices = (
        ("", "All activity"),
        *((action, action.replace(".", " ").replace("_", " ").title()) for action in actions),
    )
    if form.is_valid():
        search = form.cleaned_data["search"]
        role = form.cleaned_data["role"]
        action = form.cleaned_data["action"]
        date_from = form.cleaned_data["date_from"]
        date_to = form.cleaned_data["date_to"]
        if search:
            logs = logs.filter(
                Q(actor_name__icontains=search)
                | Q(actor_email__icontains=search)
                | Q(action__icontains=search)
                | Q(description__icontains=search)
            )
        if role:
            logs = logs.filter(actor_role=role)
        if action:
            logs = logs.filter(action=action)
        if date_from:
            logs = logs.filter(created_at__date__gte=date_from)
        if date_to:
            logs = logs.filter(created_at__date__lte=date_to)
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    return render(
        request,
        "administrators/activity_logs.html",
        {"form": form, "page": page},
    )
