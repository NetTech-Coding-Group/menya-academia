from django.contrib import admin

from .models import Exam, ExamPackage


@admin.register(ExamPackage)
class ExamPackageAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "package_type",
        "price_rwf",
        "duration_days",
        "max_exam_attempts",
        "is_active",
    )
    list_editable = ("price_rwf", "duration_days", "max_exam_attempts", "is_active")
    ordering = ("display_order", "price_rwf")


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "category",
        "status",
        "is_active",
        "question_count",
        "duration_minutes",
        "pass_mark",
        "updated_at",
    )
    list_filter = ("status", "is_active", "category")
    search_fields = ("title", "category", "teacher__full_name", "teacher__email")
    list_editable = ("status", "is_active")
    readonly_fields = ("created_at", "updated_at")
    filter_horizontal = ("selected_questions",)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "title",
                    "slug",
                    "teacher",
                    "category",
                    "description",
                    "instructions",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Exam settings",
            {
                "fields": (
                    "question_count",
                    "duration_minutes",
                    "pass_mark",
                    "selected_questions",
                )
            },
        ),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
