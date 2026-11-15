import uuid

import django.db.models.deletion
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import migrations, models

import apps.lessons.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("courses", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="CourseSection",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("position", models.PositiveSmallIntegerField(default=1)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sections",
                        to="courses.course",
                    ),
                ),
            ],
            options={"ordering": ("position", "created_at")},
        ),
        migrations.AddConstraint(
            model_name="coursesection",
            constraint=models.UniqueConstraint(
                fields=("course", "position"),
                name="unique_course_section_position",
            ),
        ),
        migrations.CreateModel(
            name="Lesson",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("description", models.CharField(blank=True, max_length=300)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("VIDEO", "Video"),
                            ("PDF", "PDF material"),
                            ("TEXT", "Reading"),
                        ],
                        max_length=8,
                    ),
                ),
                ("content", models.TextField(blank=True)),
                (
                    "video_url",
                    models.URLField(
                        blank=True,
                        validators=[apps.lessons.models.validate_video_url],
                    ),
                ),
                (
                    "material",
                    models.FileField(
                        blank=True,
                        upload_to=apps.lessons.models.lesson_material_upload_path,
                        validators=[apps.lessons.models.validate_material_file],
                    ),
                ),
                ("position", models.PositiveSmallIntegerField(default=1)),
                ("is_archived", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "section",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="lessons",
                        to="lessons.coursesection",
                    ),
                ),
            ],
            options={"ordering": ("position", "created_at")},
        ),
        migrations.AddConstraint(
            model_name="lesson",
            constraint=models.UniqueConstraint(
                fields=("section", "position"),
                name="unique_section_lesson_position",
            ),
        ),
        migrations.CreateModel(
            name="Assignment",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("title", models.CharField(max_length=180)),
                ("instructions", models.TextField()),
                (
                    "max_points",
                    models.PositiveSmallIntegerField(
                        default=100,
                        validators=[MinValueValidator(1)],
                    ),
                ),
                ("due_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "lesson",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="lessons.lesson",
                    ),
                ),
            ],
            options={"ordering": ("due_at", "created_at")},
        ),
        migrations.CreateModel(
            name="AssignmentSubmission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("answer", models.TextField()),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("score", models.PositiveSmallIntegerField(blank=True, null=True)),
                ("feedback", models.TextField(blank=True)),
                ("graded_at", models.DateTimeField(blank=True, null=True)),
                (
                    "assignment",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="submissions",
                        to="lessons.assignment",
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignment_submissions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-submitted_at",)},
        ),
        migrations.AddConstraint(
            model_name="assignmentsubmission",
            constraint=models.UniqueConstraint(
                fields=("assignment", "student"),
                name="unique_student_assignment_submission",
            ),
        ),
        migrations.AddConstraint(
            model_name="assignmentsubmission",
            constraint=models.CheckConstraint(
                condition=models.Q(score__isnull=True) | models.Q(score__gte=0),
                name="submission_score_nonnegative",
            ),
        ),
    ]
