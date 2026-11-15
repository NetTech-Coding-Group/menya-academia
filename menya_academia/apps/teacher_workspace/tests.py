from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.lessons.models import CourseSection, Lesson
from apps.payments.models import PaymentTransaction
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile


class TeacherWorkspaceAccessTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            username="teacher",
            full_name="Teacher One",
            phone_number="+250788000011",
            password="test-password",
            role=User.Role.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            email="other@example.com",
            username="other-teacher",
            full_name="Teacher Two",
            phone_number="+250788000012",
            password="test-password",
            role=User.Role.TEACHER,
        )
        for teacher in (self.teacher, self.other_teacher):
            TeacherProfile.objects.create(
                user=teacher,
                teaching_subject=TeacherProfile.Subject.ROAD_TRAFFIC_RULES,
                qualifications="Driving instructor certificate",
                application_status=TeacherProfile.ApplicationStatus.APPROVED,
            )
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student",
            full_name="Student One",
            phone_number="+250788000013",
            password="test-password",
            role=User.Role.STUDENT,
        )
        self.course = self.create_course(self.teacher, "My course")
        self.other_course = self.create_course(self.other_teacher, "Other course")
        self.section = CourseSection.objects.create(
            course=self.course,
            title="Getting started",
            position=1,
        )
        self.lesson = Lesson.objects.create(
            section=self.section,
            title="First lesson",
            kind=Lesson.Kind.TEXT,
            content="Course content.",
            position=1,
        )
        self.client.force_login(self.teacher)

    @staticmethod
    def create_course(teacher, title):
        return Course.objects.create(
            teacher=teacher,
            title=title,
            education_level=Course.EducationLevel.PRIMARY,
            short_description=f"About {title}",
            description=f"Description for {title}",
            price_rwf=5000,
        )

    def grant(self, permission_key):
        return TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key=permission_key,
        )

    def test_workspace_lists_only_courses_owned_by_teacher(self):
        response = self.client.get(reverse("teacher_workspace:workspace"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.course.title)
        self.assertNotContains(response, self.other_course.title)

    def test_teacher_cannot_open_another_teachers_course(self):
        response = self.client.get(
            reverse(
                "teacher_workspace:course_detail",
                args=(self.other_course.pk,),
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_permission_page_includes_granted_and_denied_capabilities(self):
        self.grant("can_create_course")

        response = self.client.get(reverse("teacher_workspace:permissions"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create courses")
        self.assertContains(response, "Not granted")

    def test_lesson_upload_field_requires_upload_permission(self):
        url = reverse(
            "teacher_workspace:lesson_create",
            args=(self.course.pk,),
        )
        self.grant("can_create_lesson")

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("material", response.context["form"].fields)

        self.grant("can_upload_materials")
        response = self.client.get(url)
        self.assertIn("material", response.context["form"].fields)

    def test_student_cannot_open_course_lesson_without_verified_enrollment(self):
        lesson_url = reverse("lessons:lesson_detail", args=(self.lesson.pk,))
        self.client.force_login(self.student)

        response = self.client.get(lesson_url)
        self.assertEqual(response.status_code, 403)

        payment = PaymentTransaction.objects.create(
            course=self.course,
            user=self.student,
            full_name=self.student.full_name,
            phone_number=self.student.phone_number,
            email=self.student.email,
            amount_rwf=self.course.price_rwf,
            provider=PaymentTransaction.Provider.MTN_MOMO,
            provider_reference="verified-course-payment",
            status=PaymentTransaction.Status.SUCCESSFUL,
        )
        CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            payment=payment,
        )

        response = self.client.get(lesson_url)
        self.assertEqual(response.status_code, 200)

        self.lesson.is_archived = True
        self.lesson.save(update_fields=("is_archived",))
        response = self.client.get(lesson_url)
        self.assertEqual(response.status_code, 200)
