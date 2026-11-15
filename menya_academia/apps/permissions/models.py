# apps/permissions/models.py
from django.conf import settings
from django.db import models


class TeacherPermission(models.Model):
    PERMISSION_KEYS = (
        ("can_create_course", "Create courses"),
        ("can_edit_course", "Edit courses"),
        ("can_delete_course", "Delete courses"),
        ("can_publish_course", "Publish courses"),
        ("can_create_lesson", "Create lessons"),
        ("can_edit_lesson", "Edit lessons"),
        ("can_delete_lesson", "Delete lessons"),
        ("can_upload_materials", "Upload videos and PDFs"),
        ("can_view_students", "View students"),
        ("can_manage_students", "Manage students"),
        ("can_view_student_progress", "View student progress"),
        ("can_create_exams", "Create exams"),
        ("can_edit_exams", "Edit exams"),
        ("can_delete_exams", "Delete exams"),
        ("can_grade_exams", "Grade exams"),
        ("can_create_assignments", "Create assignments"),
        ("can_grade_assignments", "Grade assignments"),
        ("can_create_quizzes", "Create quizzes"),
        ("can_send_messages", "Send messages"),
        ("can_send_announcements", "Create announcements"),
        ("can_view_reports", "View reports"),
        ("can_download_reports", "Download reports"),
    )

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="granted_permissions",
    )
    permission_key = models.CharField(max_length=50, choices=PERMISSION_KEYS)
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("teacher", "permission_key"),
                name="unique_teacher_permission",
            )
        ]

    def __str__(self):
        return f"{self.teacher}: {self.get_permission_key_display()}"