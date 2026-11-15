from django.contrib import admin

from .models import Assignment, AssignmentSubmission, CourseSection, Lesson


class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    readonly_fields = ("created_at", "updated_at")


@admin.register(CourseSection)
class CourseSectionAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "position", "created_at")
    search_fields = ("title", "course__title")
    inlines = (LessonInline,)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("title", "section", "kind", "position", "is_archived")
    list_filter = ("kind", "is_archived")
    search_fields = ("title", "section__course__title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("title", "lesson", "max_points", "due_at")
    search_fields = ("title", "lesson__title", "lesson__section__course__title")


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ("assignment", "student", "submitted_at", "score", "graded_at")
    list_filter = ("submitted_at", "graded_at")
    search_fields = ("student__email", "student__full_name", "assignment__title")
    readonly_fields = ("assignment", "student", "answer", "submitted_at", "updated_at")
