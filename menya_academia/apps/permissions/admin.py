from django.contrib import admin

from .models import TeacherPermission


@admin.register(TeacherPermission)
class TeacherPermissionAdmin(admin.ModelAdmin):
    list_display = ("teacher", "permission_key", "granted_at")
    list_filter = ("permission_key",)
    search_fields = ("teacher__email", "teacher__full_name")
