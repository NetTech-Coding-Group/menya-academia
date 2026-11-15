from django.contrib import admin

from .models import ActivationCode


@admin.register(ActivationCode)
class ActivationCodeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "package_name",
        "display_status",
        "attempts_made",
        "expires_at",
    )
    list_filter = ("status", "payment__provider", "payment__package")
    search_fields = ("code", "payment__email", "payment__phone_number")
    readonly_fields = (
        "code",
        "payment",
        "activated_by",
        "attempts_made",
        "activated_at",
        "expires_at",
        "created_at",
    )

    @admin.display(description="Package")
    def package_name(self, obj):
        return obj.package.name

    @admin.display(description="Status", ordering="status")
    def display_status(self, obj):
        return dict(ActivationCode.Status.choices)[obj.effective_status]

    def has_delete_permission(self, request, obj=None):
        return False
