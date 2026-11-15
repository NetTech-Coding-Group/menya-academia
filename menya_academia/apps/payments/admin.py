from django.contrib import admin

from .models import PaymentTransaction


@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "full_name",
        "course",
        "provider",
        "amount_rwf",
        "status",
        "created_at",
    )
    list_filter = ("status", "provider", "created_at")
    search_fields = ("reference", "provider_reference", "email", "phone_number", "full_name")
    readonly_fields = (
        "reference",
        "provider_reference",
        "package",
        "course",
        "user",
        "full_name",
        "phone_number",
        "email",
        "amount_rwf",
        "provider",
        "status",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
