import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.courses.models import Course


class AttendanceRecord(models.Model):
    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        EXCUSED = "EXCUSED", "Excused"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    remarks = models.CharField(max_length=255, blank=True)
    marked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="attendance_marked",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-date", "student__full_name")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "student", "date"),
                name="unique_attendance_per_student_date",
            )
        ]
        indexes = [
            models.Index(fields=("course", "date"), name="attendance_course_date_idx"),
        ]

    def __str__(self):
        return f"{self.student} {self.date} {self.status}"


class StudentMark(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="student_marks",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_marks",
    )
    assessment_name = models.CharField(max_length=120)
    assessment_type = models.CharField(max_length=60, blank=True)
    term = models.CharField(max_length=60, blank=True)
    score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=100,
        validators=[MinValueValidator(0.01)],
    )
    remarks = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="marks_recorded",
    )
    assessment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-assessment_date", "-created_at", "student__full_name")
        indexes = [
            models.Index(fields=("course", "student"), name="mark_course_student_idx"),
        ]

    @property
    def percentage(self):
        if not self.max_score:
            return 0
        return round((self.score / self.max_score) * 100, 1)

    def __str__(self):
        return f"{self.student} - {self.assessment_name}: {self.score}/{self.max_score}"
