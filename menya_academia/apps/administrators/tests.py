from django.core import mail
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from apps.activity_logs.models import ActivityLog
from apps.accounts.models import User
from apps.permissions.decorators import teacher_permission_required
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile


class AdminPanelTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="platform-admin",
            full_name="Platform Admin",
            phone_number="+250788000010",
            password="Secure-test-password-2026",
            role=User.Role.ADMIN,
            is_email_verified=True,
            is_staff=True,
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            username="teacher",
            full_name="Teacher One",
            phone_number="+250788000011",
            password="Secure-test-password-2026",
            role=User.Role.TEACHER,
        )
        TeacherProfile.objects.create(
            user=self.teacher,
            teaching_subject=TeacherProfile.Subject.ROAD_TRAFFIC_RULES,
            qualifications="Driving instructor certificate",
            application_status=TeacherProfile.ApplicationStatus.APPROVED,
        )
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student",
            full_name="Student One",
            phone_number="+250788000012",
            password="Secure-test-password-2026",
            role=User.Role.STUDENT,
        )
        self.client.force_login(self.admin)

    def test_dashboard_uses_database_counts_and_does_not_invent_course_data(self):
        response = self.client.get(reverse("administrators:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total students")
        self.assertContains(response, "Total teachers")
        self.assertContains(response, "Total courses")
        self.assertContains(response, "Active enrollments")

    def test_non_admin_cannot_open_admin_panel(self):
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("administrators:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_admin_sign_in_lands_on_admin_dashboard(self):
        self.client.logout()

        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.admin.email,
                "password": "Secure-test-password-2026",
            },
        )

        self.assertRedirects(response, reverse("administrators:dashboard"))

    def test_user_search_and_activity_are_audited(self):
        response = self.client.get(
            reverse("administrators:user_list"),
            {"q": "teacher@example.com", "role": User.Role.TEACHER},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.teacher.email)
        self.assertNotContains(response, self.student.email)

        response = self.client.post(
            reverse("administrators:user_status", args=(self.teacher.pk,))
        )

        self.assertRedirects(
            response,
            reverse("administrators:user_detail", args=(self.teacher.pk,)),
        )
        self.teacher.refresh_from_db()
        self.assertFalse(self.teacher.is_active)
        self.assertTrue(
            ActivityLog.objects.filter(
                action="user.deactivated",
                actor=self.admin,
                description__contains=self.teacher.full_name,
            ).exists()
        )

    def test_changing_teacher_role_revokes_old_teacher_permissions(self):
        TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key="can_create_course",
        )

        response = self.client.post(
            reverse("administrators:user_edit", args=(self.teacher.pk,)),
            {
                "full_name": self.teacher.full_name,
                "username": self.teacher.username,
                "email": self.teacher.email,
                "phone_number": self.teacher.phone_number,
                "role": User.Role.STUDENT,
                "preferred_language": self.teacher.preferred_language,
                "is_email_verified": "on",
                "is_active": "on",
            },
        )

        # Teachers are managed through the dedicated teacher management flow.
        self.assertRedirects(response, reverse("administrators:teacher_edit", args=(self.teacher.pk,)))
        self.teacher.refresh_from_db()
        self.assertEqual(self.teacher.role, User.Role.TEACHER)
        self.assertTrue(
            TeacherPermission.objects.filter(teacher=self.teacher, permission_key="can_create_course").exists()
        )

    def test_teacher_permissions_are_replaced_and_audited(self):
        TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key="can_edit_course",
        )
        response = self.client.post(
            reverse("administrators:teacher_permissions"),
            {
                "teacher": str(self.teacher.pk),
                "permissions": ["can_create_course", "can_view_students"],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(
                TeacherPermission.objects.filter(teacher=self.teacher)
                .order_by("permission_key")
                .values_list("permission_key", flat=True)
            ),
            ["can_create_course", "can_view_students"],
        )
        self.assertTrue(
            ActivityLog.objects.filter(
                actor=self.admin,
                action="permissions.updated",
                description__contains=self.teacher.full_name,
            ).exists()
        )

    def test_permission_decorator_enforces_granted_teacher_capability(self):
        @teacher_permission_required("can_create_course")
        def protected_view(request):
            from django.http import HttpResponse

            return HttpResponse("allowed")

        request = RequestFactory().get("/")
        request.user = self.teacher
        with self.assertRaises(PermissionDenied):
            protected_view(request)

        TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key="can_create_course",
        )
        response = protected_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"allowed")

    def test_teacher_workspace_shows_granted_and_denied_capabilities(self):
        TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key="can_create_course",
        )
        self.client.force_login(self.teacher)

        response = self.client.get(reverse("teacher_workspace:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create courses")
        self.assertContains(response, "Allowed")
        self.assertContains(response, "Delete courses")
        self.assertContains(response, "Not granted")

    def test_activity_log_can_be_searched_by_role_and_action(self):
        ActivityLog.objects.create(
            actor=self.teacher,
            actor_name=self.teacher.full_name,
            actor_email=self.teacher.email,
            actor_role=self.teacher.role,
            action="course.created",
            description="Created an introductory course.",
        )

        response = self.client.get(
            reverse("administrators:activity_logs"),
            {"search": "introductory", "role": User.Role.TEACHER, "action": "course.created"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Created an introductory course.")

    def test_authenticated_write_requests_are_added_to_activity_log(self):
        self.client.force_login(self.student)

        response = self.client.post(
            reverse("set_language"),
            {"language": "fr", "next": reverse("home")},
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            ActivityLog.objects.filter(
                actor=self.student,
                action="post.set_language",
                status=ActivityLog.Status.SUCCESS,
            ).exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_admin_can_initiate_a_standard_password_reset(self):
        response = self.client.post(
            reverse("administrators:user_password_reset", args=(self.student.pk,))
        )

        self.assertRedirects(
            response,
            reverse("administrators:user_detail", args=(self.student.pk,)),
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.student.email, mail.outbox[0].to)
        self.assertTrue(
            ActivityLog.objects.filter(
                action="user.password_reset",
                actor=self.admin,
            ).exists()
        )

    def test_user_deletion_requires_confirmation_and_records_actor(self):
        response = self.client.get(
            reverse("administrators:user_delete", args=(self.student.pk,))
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("administrators:user_delete", args=(self.student.pk,)),
            {"confirm": "yes"},
        )

        self.assertRedirects(response, reverse("administrators:user_list"))
        self.assertFalse(User.objects.filter(pk=self.student.pk).exists())
        self.assertTrue(
            ActivityLog.objects.filter(
                action="user.deleted",
                actor=self.admin,
                description__contains=self.student.email,
            ).exists()
        )

    def test_staff_account_cannot_be_changed_or_deleted_from_panel(self):
        staff_user = User.objects.create_user(
            email="staff@example.com",
            username="staff",
            full_name="Another Admin",
            phone_number="+250788000013",
            password="Secure-test-password-2026",
            role=User.Role.ADMIN,
            is_staff=True,
        )

        response = self.client.get(
            reverse("administrators:user_edit", args=(staff_user.pk,))
        )
        self.assertRedirects(
            response,
            reverse("administrators:user_detail", args=(staff_user.pk,)),
        )
        self.assertTrue(User.objects.filter(pk=staff_user.pk).exists())
