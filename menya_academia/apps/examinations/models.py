import secrets
import uuid

from django.conf import settings
from django.db import models

from apps.activation_codes.models import ActivationCode
from apps.provisual.models import Exam


class Question(models.Model):
    text_rw = models.TextField(verbose_name="Question (Kinyarwanda)")
    text_en = models.TextField(verbose_name="Question (English)", blank=True)
    text_fr = models.TextField(verbose_name="Question (French)", blank=True)
    image = models.ImageField(upload_to="questions/signs/", blank=True)
    explanation_rw = models.TextField(verbose_name="Explanation (Kinyarwanda)", blank=True)
    explanation_en = models.TextField(verbose_name="Explanation (English)", blank=True)
    explanation_fr = models.TextField(verbose_name="Explanation (French)", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("id",)

    def get_text(self, language="en"):
        return getattr(self, f"text_{language}", "") or self.text_en or self.text_rw

    def get_explanation(self, language="en"):
        return (
            getattr(self, f"explanation_{language}", "")
            or self.explanation_en
            or self.explanation_rw
        )

    def __str__(self):
        return self.text_en or self.text_rw[:80]


class AnswerOption(models.Model):
    class Letter(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    question = models.ForeignKey(
        Question, on_delete=models.CASCADE, related_name="options"
    )
    letter = models.CharField(max_length=1, choices=Letter.choices)
    text_rw = models.CharField(max_length=255)
    text_en = models.CharField(max_length=255, blank=True)
    text_fr = models.CharField(max_length=255, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        ordering = ("letter",)
        constraints = [
            models.UniqueConstraint(
                fields=("question", "letter"), name="unique_option_letter_per_question"
            ),
            models.UniqueConstraint(
                fields=("question",),
                condition=models.Q(is_correct=True),
                name="one_correct_option_per_question",
            ),
        ]

    def get_text(self, language="en"):
        return getattr(self, f"text_{language}", "") or self.text_en or self.text_rw

    def __str__(self):
        return f"{self.letter}. {self.text_en or self.text_rw}"


def create_anonymous_id():
    return f"CAND-{secrets.token_hex(4).upper()}"


class ExamAttempt(models.Model):
    class Status(models.TextChoices):
        IN_PROGRESS = "IN_PROGRESS", "In progress"
        COMPLETED = "COMPLETED", "Completed"
        TIMED_OUT = "TIMED_OUT", "Timed out"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    exam = models.ForeignKey(Exam, on_delete=models.PROTECT, related_name="attempts")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="exam_attempts",
    )
    activation_code = models.ForeignKey(
        ActivationCode, on_delete=models.PROTECT, related_name="attempts"
    )
    anonymous_id = models.CharField(
        max_length=20, default=create_anonymous_id, db_index=True
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.IN_PROGRESS
    )
    total_questions = models.PositiveSmallIntegerField()
    pass_mark = models.PositiveSmallIntegerField()
    score_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    correct_answers = models.PositiveSmallIntegerField(default=0)
    passed = models.BooleanField(default=False)
    started_at = models.DateTimeField(auto_now_add=True)
    deadline = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-started_at",)

    def __str__(self):
        return f"{self.anonymous_id} - {self.exam}"


class AttemptQuestion(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="ordered_questions"
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    correct_option = models.ForeignKey(
        AnswerOption, on_delete=models.PROTECT, related_name="correct_for_attempts"
    )
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "question"), name="unique_question_per_attempt"
            ),
            models.UniqueConstraint(
                fields=("attempt", "position"), name="unique_position_per_attempt"
            ),
        ]


class AttemptAnswer(models.Model):
    attempt = models.ForeignKey(
        ExamAttempt, on_delete=models.CASCADE, related_name="recorded_answers"
    )
    question = models.ForeignKey(Question, on_delete=models.PROTECT)
    selected_option = models.ForeignKey(
        AnswerOption, on_delete=models.PROTECT, null=True, blank=True
    )
    is_correct = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("attempt", "question"), name="one_answer_per_attempt_question"
            )
        ]
