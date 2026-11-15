from django.contrib import admin

from .models import CourseEnrollment, LessonProgress


class LessonProgressInline(admin.TabularInline):
    model = LessonProgress
    extra = 0
    readonly_fields = ("lesson", "completed_at")
    can_delete = False


@admin.register(CourseEnrollment)
class CourseEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("student", "course", "status", "payment", "enrolled_at")
    list_filter = ("status", "enrolled_at")
    search_fields = ("student__email", "student__full_name", "course__title")
    readonly_fields = (
        "course",
        "student",
        "payment",
        "status",
        "enrolled_at",
        "completed_at",
    )
    inlines = (LessonProgressInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LessonProgress)
class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ("enrollment", "lesson", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("enrollment__student__email", "lesson__title")
    readonly_fields = ("enrollment", "lesson", "completed_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
