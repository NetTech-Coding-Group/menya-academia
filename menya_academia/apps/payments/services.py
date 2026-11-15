from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.utils import timezone

from apps.activation_codes.models import ActivationCode
from apps.enrollments.models import CourseEnrollment
from apps.payments.models import PaymentTransaction


class PaymentGatewayNotConfigured(ImproperlyConfigured):
    pass


def request_mobile_money_payment(*, package, full_name, phone_number, email, provider):
    if not settings.PAYMENTS_ENABLED:
        raise PaymentGatewayNotConfigured(
            "Online payments are not configured. No payment has been taken."
        )
    raise PaymentGatewayNotConfigured(
        "A verified MTN MoMo or Airtel Money provider adapter is required before "
        "online payments can be enabled. No payment has been taken."
    )


def request_course_mobile_money_payment(
    *,
    course,
    user,
    phone_number,
    provider,
):
    del course, user, phone_number, provider
    if not settings.PAYMENTS_ENABLED:
        raise PaymentGatewayNotConfigured(
            "Online course payments are not configured. No payment has been taken."
        )
    raise PaymentGatewayNotConfigured(
        "A verified MTN MoMo or Airtel Money provider adapter is required before "
        "course payments can be enabled. No payment has been taken."
    )


@transaction.atomic
def confirm_verified_payment(*, reference, provider_reference, amount_rwf):
    """Fulfill a payment only after an authenticated provider adapter verifies it."""
    if not provider_reference or not str(provider_reference).strip():
        raise ValueError("A verified provider transaction reference is required.")
    if type(amount_rwf) is not int or amount_rwf <= 0:
        raise ValueError("The provider-confirmed amount must be a positive RWF integer.")
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("package", "course", "user")
        .get(reference=reference)
    )
    if amount_rwf != payment.amount_rwf:
        raise ValueError("The provider-confirmed amount does not match the order.")
    if payment.status == PaymentTransaction.Status.SUCCESSFUL:
        if payment.provider_reference != provider_reference:
            raise ValueError("The payment reference was confirmed with conflicting data.")
        if payment.course_id:
            return CourseEnrollment.objects.get(payment=payment)
        return payment.activation_code
    if payment.status != PaymentTransaction.Status.PENDING:
        raise ValueError("Only a pending payment can be fulfilled.")
    if payment.course_id:
        if (
            payment.user_id is None
            or payment.user.role != payment.user.Role.STUDENT
        ):
            raise ValueError("This course order has no eligible student account.")
        if CourseEnrollment.objects.filter(
            course=payment.course,
            student=payment.user,
        ).exists():
            raise ValueError("The student is already enrolled in this course.")

    payment.status = PaymentTransaction.Status.SUCCESSFUL
    payment.provider_reference = provider_reference
    payment.save(update_fields=("status", "provider_reference", "updated_at"))
    if payment.course_id:
        return CourseEnrollment.objects.create(
            course=payment.course,
            student=payment.user,
            payment=payment,
        )

    expires_at = None
    if payment.package.package_type != payment.package.PackageType.SINGLE:
        expires_at = timezone.now() + timedelta(days=payment.package.duration_days)
    activation_code = ActivationCode.objects.create(
        payment=payment,
        expires_at=expires_at,
    )
    return activation_code
