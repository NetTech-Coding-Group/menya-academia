from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.activity_logs.models import ActivityLog
from apps.lessons.models import Lesson
from apps.payments.models import PaymentTransaction

from .models import CourseEnrollment, LessonProgress
from .services import paid_enrollment_for_user


def _require_student(user):
    if not user.is_active or user.role != user.Role.STUDENT:
        raise PermissionDenied("This page is available to active student accounts.")


@login_required(login_url="accounts:login")
def my_courses(request):
    _require_student(request.user)
    enrollments = (
        CourseEnrollment.objects.filter(
            student=request.user,
            payment__status=PaymentTransaction.Status.SUCCESSFUL,
            payment__course_id=F("course_id"),
            payment__user_id=F("student_id"),
        )
        .select_related("course", "course__teacher", "payment")
        .annotate(
            lessons_total=Count(
                "course__sections__lessons",
                filter=Q(course__sections__lessons__is_archived=False),
                distinct=True,
            ),
            lessons_completed=Count(
                "lesson_progress",
                filter=Q(lesson_progress__lesson__is_archived=False),
                distinct=True,
            ),
        )
    )
    for enrollment in enrollments:
        enrollment.progress_percent = (
            round(100 * enrollment.lessons_completed / enrollment.lessons_total)
            if enrollment.lessons_total
            else 0
        )
    return render(
        request,
        "enrollments/my_courses.html",
        {"enrollments": enrollments},
    )


@login_required(login_url="accounts:login")
def course_learning(request, enrollment_id):
    _require_student(request.user)
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("course", "payment"),
        pk=enrollment_id,
        student=request.user,
        payment__status=PaymentTransaction.Status.SUCCESSFUL,
        payment__course_id=F("course_id"),
        payment__user_id=F("student_id"),
    )
    progress_ids = set(
        enrollment.lesson_progress.filter(
            lesson__is_archived=False
        ).values_list("lesson_id", flat=True)
    )
    sections = (
        enrollment.course.sections.prefetch_related("lessons", "lessons__assignments")
        .annotate(
            active_lesson_count=Count(
                "lessons",
                filter=Q(lessons__is_archived=False),
                distinct=True,
            )
        )
        .order_by("position", "created_at")
    )
    lessons_total = sum(section.active_lesson_count for section in sections)
    lessons_completed = len(progress_ids)
    progress_percent = round(100 * lessons_completed / lessons_total) if lessons_total else 0
    announcements = enrollment.course.announcements.all()
    return render(
        request,
        "enrollments/course_learning.html",
        {
            "enrollment": enrollment,
            "course": enrollment.course,
            "sections": sections,
            "progress_ids": progress_ids,
            "lessons_total": lessons_total,
            "lessons_completed": lessons_completed,
            "progress_percent": progress_percent,
            "announcements": announcements,
        },
    )


@login_required(login_url="accounts:login")
@require_POST
def mark_lesson_complete(request, enrollment_id, lesson_id):
    _require_student(request.user)
    enrollment = get_object_or_404(
        CourseEnrollment.objects.select_related("course"),
        pk=enrollment_id,
        student=request.user,
        payment__status=PaymentTransaction.Status.SUCCESSFUL,
        payment__course_id=F("course_id"),
        payment__user_id=F("student_id"),
    )
    lesson = get_object_or_404(
        Lesson,
        pk=lesson_id,
        section__course=enrollment.course,
        is_archived=False,
    )
    LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
    active_lessons = Lesson.objects.filter(
        section__course=enrollment.course,
        is_archived=False,
    )
    if active_lessons.exists() and not active_lessons.exclude(
        student_progress__enrollment=enrollment
    ).exists():
        enrollment.status = CourseEnrollment.Status.COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=("status", "completed_at"))
    ActivityLog.objects.create(
        actor=request.user,
        actor_name=request.user.full_name,
        actor_email=request.user.email,
        actor_role=request.user.role,
        action="lesson.completed",
        description=f"Completed lesson {lesson.title} in {enrollment.course.title}.",
    )
    messages.success(request, "Lesson marked complete.")
    return redirect(
        "enrollments:course_learning",
        enrollment_id=enrollment.pk,
    )
