from django.apps import AppConfig
from django.conf import settings
from django.db.models.signals import post_migrate


def sync_site_domain(app_config, **kwargs):
    if app_config.label != "sites":
        return
    from django.contrib.sites.models import Site

    Site.objects.update_or_create(
        pk=getattr(settings, "SITE_ID", 1),
        defaults={
            "domain": getattr(settings, "SITE_DOMAIN", "127.0.0.1:8000").strip(),
            "name": getattr(settings, "SITE_NAME", "MENYA ACADEMIA").strip() or "MENYA ACADEMIA",
        },
    )


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
        post_migrate.connect(
            sync_site_domain,
            dispatch_uid="accounts.sync_site_domain",
        )
