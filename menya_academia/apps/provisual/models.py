from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


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
    slug = models.SlugField(unique=True, default="practice")
    title = models.CharField(max_length=150, default="PROVISUAL Practice Exam")
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

    def __str__(self):
        return self.title
