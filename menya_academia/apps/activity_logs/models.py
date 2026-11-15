from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    class Status(models.TextChoices):
        SUCCESS = "SUCCESS", "Success"
        FAILURE = "FAILURE", "Failure"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    actor_name = models.CharField(max_length=150)
    actor_email = models.EmailField(blank=True)
    actor_role = models.CharField(max_length=15, blank=True)
    action = models.CharField(max_length=64, db_index=True)
    description = models.CharField(max_length=512)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.SUCCESS,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("actor_role", "created_at"),
                name="activity_actor_role_created",
            ),
            models.Index(
                fields=("status", "created_at"),
                name="activity_status_created",
            ),
        ]

    def __str__(self):
        return f"{self.actor_name}: {self.description}"
