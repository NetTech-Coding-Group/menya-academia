import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
import apps.teachers.models


def create_legacy_teacher_applications(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    TeacherProfile = apps.get_model("teachers", "TeacherProfile")
    for user in User.objects.filter(role="TEACHER").iterator():
        TeacherProfile.objects.get_or_create(
            user_id=user.pk,
            defaults={
                "teaching_subject": "OTHER",
                "qualifications": (
                    "Legacy teacher account. Review qualifications with this "
                    "teacher before approval."
                ),
                "application_status": "PENDING",
            },
        )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="TeacherProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "teaching_subject",
                    models.CharField(
                        choices=[
                            ("ROAD_TRAFFIC_RULES", "Road traffic rules"),
                            ("ROAD_SIGNS", "Road signs"),
                            ("ROAD_SAFETY", "Road safety"),
                            ("OTHER", "Other"),
                        ],
                        max_length=32,
                    ),
                ),
                ("qualifications", models.TextField()),
                ("teaching_experience", models.TextField(blank=True)),
                ("institution", models.CharField(blank=True, max_length=180)),
                (
                    "profile_photo",
                    models.ImageField(
                        blank=True,
                        storage=apps.teachers.models.PrivateTeacherStorage(),
                        upload_to=apps.teachers.models.teacher_photo_upload_path,
                    ),
                ),
                (
                    "terms_accepted_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "application_status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending review"),
                            ("APPROVED", "Approved"),
                            ("REJECTED", "Rejected"),
                            ("SUSPENDED", "Suspended"),
                        ],
                        db_index=True,
                        default="PENDING",
                        max_length=10,
                    ),
                ),
                ("approval_date", models.DateTimeField(blank=True, null=True)),
                ("rejection_reason", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "approved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="approved_teacher_applications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="teacher_profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("application_status", "-created_at"),
            },
        ),
        migrations.CreateModel(
            name="TeacherSupportingDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "file",
                    models.FileField(
                        storage=apps.teachers.models.PrivateTeacherStorage(),
                        upload_to=apps.teachers.models.supporting_document_upload_path,
                        validators=[
                            apps.teachers.models.validate_supporting_document
                        ],
                    ),
                ),
                ("original_name", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "application",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="supporting_documents",
                        to="teachers.teacherprofile",
                    ),
                ),
            ],
            options={
                "ordering": ("uploaded_at",),
            },
        ),
        migrations.RunPython(
            create_legacy_teacher_applications,
            migrations.RunPython.noop,
        ),
    ]
