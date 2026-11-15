from django.apps import AppConfig
from django.db.models.signals import post_migrate


def sync_verified_email_addresses(sender, **kwargs):
    from allauth.account.models import EmailAddress

    user_model = sender.get_model("User")
    for user in user_model.objects.only("pk", "email", "is_email_verified").iterator():
        address, created = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={
                "primary": True,
                "verified": user.is_email_verified,
            },
        )
        if not created and user.is_email_verified and not address.verified:
            address.verified = True
            address.save(update_fields=("verified",))


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        post_migrate.connect(
            sync_verified_email_addresses,
            sender=self,
            dispatch_uid="accounts.sync_verified_email_addresses",
        )
