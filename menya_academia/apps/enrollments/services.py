from django.db.models import F

from apps.payments.models import PaymentTransaction

from .models import CourseEnrollment


def paid_enrollment_for_user(*, course, user):
    return (
        CourseEnrollment.objects.select_related("course", "payment", "student")
        .filter(
            course=course,
            student=user,
            payment__course_id=F("course_id"),
            payment__user_id=F("student_id"),
            payment__status=PaymentTransaction.Status.SUCCESSFUL,
        )
        .first()
    )
