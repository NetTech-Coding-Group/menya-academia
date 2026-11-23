from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.examinations.models import AnswerOption, Question
from apps.lessons.models import CourseSection, Lesson
from apps.payments.models import PaymentTransaction
from apps.permissions.models import TeacherPermission
from apps.provisual.models import Exam
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


class TeacherExamCreateTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="traffic-teacher@example.com",
            username="traffic-teacher",
            full_name="Traffic Teacher",
            phone_number="+250788000021",
            password="test-password",
            role=User.Role.TEACHER,
        )
        self.profile = TeacherProfile.objects.create(
            user=self.teacher,
            teaching_category=TeacherProfile.TeachingCategory.TRAFFIC_RULES,
            teaching_level=TeacherProfile.TeachingLevel.NONE,
            teaching_subject=TeacherProfile.Subject.ROAD_TRAFFIC_RULES,
            qualifications="Traffic instructor certificate",
            application_status=TeacherProfile.ApplicationStatus.APPROVED,
        )
        self.url = reverse("teacher_workspace:exam_create")

    def grant(self, permission_key):
        return TeacherPermission.objects.create(
            teacher=self.teacher,
            permission_key=permission_key,
        )

    @staticmethod
    def create_question(text="What does a stop sign mean?", correct="A"):
        question = Question.objects.create(
            text_en=text,
            text_rw=text,
            is_active=True,
        )
        for letter in ("A", "B", "C", "D"):
            AnswerOption.objects.create(
                question=question,
                letter=letter,
                text_en=f"Option {letter}",
                text_rw=f"Option {letter}",
                is_correct=(letter == correct),
            )
        return question

    def test_unapproved_teacher_cannot_access_add_exam_page(self):
        self.profile.application_status = TeacherProfile.ApplicationStatus.PENDING
        self.profile.save(update_fields=["application_status"])
        self.grant("can_create_exams")
        self.client.force_login(self.teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_teacher_without_permission_cannot_access_add_exam_page(self):
        self.client.force_login(self.teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_approved_teacher_can_open_add_exam_page(self):
        self.grant("can_create_exams")
        self.client.force_login(self.teacher)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create Exam")
        self.assertContains(response, "Save as Draft")
        self.assertContains(response, "Submit for Approval")

    def test_teacher_can_save_exam_draft(self):
        question = self.create_question()
        self.grant("can_create_exams")
        self.client.force_login(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Road Signs Draft",
                "description": "Draft description",
                "category": "Road Signs",
                "question_count": "1",
                "duration_minutes": "20",
                "pass_mark": "70",
                "instructions": "Read carefully.",
                "selected_questions": [str(question.pk)],
                "action": "draft",
            },
        )

        self.assertEqual(response.status_code, 302)
        exam = Exam.objects.get(title="Road Signs Draft")
        self.assertEqual(exam.teacher, self.teacher)
        self.assertEqual(exam.status, Exam.Status.DRAFT)
        self.assertFalse(exam.is_active)
        self.assertEqual(exam.selected_questions.count(), 1)
        self.assertEqual(exam.question_count, 1)

    def test_teacher_can_submit_exam_for_approval(self):
        q1 = self.create_question("Question 1")
        q2 = self.create_question("Question 2")
        self.grant("can_create_exams")
        self.client.force_login(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Traffic Rules Exam",
                "description": "Basic traffic rules exam",
                "category": "Traffic Rules",
                "question_count": "2",
                "duration_minutes": "30",
                "pass_mark": "75",
                "instructions": "Answer all questions.",
                "selected_questions": [str(q1.pk), str(q2.pk)],
                "action": "submit",
            },
        )

        self.assertEqual(response.status_code, 302)
        exam = Exam.objects.get(title="Traffic Rules Exam")
        self.assertEqual(exam.status, Exam.Status.PENDING_APPROVAL)
        self.assertFalse(exam.is_active)
        self.assertEqual(exam.teacher, self.teacher)
        self.assertCountEqual(
            list(exam.selected_questions.values_list("pk", flat=True)),
            [q1.pk, q2.pk],
        )

    def test_submit_requires_selected_questions(self):
        self.grant("can_create_exams")
        self.client.force_login(self.teacher)

        response = self.client.post(
            self.url,
            {
                "title": "Incomplete Exam",
                "description": "Missing questions",
                "category": "Traffic Rules",
                "question_count": "1",
                "duration_minutes": "30",
                "pass_mark": "70",
                "instructions": "Answer all questions.",
                "action": "submit",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Exam.objects.filter(title="Incomplete Exam").exists())
        form = response.context["form"]
        self.assertIn("selected_questions", form.errors)

    def test_existing_provisual_practice_exam_is_preserved(self):
        exam = Exam.objects.create(
            slug="practice",
            title="PROVISUAL Practice Exam",
            question_count=30,
            duration_minutes=30,
            pass_mark=70,
            is_active=True,
        )

        self.assertEqual(exam.status, Exam.Status.APPROVED)
        self.assertTrue(exam.is_active)
        self.assertIsNone(exam.teacher)


class ProvisualBulkQuestionCreateTests(TestCase):
    def setUp(self):
        self.teacher = User.objects.create_user(
            email="bulk-teacher@example.com",
            username="bulk-teacher",
            full_name="Bulk Teacher",
            phone_number="+250788000031",
            password="test-password",
            role=User.Role.TEACHER,
        )
        TeacherProfile.objects.create(
            user=self.teacher,
            teaching_category=TeacherProfile.TeachingCategory.TRAFFIC_RULES,
            teaching_level=TeacherProfile.TeachingLevel.NONE,
            teaching_subject=TeacherProfile.Subject.ROAD_TRAFFIC_RULES,
            qualifications="Traffic instructor certificate",
            application_status=TeacherProfile.ApplicationStatus.APPROVED,
        )
        TeacherPermission.objects.create(teacher=self.teacher, permission_key="can_create_exams")
        self.client.force_login(self.teacher)
        self.url = reverse("teacher_workspace:question_create")

    @staticmethod
    def question_payload(index, **overrides):
        data = {
            f"q{index}-text_rw": f"Ikibazo {index}?",
            f"q{index}-option_a_rw": f"Igisubizo A {index}",
            f"q{index}-option_b_rw": f"Igisubizo B {index}",
            f"q{index}-option_c_rw": f"Igisubizo C {index}",
            f"q{index}-option_d_rw": f"Igisubizo D {index}",
            f"q{index}-correct_option": "A",
            f"q{index}-explanation_rw": f"Ibisobanuro {index}",
            f"q{index}-is_active": "on",
        }
        data.update(overrides)
        return data

    def build_payload(self, count=20):
        payload = {}
        for i in range(1, count + 1):
            payload.update(self.question_payload(i))
        return payload

    def test_bulk_create_page_shows_20_forms(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create PROVISUAL Questions")
        self.assertContains(response, "IKIBAZO 20/20")

    def test_successful_creation_of_20_questions(self):
        response = self.client.post(self.url, self.build_payload())
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Question.objects.count(), 20)
        question = Question.objects.first()
        self.assertEqual(question.approval_status, Question.ApprovalStatus.PENDING_APPROVAL)
        self.assertFalse(question.is_active)
        self.assertEqual(question.options.count(), 4)
        self.assertEqual(question.options.filter(is_correct=True).count(), 1)
        self.assertTrue(question.text_rw)
        self.assertEqual(question.text_en, "")

    def test_incomplete_submission_is_rejected(self):
        payload = self.build_payload()
        payload["q20-text_rw"] = ""
        payload["q20-explanation_rw"] = ""
        payload["q20-option_a_rw"] = ""
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 0)
        self.assertContains(response, "Uzuza ibibazo byose 20")

    def test_missing_correct_answer_is_rejected(self):
        payload = self.build_payload()
        del payload["q3-correct_option"]
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.count(), 0)

    def test_unapproved_teacher_cannot_access_bulk_create(self):
        self.client.logout()
        other = User.objects.create_user(
            email="pending-bulk@example.com",
            username="pending-bulk",
            full_name="Pending Bulk",
            phone_number="+250788000032",
            password="test-password",
            role=User.Role.TEACHER,
        )
        TeacherProfile.objects.create(
            user=other,
            teaching_category=TeacherProfile.TeachingCategory.TRAFFIC_RULES,
            teaching_level=TeacherProfile.TeachingLevel.NONE,
            teaching_subject=TeacherProfile.Subject.ROAD_TRAFFIC_RULES,
            qualifications="Cert",
            application_status=TeacherProfile.ApplicationStatus.PENDING,
        )
        TeacherPermission.objects.create(teacher=other, permission_key="can_create_exams")
        self.client.force_login(other)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_image_upload_is_optional_and_saved(self):
        import io

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        payload = self.build_payload()
        buffer = io.BytesIO()
        Image.new("RGB", (1, 1), color="white").save(buffer, format="PNG")
        buffer.seek(0)
        image = SimpleUploadedFile("sign.png", buffer.read(), content_type="image/png")
        payload["q1-image"] = image
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 302)
        q1 = Question.objects.get(text_rw="Ikibazo 1?")
        self.assertTrue(q1.image.name)
