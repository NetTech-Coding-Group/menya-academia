from django.db import transaction
from django.utils import timezone

from apps.activation_codes.models import ActivationCode
from apps.payments.models import PaymentTransaction


class CodeActivationError(Exception):
    pass


@transaction.atomic
def activate_code(*, code_text, user=None):
    normalized_code = code_text.strip().upper()
    try:
        code = (
            ActivationCode.objects.select_for_update(of=("self",))
            .select_related("payment__package")
            .get(code=normalized_code)
        )
    except ActivationCode.DoesNotExist as exc:
        raise CodeActivationError("That activation code was not found.") from exc

    if code.payment.status != PaymentTransaction.Status.SUCCESSFUL:
        raise CodeActivationError("Payment for this code has not been verified.")
    if code.status in (ActivationCode.Status.REVOKED, ActivationCode.Status.CONSUMED):
        raise CodeActivationError("This activation code can no longer be used.")
    if code.payment.user_id and (
        not user or not user.is_authenticated or code.payment.user_id != user.pk
    ):
        raise CodeActivationError("This code belongs to a different account.")

    now = timezone.now()
    if code.expires_at and code.expires_at <= now:
        raise CodeActivationError("This activation code has expired.")

    if code.status == ActivationCode.Status.ISSUED:
        code.status = ActivationCode.Status.ACTIVE
        code.activated_at = now
        code.activated_by = user
        code.save(
            update_fields=("status", "activated_at", "expires_at", "activated_by")
        )

    if (
        code.package.max_exam_attempts
        and code.attempts_made >= code.package.max_exam_attempts
    ):
        raise CodeActivationError("The examination limit for this code has been reached.")

    if user and code.activated_by_id and code.activated_by_id != user.pk:
        raise CodeActivationError("This code is already linked to a different account.")
    return code
