from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("teachers", "0002_teacherprofile_assignments"),
    ]

    operations = [
        migrations.AddField(
            model_name="teacherprofile",
            name="teaching_category",
            field=models.CharField(
                choices=[("ACADEMIC", "Academic Teacher"), ("TRAFFIC_RULES", "Traffic Rules Teacher")],
                db_index=True,
                default="ACADEMIC",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="teacherprofile",
            name="teaching_level",
            field=models.CharField(
                choices=[("PRIMARY", "Primary"), ("SECONDARY", "Secondary"), ("BOTH", "Both"), ("NONE", "Not applicable")],
                default="PRIMARY",
                max_length=10,
            ),
        ),
    ]
