from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class TeacherManagementTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="admin",
            full_name="Platform Admin",
            phone_number="+250788000001",
            password="Secure-test-password-2026",
            role=User.Role.ADMIN,
            is_staff=True,
            is_email_verified=True,
        )

    def teacher_payload(self, **overrides):
        data = {
            "full_name": "Aline Teacher",
            "phone_number": "+250788000099",
            "email": "aline@example.com",
            "username": "aline_teacher",
            "password1": "Strong-test-password-2026",
            "password2": "Strong-test-password-2026",
            "teaching_category": TeacherProfile.TeachingCategory.ACADEMIC,
            "teaching_level": TeacherProfile.TeachingLevel.PRIMARY,
            "assigned_subjects": "Mathematics\nEnglish",
            "is_active": "on",
            "preferred_language": User.Language.ENGLISH,
            "is_email_verified": "on",
        }
        data.update(overrides)
        return data

    def test_public_teacher_registration_is_disabled(self):
        response = self.client.get(reverse("teachers:register"))
        self.assertEqual(response.status_code, 302)
        response = self.client.post(reverse("teachers:register"), {"email": "x@x.com"})
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.filter(email="x@x.com").exists())

    def test_admin_can_create_teacher(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("administrators:teacher_create"), self.teacher_payload())
        self.assertEqual(response.status_code, 302)
        teacher = User.objects.get(email="aline@example.com")
        self.assertEqual(teacher.role, User.Role.TEACHER)
        self.assertTrue(teacher.must_change_password)
        profile = teacher.teacher_profile
        self.assertEqual(profile.teaching_category, TeacherProfile.TeachingCategory.ACADEMIC)
        self.assertEqual(profile.teaching_level, TeacherProfile.TeachingLevel.PRIMARY)
        self.assertEqual(profile.application_status, TeacherProfile.ApplicationStatus.APPROVED)

    def test_duplicate_email_is_rejected(self):
        User.objects.create_user(
            email="aline@example.com",
            username="existing",
            full_name="Existing",
            phone_number="+250788000010",
            password="Secure-test-password-2026",
            role=User.Role.STUDENT,
        )
        self.client.force_login(self.admin)
        response = self.client.post(reverse("administrators:teacher_create"), self.teacher_payload())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "An account with this email already exists.")

    def test_teacher_must_change_temporary_password(self):
        self.client.force_login(self.admin)
        self.client.post(reverse("administrators:teacher_create"), self.teacher_payload())
        self.client.logout()

        teacher = User.objects.get(email="aline@example.com")
        self.assertTrue(teacher.must_change_password)
        self.client.post(
            reverse("accounts:login"),
            {"username": teacher.email, "password": "Strong-test-password-2026"},
        )
        response = self.client.get(reverse("teacher_workspace:workspace"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:force_password_change"), response.url)

        response = self.client.post(
            reverse("accounts:force_password_change"),
            {
                "old_password": "Strong-test-password-2026",
                "new_password1": "New-strong-password-2026",
                "new_password2": "New-strong-password-2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        teacher.refresh_from_db()
        self.assertFalse(teacher.must_change_password)

    def test_academic_teacher_receives_assigned_subjects(self):
        self.client.force_login(self.admin)
        payload = self.teacher_payload(
            teaching_category=TeacherProfile.TeachingCategory.ACADEMIC,
            teaching_level=TeacherProfile.TeachingLevel.SECONDARY,
            assigned_subjects="Physics\nChemistry",
        )
        self.client.post(reverse("administrators:teacher_create"), payload)
        profile = TeacherProfile.objects.get(user__email="aline@example.com")
        self.assertEqual(profile.teaching_category, TeacherProfile.TeachingCategory.ACADEMIC)
        self.assertEqual(profile.teaching_level, TeacherProfile.TeachingLevel.SECONDARY)
        self.assertIn("Physics", profile.subject_list)
        self.assertIn("Chemistry", profile.subject_list)

    def test_traffic_rules_teacher_category_is_enforced(self):
        self.client.force_login(self.admin)
        payload = self.teacher_payload(
            teaching_category=TeacherProfile.TeachingCategory.TRAFFIC_RULES,
            teaching_level=TeacherProfile.TeachingLevel.PRIMARY,  # should be normalized to NONE
            assigned_subjects="Road Signs",
        )
        self.client.post(reverse("administrators:teacher_create"), payload)
        profile = TeacherProfile.objects.get(user__email="aline@example.com")
        self.assertTrue(profile.is_traffic_rules_teacher)
        self.assertEqual(profile.teaching_level, TeacherProfile.TeachingLevel.NONE)

    def test_unauthorized_user_cannot_create_teacher_account(self):
        student = User.objects.create_user(
            email="student@example.com",
            username="student",
            full_name="Student",
            phone_number="+250788000022",
            password="Secure-test-password-2026",
            role=User.Role.STUDENT,
            is_email_verified=True,
        )
        self.client.force_login(student)
        response = self.client.get(reverse("administrators:teacher_create"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_teacher_cannot_access_another_teachers_records(self):
        teacher1 = User.objects.create_user(
            email="t1@example.com", username="t1", full_name="T1", phone_number="+250788000031",
            password="Secure-test-password-2026", role=User.Role.TEACHER, is_email_verified=True,
        )
        teacher2 = User.objects.create_user(
            email="t2@example.com", username="t2", full_name="T2", phone_number="+250788000032",
            password="Secure-test-password-2026", role=User.Role.TEACHER, is_email_verified=True,
        )
        TeacherProfile.objects.create(user=teacher1, teaching_subject=TeacherProfile.Subject.OTHER, qualifications="Q", application_status=TeacherProfile.ApplicationStatus.APPROVED, teaching_category=TeacherProfile.TeachingCategory.ACADEMIC, teaching_level=TeacherProfile.TeachingLevel.PRIMARY)
        TeacherProfile.objects.create(user=teacher2, teaching_subject=TeacherProfile.Subject.OTHER, qualifications="Q", application_status=TeacherProfile.ApplicationStatus.APPROVED, teaching_category=TeacherProfile.TeachingCategory.ACADEMIC, teaching_level=TeacherProfile.TeachingLevel.PRIMARY)
        TeacherPermission.objects.create(teacher=teacher1, permission_key="can_view_students")
        TeacherPermission.objects.create(teacher=teacher2, permission_key="can_view_students")

        # Create a course owned by teacher2
        from apps.courses.models import Course
        course = Course.objects.create(
            teacher=teacher2, title="T2 Course", education_level=Course.EducationLevel.PRIMARY,
            short_description="s", description="d", price_rwf=1000, is_published=True,
        )
        self.client.force_login(teacher1)
        response = self.client.get(reverse("teacher_workspace:course_detail", args=[course.pk]))
        self.assertEqual(response.status_code, 404)
