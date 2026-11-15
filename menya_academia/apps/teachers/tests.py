from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.permissions.models import TeacherPermission

from .models import TeacherProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TeacherRegistrationTests(TestCase):
    def application_data(self, **overrides):
        data = {
            "full_name": "Aline Teacher",
            "email": "aline@example.com",
            "phone_number": "+250788000099",
            "password1": "Strong-test-password-2026",
            "password2": "Strong-test-password-2026",
            "teaching_subject": TeacherProfile.Subject.ROAD_SIGNS,
            "qualifications": "Certified road safety instructor",
            "teaching_experience": "Five years",
            "institution": "Kigali Driving School",
            "terms_accepted": "on",
        }
        data.update(overrides)
        return data

    def test_registration_creates_pending_teacher_and_sends_notifications(self):
        response = self.client.post(
            reverse("teachers:register"),
            self.application_data(),
        )

        self.assertRedirects(response, reverse("accounts:login"))
        user = User.objects.get(email="aline@example.com")
        profile = user.teacher_profile
        self.assertEqual(user.role, User.Role.TEACHER)
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_email_verified)
        self.assertEqual(
            profile.application_status,
            TeacherProfile.ApplicationStatus.PENDING,
        )
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn("verify/", mail.outbox[0].body)
        self.assertIn("Teacher application received", mail.outbox[1].subject)

    def test_password_mismatch_and_terms_are_required(self):
        response = self.client.post(
            reverse("teachers:register"),
            self.application_data(password2="different-password"),
        )
        self.assertContains(response, "The passwords do not match.")
        self.assertFalse(User.objects.filter(email="aline@example.com").exists())

        response = self.client.post(
            reverse("teachers:register"),
            self.application_data(terms_accepted=""),
        )
        self.assertContains(response, "This field is required.")
        self.assertFalse(User.objects.filter(email="aline@example.com").exists())

    def test_supporting_documents_reject_disallowed_extensions(self):
        data = self.application_data()
        data["supporting_documents"] = SimpleUploadedFile(
            "not-a-document.exe",
            b"MZ executable",
            content_type="application/octet-stream",
        )
        response = self.client.post(
            reverse("teachers:register"),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Upload a PDF, JPG, or PNG")
        self.assertFalse(User.objects.filter(email="aline@example.com").exists())

    def test_teacher_cannot_open_workspace_before_approval(self):
        response = self.client.post(
            reverse("teachers:register"),
            self.application_data(),
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email="aline@example.com")
        user.is_email_verified = True
        user.save(update_fields=("is_email_verified",))

        self.client.force_login(user)
        response = self.client.get(reverse("teacher_workspace:workspace"))

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.get(reverse("teachers:application_status")).status_code,
            200,
        )

    def test_login_sends_pending_teacher_to_application_status(self):
        self.client.post(reverse("teachers:register"), self.application_data())
        teacher = User.objects.get(email="aline@example.com")
        teacher.is_email_verified = True
        teacher.save(update_fields=("is_email_verified",))

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": teacher.email,
                "password": "Strong-test-password-2026",
            },
        )

        self.assertRedirects(response, reverse("teachers:application_status"))

    def test_admin_approval_verifies_and_audits_teacher(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            full_name="Platform Admin",
            phone_number="+250788000001",
            password="Secure-test-password-2026",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.post(reverse("teachers:register"), self.application_data())
        teacher = User.objects.get(email="aline@example.com")
        teacher.is_email_verified = True
        teacher.save(update_fields=("is_email_verified",))
        profile = teacher.teacher_profile
        TeacherPermission.objects.create(
            teacher=teacher,
            permission_key="can_create_course",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse(
                "administrators:teacher_application_approve",
                args=(profile.pk,),
            )
        )

        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        teacher.refresh_from_db()
        self.assertEqual(
            profile.application_status,
            TeacherProfile.ApplicationStatus.APPROVED,
        )
        self.assertEqual(profile.approved_by, admin)
        self.assertIsNotNone(profile.approval_date)
        self.assertEqual(teacher.role, User.Role.TEACHER)
        self.assertFalse(
            TeacherPermission.objects.filter(teacher=teacher).exists()
        )
        self.assertEqual(len(mail.outbox), 4)
        self.assertIn("approved", mail.outbox[-1].subject.lower())

    def test_rejection_requires_a_reason_and_disables_teacher_grants(self):
        admin = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            full_name="Platform Admin",
            phone_number="+250788000001",
            password="Secure-test-password-2026",
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.client.post(reverse("teachers:register"), self.application_data())
        teacher = User.objects.get(email="aline@example.com")
        profile = teacher.teacher_profile
        TeacherPermission.objects.create(
            teacher=teacher,
            permission_key="can_create_course",
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse(
                "administrators:teacher_application_reject",
                args=(profile.pk,),
            ),
            {"rejection_reason": ""},
        )
        self.assertEqual(response.status_code, 200)
        profile.refresh_from_db()
        self.assertEqual(
            profile.application_status,
            TeacherProfile.ApplicationStatus.PENDING,
        )

        response = self.client.post(
            reverse(
                "administrators:teacher_application_reject",
                args=(profile.pk,),
            ),
            {"rejection_reason": "Please provide a valid teaching certificate."},
        )
        self.assertEqual(response.status_code, 302)
        profile.refresh_from_db()
        self.assertEqual(
            profile.application_status,
            TeacherProfile.ApplicationStatus.REJECTED,
        )
        self.assertFalse(
            TeacherPermission.objects.filter(teacher=teacher).exists()
        )
        self.assertIn("valid teaching certificate", mail.outbox[-1].body)

    def test_non_admin_cannot_download_application_documents(self):
        self.client.post(reverse("teachers:register"), self.application_data())
        teacher = User.objects.get(email="aline@example.com")
        profile = teacher.teacher_profile
        self.client.force_login(teacher)

        response = self.client.get(
            reverse(
                "administrators:teacher_application_photo",
                args=(profile.pk,),
            )
        )

        self.assertEqual(response.status_code, 302)
