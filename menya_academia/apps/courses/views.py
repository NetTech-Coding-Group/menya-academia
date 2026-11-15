from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Exists, F, OuterRef, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.enrollments.services import paid_enrollment_for_user
from apps.payments.forms import CourseCheckoutForm
from apps.payments.services import (
    PaymentGatewayNotConfigured,
    request_course_mobile_money_payment,
)
from apps.teachers.models import TeacherProfile

from .models import Course


def catalog(request):
    verified_teacher = TeacherProfile.objects.filter(
        user_id=OuterRef("teacher_id"),
        application_status=TeacherProfile.ApplicationStatus.APPROVED,
    )
    courses = Course.objects.filter(
        is_published=True,
        is_archived=False,
        teacher__teacher_profile__application_status=TeacherProfile.ApplicationStatus.APPROVED,
    ).select_related("teacher").annotate(teacher_verified=Exists(verified_teacher))
    selected_level = request.GET.get("level", "")
    search = request.GET.get("q", "").strip()
    if selected_level in Course.EducationLevel.values:
        courses = courses.filter(education_level=selected_level)
    if search:
        courses = courses.filter(
            Q(title__icontains=search)
            | Q(short_description__icontains=search)
            | Q(teacher__full_name__icontains=search)
        )

    enrolled_ids = set()
    if request.user.is_authenticated:
        enrolled_ids = set(
            request.user.course_enrollments.filter(
                payment__status="SUCCESSFUL",
                payment__course_id=F("course_id"),
                payment__user_id=F("student_id"),
            ).values_list("course_id", flat=True)
        )

    return render(
        request,
        "courses/catalog.html",
        {
            "courses": courses,
            "levels": Course.EducationLevel.choices,
            "selected_level": selected_level,
            "search": search,
            "enrolled_ids": enrolled_ids,
        },
    )


def course_detail(request, slug):
    verified_teacher = TeacherProfile.objects.filter(
        user_id=OuterRef("teacher_id"),
        application_status=TeacherProfile.ApplicationStatus.APPROVED,
    )
    course_query = (
        Course.objects.select_related("teacher")
        .annotate(teacher_verified=Exists(verified_teacher))
        .filter(slug=slug)
    )
    if request.user.is_authenticated:
        course_query = course_query.filter(
            Q(
                is_published=True,
                is_archived=False,
                teacher__teacher_profile__application_status=TeacherProfile.ApplicationStatus.APPROVED,
            )
            | Q(
                enrollments__student=request.user,
                enrollments__payment__status="SUCCESSFUL",
                enrollments__payment__course_id=F("id"),
                enrollments__payment__user_id=F("enrollments__student_id"),
            )
        ).distinct()
    else:
        course_query = course_query.filter(is_published=True, is_archived=False)
    course = get_object_or_404(course_query)
    enrollment = (
        paid_enrollment_for_user(course=course, user=request.user)
        if request.user.is_authenticated
        else None
    )
    is_teacher = (
        request.user.is_authenticated
        and request.user.role == request.user.Role.TEACHER
        and course.teacher_id == request.user.pk
        and course.teacher_verified
    )
    return render(
        request,
        "courses/detail.html",
        {
            "course": course,
            "enrollment": enrollment,
            "is_teacher": is_teacher,
        },
    )


@login_required(login_url="accounts:login")
def checkout(request, slug):
    course = get_object_or_404(
        Course,
        slug=slug,
        is_published=True,
        is_archived=False,
        teacher__teacher_profile__application_status=TeacherProfile.ApplicationStatus.APPROVED,
    )
    if request.user.role != request.user.Role.STUDENT:
        raise PermissionDenied("Only student accounts can purchase courses.")
    enrollment = paid_enrollment_for_user(course=course, user=request.user)
    if enrollment:
        return redirect(
            "enrollments:course_learning",
            enrollment_id=enrollment.pk,
        )

    form = CourseCheckoutForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            request_course_mobile_money_payment(
                course=course,
                user=request.user,
                phone_number=form.cleaned_data["phone_number"],
                provider=form.cleaned_data["provider"],
            )
        except PaymentGatewayNotConfigured as exc:
            messages.error(request, str(exc))
        else:
            messages.error(
                request,
                "The payment provider did not return a verifiable transaction. No access was granted.",
            )
    return render(
        request,
        "payments/course_checkout.html",
        {"course": course, "form": form},
    )
