from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.activation_codes.models import ActivationCode
from apps.activation_codes.services import CodeActivationError
from apps.examinations.models import AnswerOption, ExamAttempt, Question
from apps.examinations.services import (
    ExamAccessError,
    save_answer,
    start_exam_for_code,
    submit_attempt,
)
from apps.payments.models import PaymentTransaction
from apps.payments.services import (
    PaymentGatewayNotConfigured,
    confirm_verified_payment,
    request_mobile_money_payment,
)
from apps.provisual.models import Exam, ExamPackage


class ProvisualWorkflowTests(TestCase):
    def setUp(self):
        self.package = ExamPackage.objects.create(
            name="Single Examination",
            package_type=ExamPackage.PackageType.SINGLE,
            price_rwf=200,
            duration_days=1,
            max_exam_attempts=1,
        )
        self.exam = Exam.objects.create(
            slug="practice",
            title="Practice",
            question_count=2,
            duration_minutes=30,
            pass_mark=70,
        )
        self.payment = PaymentTransaction.objects.create(
            package=self.package,
            full_name="Test Candidate",
            phone_number="+250788000000",
            email="candidate@example.com",
            amount_rwf=200,
            provider=PaymentTransaction.Provider.MTN_MOMO,
        )
        self.activation_code = confirm_verified_payment(
            reference=self.payment.reference,
            provider_reference="verified-provider-ref",
            amount_rwf=200,
        )

    def add_question(self, text):
        question = Question.objects.create(text_en=text, text_rw=text)
        options = []
        for letter, is_correct in (("A", True), ("B", False), ("C", False), ("D", False)):
            options.append(
                AnswerOption.objects.create(
                    question=question,
                    letter=letter,
                    text_en=f"{text} option {letter}",
                    text_rw=f"{text} option {letter}",
                    is_correct=is_correct,
                )
            )
        return question, options

    def add_question_bank(self):
        return [
            self.add_question("Question one"),
            self.add_question("Question two"),
        ]

    def test_payment_fulfillment_is_idempotent(self):
        self.assertTrue(self.activation_code.code.startswith("ACADEMIA-"))
        self.assertLessEqual(len(self.activation_code.code), 40)
        duplicate = confirm_verified_payment(
            reference=self.payment.reference,
            provider_reference="verified-provider-ref",
            amount_rwf=200,
        )
        self.assertEqual(duplicate.pk, self.activation_code.pk)
        self.assertEqual(ActivationCode.objects.count(), 1)

    def test_payment_amount_must_match_order(self):
        pending = PaymentTransaction.objects.create(
            package=self.package,
            full_name="Another Candidate",
            phone_number="+250788000001",
            email="another@example.com",
            amount_rwf=200,
            provider=PaymentTransaction.Provider.AIRTEL_MONEY,
        )
        with self.assertRaises(ValueError):
            confirm_verified_payment(
                reference=pending.reference,
                provider_reference="wrong-amount",
                amount_rwf=1,
            )
        pending.refresh_from_db()
        self.assertEqual(pending.status, PaymentTransaction.Status.PENDING)

    @override_settings(PAYMENTS_ENABLED=False)
    def test_checkout_never_fakes_provider_confirmation(self):
        payment_count = PaymentTransaction.objects.count()
        with self.assertRaises(PaymentGatewayNotConfigured):
            request_mobile_money_payment(
                package=self.package,
                full_name="Test Candidate",
                phone_number="+250788000000",
                email="candidate@example.com",
                provider=PaymentTransaction.Provider.MTN_MOMO,
            )
        self.assertEqual(PaymentTransaction.objects.count(), payment_count)

    def test_activation_requires_a_confirmed_payment(self):
        self.add_question_bank()
        payment = PaymentTransaction.objects.create(
            package=self.package,
            full_name="Pending Candidate",
            phone_number="+250788000002",
            email="pending@example.com",
            amount_rwf=200,
            provider=PaymentTransaction.Provider.MTN_MOMO,
        )
        code = ActivationCode.objects.create(payment=payment)
        with self.assertRaises(CodeActivationError):
            start_exam_for_code(code_text=code.code)
        self.assertEqual(
            ExamAttempt.objects.filter(activation_code=code).count(),
            0,
        )

    def test_single_exam_code_is_consumed_after_submission(self):
        questions = self.add_question_bank()
        attempt = start_exam_for_code(code_text=self.activation_code.code)
        self.assertEqual(attempt.ordered_questions.count(), 2)

        for question, options in questions:
            save_answer(
                attempt_id=attempt.pk,
                question_id=question.pk,
                option_id=options[0].pk,
            )
        result = submit_attempt(attempt_id=attempt.pk)
        self.activation_code.refresh_from_db()

        self.assertEqual(result.status, ExamAttempt.Status.COMPLETED)
        self.assertEqual(result.score_percentage, 100)
        self.assertTrue(result.passed)
        self.assertEqual(self.activation_code.status, ActivationCode.Status.CONSUMED)
        with self.assertRaises(CodeActivationError):
            start_exam_for_code(code_text=self.activation_code.code)

    def test_invalid_answer_option_cannot_be_submitted_for_other_question(self):
        questions = self.add_question_bank()
        attempt = start_exam_for_code(code_text=self.activation_code.code)
        first_question, first_options = questions[0]
        second_question, _ = questions[1]
        save_answer(
            attempt_id=attempt.pk,
            question_id=first_question.pk,
            option_id=first_options[0].pk,
        )
        with self.assertRaises(ExamAccessError):
            save_answer(
                attempt_id=attempt.pk,
                question_id=second_question.pk,
                option_id=first_options[0].pk,
            )

    def test_deadline_is_enforced_by_server(self):
        self.add_question_bank()
        attempt = start_exam_for_code(code_text=self.activation_code.code)
        attempt.deadline = timezone.now() - timedelta(seconds=1)
        attempt.save(update_fields=("deadline",))
        result = submit_attempt(attempt_id=attempt.pk)
        self.assertEqual(result.status, ExamAttempt.Status.TIMED_OUT)

    def test_guest_attempt_is_bound_to_the_starting_session(self):
        questions = self.add_question_bank()
        attempt = start_exam_for_code(code_text=self.activation_code.code)
        url = reverse("exam_take", args=(attempt.pk,))
        self.assertEqual(self.client.get(url).status_code, 404)

        session = self.client.session
        session["exam_attempt_ids"] = [str(attempt.pk)]
        session.save()
        self.assertEqual(self.client.get(url).status_code, 200)
        question, options = questions[0]
        answer_url = reverse("exam_save_answer", args=(attempt.pk,))
        response = self.client.post(
            answer_url,
            {"question_id": question.pk, "option": options[0].pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(attempt.recorded_answers.count(), 1)

    def test_community_results_do_not_expose_candidate_identity(self):
        candidate = User.objects.create_user(
            email="private@example.com",
            username="private_candidate",
            full_name="Private Candidate Name",
            phone_number="+250788000099",
            password="Secure-test-password-2026",
        )
        ExamAttempt.objects.create(
            exam=self.exam,
            user=candidate,
            activation_code=self.activation_code,
            status=ExamAttempt.Status.COMPLETED,
            anonymous_id="CAND-TEST0001",
            total_questions=2,
            pass_mark=70,
            score_percentage=50,
            correct_answers=1,
            passed=False,
            deadline=timezone.now(),
            completed_at=timezone.now(),
        )
        response = self.client.get(reverse("community_results"))
        self.assertContains(response, "CAND-TEST0001")
        self.assertNotContains(response, "Private Candidate Name")
        self.assertNotContains(response, "private@example.com")


class ProvisualKinyarwandaRenderingTests(TestCase):
    def setUp(self):
        self.package = ExamPackage.objects.create(
            name="Single",
            package_type=ExamPackage.PackageType.SINGLE,
            price_rwf=200,
            duration_days=1,
            max_exam_attempts=1,
            is_active=True,
        )
        self.exam = Exam.objects.create(
            slug="practice",
            title="PROVISUAL Practice Exam",
            question_count=1,
            duration_minutes=30,
            pass_mark=70,
            is_active=True,
        )
        payment = PaymentTransaction.objects.create(
            package=self.package,
            full_name="Learner",
            phone_number="+250788000001",
            amount_rwf=200,
            provider=PaymentTransaction.Provider.MTN_MOMO,
        )
        self.code = confirm_verified_payment(
            reference=payment.reference,
            provider_reference="provider-ref-rw",
            amount_rwf=200,
        )
        question = Question.objects.create(
            text_rw="Iki kimenyetso gisobanura iki?",
            text_en="What does this sign mean?",
            text_fr="Que signifie ce panneau?",
            explanation_rw="Ibisobanuro mu Kinyarwanda.",
            explanation_en="English explanation.",
            explanation_fr="Explication francaise.",
            is_active=True,
            approval_status=Question.ApprovalStatus.APPROVED,
        )
        for letter, is_correct in [("A", True), ("B", False), ("C", False), ("D", False)]:
            AnswerOption.objects.create(
                question=question,
                letter=letter,
                text_rw=f"Igisubizo {letter}",
                text_en=f"Option {letter}",
                text_fr=f"Option {letter} FR",
                is_correct=is_correct,
            )

    def test_exam_take_and_review_render_kinyarwanda_only(self):
        start = self.client.post(reverse("activate_code"), {"code": self.code.code})
        self.assertEqual(start.status_code, 302)
        attempt = ExamAttempt.objects.get()

        take = self.client.get(reverse("exam_take", args=(attempt.pk,)))
        self.assertContains(take, "Iki kimenyetso gisobanura iki?")
        self.assertContains(take, "Igisubizo A")
        self.assertNotContains(take, "What does this sign mean?")
        self.assertNotContains(take, "Option A")

        submit_attempt(attempt_id=attempt.pk)
        review = self.client.get(reverse("exam_review", args=(attempt.pk,)))
        self.assertContains(review, "Iki kimenyetso gisobanura iki?")
        self.assertContains(review, "Ibisobanuro mu Kinyarwanda.")
        self.assertNotContains(review, "English explanation.")
        self.assertNotContains(review, "Explication francaise.")
