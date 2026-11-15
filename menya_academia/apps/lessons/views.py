from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.activity_logs.models import ActivityLog
from apps.enrollments.services import paid_enrollment_for_user
from apps.payments.models import PaymentTransaction

from .forms import AssignmentSubmissionForm
from .models import Assignment, AssignmentSubmission, Lesson


def _require_student(user):
    if not user.is_active or user.role != user.Role.STUDENT:
        raise PermissionDenied("This page is available to active student accounts.")


@login_required(login_url="accounts:login")
def lesson_detail(request, lesson_id):
    _require_student(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
    )
    enrollment = paid_enrollment_for_user(
        course=lesson.section.course,
        user=request.user,
    )
    if not enrollment:
        raise PermissionDenied("Verified course enrollment is required.")
    assignments = (
        lesson.assignments.all()
        .prefetch_related("submissions")
    )
    submissions = {
        submission.assignment_id: submission
        for submission in AssignmentSubmission.objects.filter(
            assignment__lesson=lesson,
            student=request.user,
        )
    }
    return render(
        request,
        "lessons/lesson_detail.html",
        {
            "lesson": lesson,
            "course": lesson.section.course,
            "enrollment": enrollment,
            "assignments": assignments,
            "submissions": submissions,
            "is_completed": enrollment.lesson_progress.filter(lesson=lesson).exists(),
        },
    )


@login_required(login_url="accounts:login")
@require_POST
def assignment_submit(request, assignment_id):
    _require_student(request.user)
    assignment = get_object_or_404(
        Assignment.objects.select_related("lesson__section__course"),
        pk=assignment_id,
        lesson__section__course__is_archived=False,
    )
    enrollment = paid_enrollment_for_user(
        course=assignment.lesson.section.course,
        user=request.user,
    )
    if not enrollment:
        raise PermissionDenied("Verified course enrollment is required.")
    if not assignment.is_open:
        messages.error(request, "The assignment deadline has passed.")
        return redirect("lessons:lesson_detail", lesson_id=assignment.lesson_id)

    form = AssignmentSubmissionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Enter your assignment answer before submitting.")
        return redirect("lessons:lesson_detail", lesson_id=assignment.lesson_id)

    submission, created = AssignmentSubmission.objects.get_or_create(
        assignment=assignment,
        student=request.user,
        defaults={"answer": form.cleaned_data["answer"]},
    )
    if not created:
        if submission.is_graded:
            messages.error(request, "This assignment has already been graded.")
            return redirect("lessons:lesson_detail", lesson_id=assignment.lesson_id)
        submission.answer = form.cleaned_data["answer"]
        submission.save(update_fields=("answer", "updated_at"))
    ActivityLog.objects.create(
        actor=request.user,
        actor_name=request.user.full_name,
        actor_email=request.user.email,
        actor_role=request.user.role,
        action="assignment.submitted",
        description=f"Submitted {assignment.title} for {assignment.lesson.section.course.title}.",
    )
    messages.success(request, "Your assignment was submitted.")
    return redirect("lessons:lesson_detail", lesson_id=assignment.lesson_id)
