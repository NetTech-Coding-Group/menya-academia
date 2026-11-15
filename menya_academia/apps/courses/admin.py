from django.contrib import admin

from .models import Course, CourseAnnouncement


class CourseAnnouncementInline(admin.TabularInline):
    model = CourseAnnouncement
    extra = 0
    readonly_fields = ("teacher", "created_at")


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "teacher",
        "education_level",
        "price_rwf",
        "is_published",
        "is_archived",
        "created_at",
    )
    list_filter = ("education_level", "is_published", "is_archived")
    search_fields = ("title", "teacher__full_name", "teacher__email")
    readonly_fields = ("slug", "created_at", "updated_at")
    inlines = (CourseAnnouncementInline,)


@admin.register(CourseAnnouncement)
class CourseAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("title", "course", "teacher", "created_at")
    search_fields = ("title", "message", "course__title", "teacher__email")
    readonly_fields = ("teacher", "created_at")
