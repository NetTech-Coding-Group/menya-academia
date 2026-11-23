from django.contrib.auth import get_user_model
from django.db.models import Count, F, Q
from django.utils import timezone

from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.payments.models import PaymentTransaction
from apps.teachers.models import TeacherProfile

from .models import Conversation, Message


def is_admin_user(user):
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and (user.is_superuser or (user.is_staff and getattr(user, "role", "") == user.Role.ADMIN))
    )


def is_approved_teacher(user):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if getattr(user, "role", "") != user.Role.TEACHER:
        return False
    return TeacherProfile.objects.filter(
        user=user,
        application_status=TeacherProfile.ApplicationStatus.APPROVED,
    ).exists()


def student_can_use_messaging(user):
    return bool(user and user.is_authenticated and user.is_active and getattr(user, "role", "") == user.Role.STUDENT)


def enrolled_paid_courses_for_student(student):
    return (
        Course.objects.filter(
            enrollments__student=student,
            enrollments__payment__status=PaymentTransaction.Status.SUCCESSFUL,
            enrollments__payment__course_id=F("enrollments__course_id"),
            enrollments__payment__user_id=F("enrollments__student_id"),
            is_archived=False,
        )
        .select_related("teacher")
        .distinct()
        .order_by("title")
    )


def student_can_message_teacher(student, teacher, course):
    if not student_can_use_messaging(student):
        return False
    if not is_approved_teacher(teacher):
        return False
    if not course or course.is_archived:
        return False
    return CourseEnrollment.objects.filter(
        student=student,
        course=course,
        course__teacher=teacher,
        payment__status=PaymentTransaction.Status.SUCCESSFUL,
        payment__course_id=F("course_id"),
        payment__user_id=F("student_id"),
    ).exists()


def teacher_assigned_student_ids(teacher):
    return (
        CourseEnrollment.objects.filter(
            course__teacher=teacher,
            course__is_archived=False,
            payment__status=PaymentTransaction.Status.SUCCESSFUL,
            payment__course_id=F("course_id"),
            payment__user_id=F("student_id"),
        )
        .values_list("student_id", flat=True)
        .distinct()
    )


def can_access_conversation(user, conversation):
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if is_admin_user(user):
        return conversation.conversation_type == Conversation.Type.STUDENT_ADMIN
    if getattr(user, "role", "") == user.Role.STUDENT:
        return conversation.student_id == user.id
    if getattr(user, "role", "") == user.Role.TEACHER:
        if not is_approved_teacher(user):
            return False
        if conversation.conversation_type != Conversation.Type.STUDENT_TEACHER:
            return False
        if conversation.teacher_id != user.id:
            return False
        # Ensure teacher is still authorized for this student/course.
        if conversation.course_id:
            return student_can_message_teacher(conversation.student, user, conversation.course)
        return conversation.student_id in set(teacher_assigned_student_ids(user))
    return False


def conversations_for_user(user):
    qs = Conversation.objects.select_related("student", "teacher", "course").annotate(
        unread_count=Count(
            "messages",
            filter=Q(messages__is_read=False) & ~Q(messages__sender=user),
            distinct=True,
        )
    )
    if is_admin_user(user):
        return qs.filter(conversation_type=Conversation.Type.STUDENT_ADMIN)
    if getattr(user, "role", "") == user.Role.STUDENT:
        return qs.filter(student=user)
    if getattr(user, "role", "") == user.Role.TEACHER and is_approved_teacher(user):
        return qs.filter(conversation_type=Conversation.Type.STUDENT_TEACHER, teacher=user)
    return qs.none()


def unread_message_count(user):
    if not user or not user.is_authenticated or not user.is_active:
        return 0
    qs = Message.objects.filter(is_read=False).exclude(sender=user)
    if is_admin_user(user):
        return qs.filter(conversation__conversation_type=Conversation.Type.STUDENT_ADMIN).count()
    if getattr(user, "role", "") == user.Role.STUDENT:
        return qs.filter(conversation__student=user).count()
    if getattr(user, "role", "") == user.Role.TEACHER and is_approved_teacher(user):
        return qs.filter(
            conversation__conversation_type=Conversation.Type.STUDENT_TEACHER,
            conversation__teacher=user,
        ).count()
    return 0


def mark_conversation_read(conversation, user):
    now = timezone.now()
    updated = (
        Message.objects.filter(conversation=conversation, is_read=False)
        .exclude(sender=user)
        .update(is_read=True, read_at=now)
    )
    if updated:
        from apps.notifications.models import Notification

        try:
            from django.urls import reverse

            url = reverse("messaging:conversation_detail", kwargs={"conversation_id": conversation.pk})
        except Exception:
            url = ""
        Notification.objects.filter(recipient=user, is_read=False, url=url).update(is_read=True)
    return updated


def get_or_create_student_teacher_conversation(*, student, teacher, course):
    if not student_can_message_teacher(student, teacher, course):
        raise PermissionError("You are not allowed to start this conversation.")
    conversation, _ = Conversation.objects.get_or_create(
        conversation_type=Conversation.Type.STUDENT_TEACHER,
        student=student,
        teacher=teacher,
        course=course,
        defaults={"status": Conversation.Status.OPEN},
    )
    return conversation


def get_or_create_support_conversation(*, student, category, subject=""):
    if not student_can_use_messaging(student):
        raise PermissionError("Only students can contact administration.")
    category = category or Conversation.Category.OTHER
    valid_categories = {c for c, _ in Conversation.Category.choices}
    if category not in valid_categories:
        category = Conversation.Category.OTHER
    # Reuse latest open/pending support conversation in same category to avoid duplicates.
    existing = (
        Conversation.objects.filter(
            conversation_type=Conversation.Type.STUDENT_ADMIN,
            student=student,
            category=category,
            status__in=[Conversation.Status.OPEN, Conversation.Status.PENDING],
        )
        .order_by("-updated_at")
        .first()
    )
    if existing:
        if subject and not existing.subject:
            existing.subject = subject[:180]
            existing.save(update_fields=["subject", "updated_at"])
        return existing
    return Conversation.objects.create(
        conversation_type=Conversation.Type.STUDENT_ADMIN,
        student=student,
        category=category,
        subject=(subject or "")[:180],
        status=Conversation.Status.OPEN,
    )


def can_send_in_conversation(user, conversation):
    if not can_access_conversation(user, conversation):
        return False
    if conversation.conversation_type == Conversation.Type.STUDENT_TEACHER:
        if getattr(user, "role", "") == user.Role.TEACHER:
            return is_approved_teacher(user)
        return student_can_use_messaging(user)
    if conversation.conversation_type == Conversation.Type.STUDENT_ADMIN:
        return student_can_use_messaging(user) or is_admin_user(user)
    return False


def get_support_recipients():
    User = get_user_model()
    return User.objects.filter(is_active=True, role=User.Role.ADMIN).order_by("full_name")
