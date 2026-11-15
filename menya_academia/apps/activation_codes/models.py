import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.payments.models import PaymentTransaction


def generate_activation_code():
    return f"ACADEMIA-{secrets.token_hex(6).upper()}-{secrets.token_hex(6).upper()}"


class ActivationCode(models.Model):
    class Status(models.TextChoices):
        ISSUED = "ISSUED", "Issued"
        ACTIVE = "ACTIVE", "Active"
        EXPIRED = "EXPIRED", "Expired"
        CONSUMED = "CONSUMED", "Consumed"
        REVOKED = "REVOKED", "Revoked"

    code = models.CharField(
        max_length=40, unique=True, default=generate_activation_code, db_index=True
    )
    payment = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="activation_code",
    )
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activated_exam_codes",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.ISSUED
    )
    attempts_made = models.PositiveIntegerField(default=0)
    activated_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def package(self):
        return self.payment.package

    @property
    def effective_status(self):
        if (
            self.status == self.Status.ACTIVE
            and self.expires_at
            and self.expires_at <= timezone.now()
        ):
            return self.Status.EXPIRED
        return self.status

    def __str__(self):
        return self.code
