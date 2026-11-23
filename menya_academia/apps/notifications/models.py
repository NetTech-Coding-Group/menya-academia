from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        MESSAGE = "MESSAGE", "New message"
        SYSTEM = "SYSTEM", "System"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sent_notifications",
    )
    notification_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.MESSAGE,
        db_index=True,
    )
    title = models.CharField(max_length=180)
    message = models.CharField(max_length=512)
    url = models.CharField(max_length=500, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("recipient", "is_read", "created_at"),
                name="notif_recipient_read_created",
            ),
        ]

    def __str__(self):
        return f"Notification for {self.recipient}: {self.title}"
