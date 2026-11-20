import uuid
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import FileSystemStorage
from django.db import models
from django.utils.deconstruct import deconstructible


MAX_SUPPORTING_DOCUMENT_BYTES = 10 * 1024 * 1024
ALLOWED_SUPPORTING_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


@deconstructible
class PrivateTeacherStorage(FileSystemStorage):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("location", settings.BASE_DIR / "private_uploads" / "teachers")
        kwargs.setdefault("base_url", None)
        super().__init__(*args, **kwargs)


def supporting_document_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"teacher_documents/{instance.application_id}/{uuid.uuid4().hex}{extension}"


def teacher_photo_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    return f"teacher_photos/{instance.user_id}/{uuid.uuid4().hex}{extension}"


def validate_supporting_document(upload):
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_SUPPORTING_DOCUMENT_EXTENSIONS:
        raise ValidationError("Upload a PDF, JPG, or PNG supporting document.")
    if upload.size > MAX_SUPPORTING_DOCUMENT_BYTES:
        raise ValidationError("Supporting documents must be 10 MB or smaller.")
    signature = upload.read(8)
    upload.seek(0)
    valid_signatures = {
        ".pdf": signature.startswith(b"%PDF-"),
        ".jpg": signature.startswith(b"\xff\xd8\xff"),
        ".jpeg": signature.startswith(b"\xff\xd8\xff"),
        ".png": signature.startswith(b"\x89PNG\r\n\x1a\n"),
    }
    if not valid_signatures[extension]:
        raise ValidationError("The uploaded file does not match its file extension.")


class TeacherProfile(models.Model):
    class ApplicationStatus(models.TextChoices):
        PENDING = "PENDING", "Pending review"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        SUSPENDED = "SUSPENDED", "Suspended"

    class Subject(models.TextChoices):
        ROAD_TRAFFIC_RULES = "ROAD_TRAFFIC_RULES", "Road traffic rules"
        ROAD_SIGNS = "ROAD_SIGNS", "Road signs"
        ROAD_SAFETY = "ROAD_SAFETY", "Road safety"
        OTHER = "OTHER", "Other"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="teacher_profile",
    )
    teaching_subject = models.CharField(max_length=32, choices=Subject.choices)
    teacher_role_title = models.CharField(
        max_length=120,
        blank=True,
        help_text="Role assigned by the administrator, for example Class Teacher or Head of Department.",
    )
    responsibilities = models.TextField(
        blank=True,
        help_text="Responsibilities assigned by the administrator.",
    )
    assigned_subjects = models.TextField(
        blank=True,
        help_text="Subjects assigned by the administrator (one per line or comma-separated).",
    )
    assigned_classes = models.ManyToManyField(
        "courses.Course",
        blank=True,
        related_name="assigned_teachers",
        help_text="Classes or courses this teacher is assigned to manage.",
    )
    qualifications = models.TextField()
    teaching_experience = models.TextField(blank=True)
    institution = models.CharField(max_length=180, blank=True)
    profile_photo = models.ImageField(
        upload_to=teacher_photo_upload_path,
        storage=PrivateTeacherStorage(),
        blank=True,
    )
    terms_accepted_at = models.DateTimeField(null=True, blank=True)
    application_status = models.CharField(
        max_length=10,
        choices=ApplicationStatus.choices,
        default=ApplicationStatus.PENDING,
        db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_teacher_applications",
    )
    approval_date = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("application_status", "-created_at")

    @property
    def is_verified_teacher(self):
        return self.application_status == self.ApplicationStatus.APPROVED

    @property
    def subject_list(self):
        raw = (self.assigned_subjects or "").replace("\r", "\n")
        parts = []
        for chunk in raw.split("\n"):
            parts.extend([item.strip() for item in chunk.split(",")])
        values = [item for item in parts if item]
        return values or [self.get_teaching_subject_display()]

    @property
    def responsibility_list(self):
        return [line.strip() for line in (self.responsibilities or "").splitlines() if line.strip()]

    def __str__(self):
        return f"{self.user.full_name} - {self.get_application_status_display()}"
class TeacherSupportingDocument(models.Model):
    application = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name="supporting_documents",
    )
    file = models.FileField(
        upload_to=supporting_document_upload_path,
        storage=PrivateTeacherStorage(),
        validators=[validate_supporting_document],
    )
    original_name = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("uploaded_at",)

    def __str__(self):
        return f"{self.application.user.full_name}: {self.original_name}"
