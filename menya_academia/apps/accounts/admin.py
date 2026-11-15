from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from apps.activity_logs.models import ActivityLog
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile

from .forms import AdminUserCreationForm
from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    add_form = AdminUserCreationForm
    ordering = ("email",)
    list_display = (
        "email",
        "username",
        "full_name",
        "role",
        "is_email_verified",
        "is_active",
        "is_staff",
    )
    list_filter = ("role", "is_email_verified", "is_active", "is_staff")
    search_fields = ("email", "username", "full_name", "phone_number")
    readonly_fields = ("date_joined", "last_login")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal information", {"fields": ("username", "full_name", "phone_number", "avatar")}),
        ("Access", {"fields": ("role", "preferred_language", "is_email_verified", "is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "username",
                "full_name",
                "phone_number",
                "role",
                "preferred_language",
                "is_email_verified",
                "password1",
                "password2",
                "is_staff",
                "is_superuser",
            ),
        }),
    )

    def save_model(self, request, obj, form, change):
        previous_role = (
            User.objects.filter(pk=obj.pk).values_list("role", flat=True).first()
            if change and obj.pk
            else None
        )
        super().save_model(request, obj, form, change)
        if obj.role == User.Role.TEACHER:
            profile, created = TeacherProfile.objects.get_or_create(
                user=obj,
                defaults={
                    "teaching_subject": TeacherProfile.Subject.OTHER,
                    "qualifications": (
                        "Complete and review the teacher application before approval."
                    ),
                    "application_status": TeacherProfile.ApplicationStatus.PENDING,
                },
            )
            if created:
                ActivityLog.objects.create(
                    actor=request.user,
                    actor_name=request.user.full_name,
                    actor_email=request.user.email,
                    actor_role=request.user.role,
                    action="teacher.application_created_by_admin",
                    description=(
                        f"Created a pending teacher profile for {obj.full_name}."
                    ),
                )
        elif previous_role == User.Role.TEACHER:
            TeacherProfile.objects.filter(user=obj).update(
                application_status=TeacherProfile.ApplicationStatus.SUSPENDED
            )
            TeacherPermission.objects.filter(teacher=obj).delete()
