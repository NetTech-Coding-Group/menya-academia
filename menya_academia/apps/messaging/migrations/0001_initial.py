import uuid

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
            name="Conversation",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("conversation_type", models.CharField(choices=[("STUDENT_TEACHER", "Student-Teacher"), ("STUDENT_ADMIN", "Student-Admin")], db_index=True, max_length=20)),
                ("category", models.CharField(blank=True, choices=[("ACCOUNT", "Account"), ("COURSE", "Course"), ("PAYMENT", "Payment"), ("TECHNICAL", "Technical support"), ("OTHER", "Other")], max_length=20)),
                ("subject", models.CharField(blank=True, max_length=180)),
                ("status", models.CharField(choices=[("OPEN", "Open"), ("PENDING", "Pending"), ("RESOLVED", "Resolved")], db_index=True, default="OPEN", max_length=10)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True, db_index=True)),
                ("last_message_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("course", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="messaging_conversations", to="courses.course")),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="student_conversations", to=settings.AUTH_USER_MODEL)),
                ("teacher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="teacher_conversations", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("-last_message_at", "-updated_at"),
            },
        ),
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("content", models.TextField(max_length=5000)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("is_read", models.BooleanField(db_index=True, default=False)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("conversation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="messaging.conversation")),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="sent_messages", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("created_at",),
            },
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["student", "conversation_type", "updated_at"], name="msg_conv_student_type_updated"),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["teacher", "updated_at"], name="msg_conv_teacher_updated"),
        ),
        migrations.AddIndex(
            model_name="conversation",
            index=models.Index(fields=["conversation_type", "status", "updated_at"], name="msg_conv_type_status_updated"),
        ),
        migrations.AddConstraint(
            model_name="conversation",
            constraint=models.UniqueConstraint(condition=models.Q(("conversation_type", "STUDENT_TEACHER")), fields=("student", "teacher", "course"), name="unique_student_teacher_course_conversation"),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["conversation", "created_at"], name="msg_conv_created"),
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["conversation", "is_read"], name="msg_conv_read"),
        ),
    ]
