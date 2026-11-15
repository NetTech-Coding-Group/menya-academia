import uuid

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify


class Course(models.Model):
    class EducationLevel(models.TextChoices):
        PRIMARY = "PRIMARY", "Primary"
        LOWER_SECONDARY = "LOWER_SECONDARY", "Lower secondary"
        UPPER_SECONDARY = "UPPER_SECONDARY", "Upper secondary"
        UNIVERSITY = "UNIVERSITY", "University"
        VOCATIONAL = "VOCATIONAL", "Vocational"
        PROFESSIONAL = "PROFESSIONAL", "Professional development"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="courses",
    )
    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    education_level = models.CharField(
        max_length=24,
        choices=EducationLevel.choices,
        db_index=True,
    )
    short_description = models.CharField(max_length=300)
    description = models.TextField()
    price_rwf = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    cover_image = models.ImageField(
        upload_to="course_covers/",
        blank=True,
    )
    is_published = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("education_level", "is_published", "is_archived"),
                name="courses_level_published",
            ),
            models.Index(
                fields=("teacher", "is_archived"),
                name="courses_teacher_archived",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title)[:160] or "course"
            self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class CourseAnnouncement(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="announcements",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="course_announcements",
    )
    title = models.CharField(max_length=180)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.course}: {self.title}"
