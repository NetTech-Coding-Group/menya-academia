from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.messaging.models import Conversation, Message
from apps.payments.models import PaymentTransaction
from apps.teachers.models import TeacherProfile


User = get_user_model()


@override_settings(
    STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
)
class MessagingTests(TestCase):
    def setUp(self):
        self.password = "StrongPass123!"
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student1",
            full_name="Student One",
            phone_number="0780000001",
            password=self.password,
            role=User.Role.STUDENT,
        )
        self.other_student = User.objects.create_user(
            email="student2@example.com",
            username="student2",
            full_name="Student Two",
            phone_number="0780000002",
            password=self.password,
            role=User.Role.STUDENT,
        )
        self.teacher = User.objects.create_user(
            email="teacher@example.com",
            username="teacher1",
            full_name="Teacher One",
            phone_number="0780000003",
            password=self.password,
            role=User.Role.TEACHER,
        )
        self.other_teacher = User.objects.create_user(
            email="teacher2@example.com",
            username="teacher2",
            full_name="Teacher Two",
            phone_number="0780000004",
            password=self.password,
            role=User.Role.TEACHER,
        )
        self.admin = User.objects.create_user(
            email="admin@example.com",
            username="admin1",
            full_name="Admin One",
            phone_number="0780000005",
            password=self.password,
            role=User.Role.ADMIN,
            is_staff=True,
        )
        self.teacher_profile = TeacherProfile.objects.create(
            user=self.teacher,
            teaching_subject=TeacherProfile.Subject.OTHER,
            qualifications="B.Ed",
            application_status=TeacherProfile.ApplicationStatus.APPROVED,
        )
        self.other_teacher_profile = TeacherProfile.objects.create(
            user=self.other_teacher,
            teaching_subject=TeacherProfile.Subject.OTHER,
            qualifications="B.Ed",
            application_status=TeacherProfile.ApplicationStatus.APPROVED,
        )
        self.course = Course.objects.create(
            teacher=self.teacher,
            title="Math Basics",
            education_level=Course.EducationLevel.PRIMARY,
            short_description="Short",
            description="Desc",
            price_rwf=1000,
            is_published=True,
        )
        self.payment = PaymentTransaction.objects.create(
            user=self.student,
            course=self.course,
            full_name=self.student.full_name,
            phone_number=self.student.phone_number,
            email=self.student.email,
            amount_rwf=1000,
            status=PaymentTransaction.Status.SUCCESSFUL,
        )
        self.enrollment = CourseEnrollment.objects.create(
            course=self.course,
            student=self.student,
            payment=self.payment,
        )

    def test_student_can_start_conversation_with_assigned_teacher(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("messaging:start_teacher_conversation", args=[self.teacher.pk]),
            {"course_id": str(self.course.pk)},
        )
        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        self.assertIn(str(conversation.pk), response.url)

    def test_student_can_send_message_and_teacher_can_reply(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        self.client.force_login(self.student)
        send_url = reverse("messaging:send_message", args=[conversation.pk])
        resp = self.client.post(send_url, {"content": "Hello teacher"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])
        msg = Message.objects.get(conversation=conversation, sender=self.student)
        self.assertEqual(msg.content, "Hello teacher")

        self.client.force_login(self.teacher)
        resp = self.client.post(send_url, {"content": "Hello student"}, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Message.objects.filter(conversation=conversation).count(), 2)

    def test_student_can_contact_admin(self):
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("messaging:contact_admin"),
            {"category": Conversation.Category.ACCOUNT, "subject": "Help", "content": "Need help"},
        )
        self.assertEqual(response.status_code, 302)
        conversation = Conversation.objects.get(conversation_type=Conversation.Type.STUDENT_ADMIN, student=self.student)
        self.assertTrue(Message.objects.filter(conversation=conversation, sender=self.student, content="Need help").exists())

    def test_unapproved_teacher_cannot_access_messaging(self):
        unapproved = User.objects.create_user(
            email="pending@example.com",
            username="pendingteacher",
            full_name="Pending Teacher",
            phone_number="0780000006",
            password=self.password,
            role=User.Role.TEACHER,
        )
        TeacherProfile.objects.create(
            user=unapproved,
            teaching_subject=TeacherProfile.Subject.OTHER,
            qualifications="B.Ed",
            application_status=TeacherProfile.ApplicationStatus.PENDING,
        )
        self.client.force_login(unapproved)
        response = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(response.status_code, 403)

    def test_student_cannot_access_other_student_conversation(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        self.client.force_login(self.other_student)
        response = self.client.get(reverse("messaging:conversation_detail", args=[conversation.pk]))
        self.assertEqual(response.status_code, 403)

    def test_teacher_cannot_access_other_teacher_conversation(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        self.client.force_login(self.other_teacher)
        response = self.client.get(reverse("messaging:conversation_detail", args=[conversation.pk]))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_send_message(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        response = self.client.post(reverse("messaging:send_message", args=[conversation.pk]), {"content": "Hi"})
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/", response.url)

    def test_empty_message_rejected(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        self.client.force_login(self.student)
        response = self.client.post(
            reverse("messaging:send_message", args=[conversation.pk]),
            {"content": "   "},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Message.objects.filter(conversation=conversation).exists())

    def test_read_status_and_unread_count(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        Message.objects.create(conversation=conversation, sender=self.student, content="Unread")
        self.client.force_login(self.teacher)
        inbox = self.client.get(reverse("messaging:inbox"))
        self.assertEqual(inbox.status_code, 200)
        # Unread count is annotated on conversation; open detail marks read.
        detail = self.client.get(reverse("messaging:conversation_detail", args=[conversation.pk]))
        self.assertEqual(detail.status_code, 200)
        msg = Message.objects.get(conversation=conversation)
        self.assertTrue(msg.is_read)
        self.assertIsNotNone(msg.read_at)

    def test_duplicate_student_teacher_conversation_prevented(self):
        self.client.force_login(self.student)
        url = reverse("messaging:start_teacher_conversation", args=[self.teacher.pk])
        self.client.post(url, {"course_id": str(self.course.pk)})
        self.client.post(url, {"course_id": str(self.course.pk)})
        self.assertEqual(
            Conversation.objects.filter(
                conversation_type=Conversation.Type.STUDENT_TEACHER,
                student=self.student,
                teacher=self.teacher,
                course=self.course,
            ).count(),
            1,
        )

    def test_messages_persist(self):
        conversation = Conversation.objects.create(
            conversation_type=Conversation.Type.STUDENT_TEACHER,
            student=self.student,
            teacher=self.teacher,
            course=self.course,
        )
        Message.objects.create(conversation=conversation, sender=self.student, content="Persist me")
        self.assertEqual(Message.objects.filter(conversation=conversation, content="Persist me").count(), 1)
