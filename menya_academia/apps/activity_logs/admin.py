from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_name", "actor_email", "action", "status")
    list_filter = ("actor_role", "status", "action", "created_at")
    search_fields = ("actor_name", "actor_email", "description")
    ordering = ("-created_at",)
    readonly_fields = (
        "actor",
        "actor_name",
        "actor_email",
        "actor_role",
        "action",
        "description",
        "status",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
