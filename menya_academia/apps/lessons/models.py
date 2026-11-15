import uuid
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, URLValidator
from django.db import models
from django.utils import timezone

from apps.courses.models import Course


MAX_MATERIAL_BYTES = 100 * 1024 * 1024
VIDEO_DOMAINS = {"youtube.com", "youtube-nocookie.com", "youtu.be", "vimeo.com"}


def validate_material_file(upload):
    extension = Path(upload.name).suffix.lower()
    if upload.size > MAX_MATERIAL_BYTES:
        raise ValidationError("Learning materials must be 100 MB or smaller.")
    if extension not in {".pdf", ".mp4", ".webm", ".mov"}:
        raise ValidationError("Upload a PDF, MP4, WebM, or MOV file.")


def validate_video_url(value):
    URLValidator(schemes=["https"])(value)
    hostname = (urlparse(value).hostname or "").lower().rstrip(".")
    if not any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in VIDEO_DOMAINS
    ):
        raise ValidationError("Use a supported YouTube or Vimeo HTTPS video link.")


def lesson_material_upload_path(instance, filename):
    return f"course_materials/{instance.section.course_id}/{uuid.uuid4().hex}{Path(filename).suffix.lower()}"


class CourseSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField(max_length=180)
    position = models.PositiveSmallIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("course", "position"),
                name="unique_course_section_position",
            )
        ]

    def __str__(self):
        return f"{self.course}: {self.title}"


class Lesson(models.Model):
    class Kind(models.TextChoices):
        VIDEO = "VIDEO", "Video"
        PDF = "PDF", "PDF material"
        TEXT = "TEXT", "Reading"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    section = models.ForeignKey(
        CourseSection,
        on_delete=models.CASCADE,
        related_name="lessons",
    )
    title = models.CharField(max_length=180)
    description = models.CharField(max_length=300, blank=True)
    kind = models.CharField(max_length=8, choices=Kind.choices)
    content = models.TextField(blank=True)
    video_url = models.URLField(blank=True, validators=[validate_video_url])
    material = models.FileField(
        upload_to=lesson_material_upload_path,
        blank=True,
        validators=[validate_material_file],
    )
    position = models.PositiveSmallIntegerField(default=1)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("position", "created_at")
        constraints = [
            models.UniqueConstraint(
                fields=("section", "position"),
                name="unique_section_lesson_position",
            )
        ]

    def clean(self):
        super().clean()
        if self.kind == self.Kind.VIDEO and not self.video_url and not self.material:
            raise ValidationError(
                {"video_url": "Add a video link or upload a video file."}
            )
        if self.kind == self.Kind.PDF and not self.material:
            raise ValidationError({"material": "Upload a PDF for this lesson."})
        if self.kind == self.Kind.TEXT and not self.content.strip():
            raise ValidationError({"content": "Add the reading content."})
        if self.material:
            extension = Path(self.material.name).suffix.lower()
            if self.kind == self.Kind.PDF and extension != ".pdf":
                raise ValidationError({"material": "PDF lessons require a PDF file."})
            if self.kind == self.Kind.VIDEO and extension not in {
                ".mp4",
                ".webm",
                ".mov",
            }:
                raise ValidationError(
                    {"material": "Video lessons require an MP4, WebM, or MOV file."}
                )

    @property
    def course(self):
        return self.section.course

    def __str__(self):
        return self.title


class Assignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    title = models.CharField(max_length=180)
    instructions = models.TextField()
    max_points = models.PositiveSmallIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
    )
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("due_at", "created_at")

    def __str__(self):
        return f"{self.lesson}: {self.title}"

    @property
    def is_open(self):
        return self.due_at is None or self.due_at >= timezone.now()


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assignment_submissions",
    )
    answer = models.TextField()
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            models.UniqueConstraint(
                fields=("assignment", "student"),
                name="unique_student_assignment_submission",
            ),
            models.CheckConstraint(
                condition=models.Q(score__isnull=True)
                | models.Q(score__gte=0),
                name="submission_score_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.student}: {self.assignment}"

    @property
    def is_graded(self):
        return self.graded_at is not None
