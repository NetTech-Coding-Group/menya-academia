import uuid

from django.conf import settings
from django.db import models

from apps.courses.models import Course
from apps.lessons.models import Lesson
from apps.payments.models import PaymentTransaction


class CourseEnrollment(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        COMPLETED = "COMPLETED", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="enrollments",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="course_enrollments",
    )
    payment = models.OneToOneField(
        PaymentTransaction,
        on_delete=models.PROTECT,
        related_name="course_enrollment",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-enrolled_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("course", "student"),
                name="unique_course_student_enrollment",
            )
        ]
        indexes = [
            models.Index(
                fields=("student", "status"),
                name="enrollment_student_status",
            )
        ]

    @property
    def is_paid(self):
        return (
            self.payment.status == PaymentTransaction.Status.SUCCESSFUL
            and self.payment.course_id == self.course_id
            and self.payment.user_id == self.student_id
            and self.payment.amount_rwf > 0
        )

    def __str__(self):
        return f"{self.student} — {self.course}"


class LessonProgress(models.Model):
    enrollment = models.ForeignKey(
        CourseEnrollment,
        on_delete=models.CASCADE,
        related_name="lesson_progress",
    )
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="student_progress",
    )
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("completed_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("enrollment", "lesson"),
                name="unique_enrollment_lesson_progress",
            )
        ]

    def __str__(self):
        return f"{self.enrollment.student} completed {self.lesson}"
