from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("courses", "0001_initial"),
        ("teachers", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherprofile",
            name="teacher_role_title",
            field=models.CharField(
                blank=True,
                help_text="Role assigned by the administrator, for example Class Teacher or Head of Department.",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="teacherprofile",
            name="responsibilities",
            field=models.TextField(
                blank=True,
                help_text="Responsibilities assigned by the administrator.",
            ),
        ),
        migrations.AddField(
            model_name="teacherprofile",
            name="assigned_subjects",
            field=models.TextField(
                blank=True,
                help_text="Subjects assigned by the administrator (one per line or comma-separated).",
            ),
        ),
        migrations.AddField(
            model_name="teacherprofile",
            name="assigned_classes",
            field=models.ManyToManyField(
                blank=True,
                help_text="Classes or courses this teacher is assigned to manage.",
                related_name="assigned_teachers",
                to="courses.course",
            ),
        ),
    ]
