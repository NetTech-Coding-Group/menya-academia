from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("permissions", "0002_expand_teacher_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="teacherpermission",
            name="permission_key",
            field=models.CharField(
                choices=[
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
                ],
                max_length=50,
            ),
        ),
    ]
