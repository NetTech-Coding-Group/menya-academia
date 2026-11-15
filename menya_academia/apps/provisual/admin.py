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
    list_display = ("title", "question_count", "duration_minutes", "pass_mark", "is_active")
    list_editable = ("question_count", "duration_minutes", "pass_mark", "is_active")
