import uuid

import django.db.models.deletion
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Course",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("slug", models.SlugField(blank=True, max_length=200, unique=True)),
                (
                    "education_level",
                    models.CharField(
                        choices=[
                            ("PRIMARY", "Primary"),
                            ("LOWER_SECONDARY", "Lower secondary"),
                            ("UPPER_SECONDARY", "Upper secondary"),
                            ("UNIVERSITY", "University"),
                            ("VOCATIONAL", "Vocational"),
                            ("PROFESSIONAL", "Professional development"),
                            ("OTHER", "Other"),
                        ],
                        db_index=True,
                        max_length=24,
                    ),
                ),
                ("short_description", models.CharField(max_length=300)),
                ("description", models.TextField()),
                ("price_rwf", models.PositiveIntegerField(validators=[MinValueValidator(1)])),
                ("cover_image", models.ImageField(blank=True, upload_to="course_covers/")),
                ("is_published", models.BooleanField(db_index=True, default=False)),
                ("is_archived", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="courses",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="course",
            index=models.Index(
                fields=["education_level", "is_published", "is_archived"],
                name="courses_level_published",
            ),
        ),
        migrations.AddIndex(
            model_name="course",
            index=models.Index(
                fields=["teacher", "is_archived"],
                name="courses_teacher_archived",
            ),
        ),
        migrations.CreateModel(
            name="CourseAnnouncement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=180)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="announcements",
                        to="courses.course",
                    ),
                ),
                (
                    "teacher",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="course_announcements",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-created_at",)},
        ),
    ]
