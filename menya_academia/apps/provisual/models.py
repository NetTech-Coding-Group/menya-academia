from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify


class ExamPackage(models.Model):
    class PackageType(models.TextChoices):
        SINGLE = "SINGLE", "One exam"
        WEEKLY = "WEEKLY", "Weekly"
        TWO_WEEKS = "TWO_WEEKS", "Two weeks"
        MONTHLY = "MONTHLY", "Monthly"

    name = models.CharField(max_length=100)
    package_type = models.CharField(
        max_length=20, choices=PackageType.choices, unique=True
    )
    price_rwf = models.PositiveIntegerField()
    duration_days = models.PositiveIntegerField(default=1)
    max_exam_attempts = models.PositiveIntegerField(
        default=0,
        help_text="Set to 0 for unlimited attempts during the package validity.",
    )
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("display_order", "price_rwf")

    def __str__(self):
        return f"{self.name} - {self.price_rwf:,} RWF"


class Exam(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PENDING_APPROVAL = "PENDING_APPROVAL", "Pending approval"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    slug = models.SlugField(unique=True, blank=True, default="")
    title = models.CharField(max_length=150, default="PROVISUAL Practice Exam")
    description = models.TextField(blank=True)
    category = models.CharField(max_length=120, blank=True)
    instructions = models.TextField(blank=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_exams",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.APPROVED
    )
    selected_questions = models.ManyToManyField(
        "examinations.Question",
        blank=True,
        related_name="exams",
        help_text="Optional fixed question selection. Leave empty to use the eligible question bank.",
    )
    question_count = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    duration_minutes = models.PositiveSmallIntegerField(
        default=30, validators=[MinValueValidator(1), MaxValueValidator(180)]
    )
    pass_mark = models.PositiveSmallIntegerField(
        default=70, validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ("-updated_at", "-id")

    @property
    def is_teacher_exam(self):
        return self.teacher_id is not None

    @property
    def is_available_to_learners(self):
        return self.status == self.Status.APPROVED and self.is_active

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:60] or "exam"
            slug = base
            counter = 2
            while Exam.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                suffix = f"-{counter}"
                slug = f"{base[: max(1, 60 - len(suffix))]}{suffix}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
