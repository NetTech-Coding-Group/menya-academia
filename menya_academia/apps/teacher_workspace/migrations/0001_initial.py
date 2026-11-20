import uuid

import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("courses", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="AttendanceRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("date", models.DateField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PRESENT", "Present"),
                            ("ABSENT", "Absent"),
                            ("LATE", "Late"),
                            ("EXCUSED", "Excused"),
                        ],
                        max_length=10,
                    ),
                ),
                ("remarks", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to="courses.course",
                    ),
                ),
                (
                    "marked_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="attendance_marked",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="attendance_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-date", "student__full_name"),
            },
        ),
        migrations.CreateModel(
            name="StudentMark",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("assessment_name", models.CharField(max_length=120)),
                ("assessment_type", models.CharField(blank=True, max_length=60)),
                ("term", models.CharField(blank=True, max_length=60)),
                (
                    "score",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=6,
                        validators=[django.core.validators.MinValueValidator(0)],
                    ),
                ),
                (
                    "max_score",
                    models.DecimalField(
                        decimal_places=2,
                        default=100,
                        max_digits=6,
                        validators=[django.core.validators.MinValueValidator(0.01)],
                    ),
                ),
                ("remarks", models.TextField(blank=True)),
                ("assessment_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "course",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_marks",
                        to="courses.course",
                    ),
                ),
                (
                    "recorded_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="marks_recorded",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "student",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="student_marks",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("-assessment_date", "-created_at", "student__full_name"),
            },
        ),
        migrations.AddConstraint(
            model_name="attendancerecord",
            constraint=models.UniqueConstraint(
                fields=("course", "student", "date"),
                name="unique_attendance_per_student_date",
            ),
        ),
        migrations.AddIndex(
            model_name="attendancerecord",
            index=models.Index(fields=["course", "date"], name="attendance_course_date_idx"),
        ),
        migrations.AddIndex(
            model_name="studentmark",
            index=models.Index(fields=["course", "student"], name="mark_course_student_idx"),
        ),
    ]
