import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Conversation(models.Model):
    class Type(models.TextChoices):
        STUDENT_TEACHER = "STUDENT_TEACHER", "Student-Teacher"
        STUDENT_ADMIN = "STUDENT_ADMIN", "Student-Admin"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        PENDING = "PENDING", "Pending"
        RESOLVED = "RESOLVED", "Resolved"

    class Category(models.TextChoices):
        ACCOUNT = "ACCOUNT", "Account"
        COURSE = "COURSE", "Course"
        PAYMENT = "PAYMENT", "Payment"
        TECHNICAL = "TECHNICAL", "Technical support"
        OTHER = "OTHER", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation_type = models.CharField(max_length=20, choices=Type.choices, db_index=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="student_conversations",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="teacher_conversations",
    )
    course = models.ForeignKey(
        "courses.Course",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messaging_conversations",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        blank=True,
    )
    subject = models.CharField(max_length=180, blank=True)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.OPEN,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)
    last_message_at = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ("-last_message_at", "-updated_at")
        indexes = [
            models.Index(fields=("student", "conversation_type", "updated_at"), name="msg_conv_student_type_updated"),
            models.Index(fields=("teacher", "updated_at"), name="msg_conv_teacher_updated"),
            models.Index(fields=("conversation_type", "status", "updated_at"), name="msg_conv_type_status_updated"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("student", "teacher", "course"),
                condition=Q(conversation_type="STUDENT_TEACHER"),
                name="unique_student_teacher_course_conversation",
            ),
        ]

    def __str__(self):
        if self.conversation_type == self.Type.STUDENT_TEACHER:
            course_title = self.course.title if self.course_id else "Course"
            return f"{self.student} - {self.teacher} ({course_title})"
        return f"Support: {self.student} ({self.get_status_display()})"

    @property
    def is_support(self):
        return self.conversation_type == self.Type.STUDENT_ADMIN

    def touch(self):
        self.last_message_at = timezone.now()
        self.save(update_fields=["last_message_at", "updated_at"])

    def display_title_for(self, user):
        if self.conversation_type == self.Type.STUDENT_TEACHER:
            if user.id == self.student_id:
                return self.teacher.full_name if self.teacher_id else "Teacher"
            return self.student.full_name
        if user.role == user.Role.STUDENT:
            return "Administration Support"
        return self.student.full_name

    def other_party_for(self, user):
        if self.conversation_type == self.Type.STUDENT_TEACHER:
            return self.teacher if user.id == self.student_id else self.student
        if user.role == user.Role.STUDENT:
            return None
        return self.student


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sent_messages",
    )
    content = models.TextField(max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("created_at",)
        indexes = [
            models.Index(fields=("conversation", "created_at"), name="msg_conv_created"),
            models.Index(fields=("conversation", "is_read"), name="msg_conv_read"),
        ]

    def __str__(self):
        return f"Message from {self.sender} at {self.created_at:%Y-%m-%d %H:%M}"

    @property
    def is_support_sender_admin(self):
        return self.conversation.conversation_type == Conversation.Type.STUDENT_ADMIN and self.sender.role in {
            self.sender.Role.ADMIN,
        }
