from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings

from apps.accounts.models import User
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment

from .models import PaymentTransaction
from .services import (
    confirm_verified_payment,
    request_course_mobile_money_payment,
)


class CoursePaymentFulfillmentTests(TestCase):
    def setUp(self):
        self.student = User.objects.create_user(
            email="student@example.com",
            username="student",
            full_name="Student One",
            phone_number="+250788000013",
            password="test-password",
            role=User.Role.STUDENT,
        )
        self.course = Course.objects.create(
            teacher=User.objects.create_user(
                email="teacher@example.com",
                username="teacher",
                full_name="Teacher One",
                phone_number="+250788000011",
                password="test-password",
                role=User.Role.TEACHER,
            ),
            title="Course one",
            education_level=Course.EducationLevel.PRIMARY,
            short_description="Course summary",
            description="Course description",
            price_rwf=5000,
            is_published=True,
        )
        self.payment = PaymentTransaction.objects.create(
            course=self.course,
            user=self.student,
            full_name=self.student.full_name,
            phone_number=self.student.phone_number,
            email=self.student.email,
            amount_rwf=self.course.price_rwf,
            provider=PaymentTransaction.Provider.MTN_MOMO,
        )

    def test_verified_payment_creates_course_enrollment(self):
        enrollment = confirm_verified_payment(
            reference=self.payment.reference,
            provider_reference="mtn-confirmed-001",
            amount_rwf=self.payment.amount_rwf,
        )

        self.assertIsInstance(enrollment, CourseEnrollment)
        self.assertEqual(enrollment.payment, self.payment)
        self.assertEqual(enrollment.student, self.student)
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.SUCCESSFUL)

    def test_successful_payment_retry_remains_idempotent_after_price_change(self):
        enrollment = confirm_verified_payment(
            reference=self.payment.reference,
            provider_reference="mtn-confirmed-002",
            amount_rwf=self.payment.amount_rwf,
        )
        self.course.price_rwf += 1000
        self.course.save(update_fields=("price_rwf",))

        retried_enrollment = confirm_verified_payment(
            reference=self.payment.reference,
            provider_reference="mtn-confirmed-002",
            amount_rwf=self.payment.amount_rwf,
        )

        self.assertEqual(retried_enrollment.pk, enrollment.pk)

    def test_mismatched_confirmed_amount_does_not_grant_access(self):
        with self.assertRaises(ValueError):
            confirm_verified_payment(
                reference=self.payment.reference,
                provider_reference="mtn-confirmed-003",
                amount_rwf=self.payment.amount_rwf + 1,
            )

        self.assertFalse(CourseEnrollment.objects.exists())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, PaymentTransaction.Status.PENDING)

    @override_settings(PAYMENTS_ENABLED=True)
    def test_checkout_fails_closed_without_a_provider_adapter(self):
        with self.assertRaises(ImproperlyConfigured):
            request_course_mobile_money_payment(
                course=self.course,
                user=self.student,
                phone_number=self.student.phone_number,
                provider=PaymentTransaction.Provider.MTN_MOMO,
            )

        self.assertEqual(PaymentTransaction.objects.count(), 1)
        self.assertFalse(CourseEnrollment.objects.exists())
