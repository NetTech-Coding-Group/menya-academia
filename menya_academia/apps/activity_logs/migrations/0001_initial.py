import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("actor_name", models.CharField(max_length=150)),
                ("actor_email", models.EmailField(blank=True, max_length=254)),
                ("actor_role", models.CharField(blank=True, max_length=15)),
                ("action", models.CharField(db_index=True, max_length=64)),
                ("description", models.CharField(max_length=512)),
                (
                    "status",
                    models.CharField(
                        choices=[("SUCCESS", "Success"), ("FAILURE", "Failure")],
                        default="SUCCESS",
                        max_length=10,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "actor",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="activity_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
                "indexes": [
                    models.Index(
                        fields=["actor_role", "created_at"],
                        name="activity_actor_role_created",
                    ),
                    models.Index(
                        fields=["status", "created_at"],
                        name="activity_status_created",
                    ),
                ],
            },
        ),
    ]
