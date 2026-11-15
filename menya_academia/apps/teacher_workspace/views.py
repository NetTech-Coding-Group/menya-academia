from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.activity_logs.models import ActivityLog
from apps.courses.forms import CourseAnnouncementForm, CourseForm
from apps.courses.models import Course, CourseAnnouncement
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.services import paid_enrollment_for_user
from apps.lessons.forms import (
    AssignmentForm,
    AssignmentGradeForm,
    CourseSectionForm,
    LessonForm,
)
from apps.lessons.models import Assignment, AssignmentSubmission, Lesson
from apps.payments.models import PaymentTransaction
from apps.permissions.decorators import teacher_permission_required
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile


def _require_teacher(user):
    if not user.is_active or user.role != user.Role.TEACHER:
        raise PermissionDenied("This page is available to active teachers.")
    if not TeacherProfile.objects.filter(
        user=user,
        application_status=TeacherProfile.ApplicationStatus.APPROVED,
    ).exists():
        raise PermissionDenied("A teacher application must be approved first.")


def _managed_courses(user):
    _require_teacher(user)
    return Course.objects.filter(teacher=user, is_archived=False)


def _managed_course(user, course_id):
    return get_object_or_404(
        _managed_courses(user).prefetch_related("sections__lessons"),
        pk=course_id,
    )


def _record_teacher_activity(user, action, description):
    ActivityLog.objects.create(
        actor=user,
        actor_name=user.full_name,
        actor_email=user.email,
        actor_role=user.role,
        action=action,
        description=description,
    )


@login_required(login_url="accounts:login")
def workspace(request):
    _require_teacher(request.user)
    courses = _managed_courses(request.user)
    permission_groups = (
        ("Courses", ("can_create_course", "can_edit_course", "can_delete_course", "can_publish_course")),
        ("Lessons & materials", ("can_create_lesson", "can_edit_lesson", "can_delete_lesson", "can_upload_materials")),
        ("Students", ("can_view_students", "can_manage_students", "can_view_student_progress")),
        ("Exams", ("can_create_exams", "can_edit_exams", "can_delete_exams", "can_grade_exams")),
        ("Assignments", ("can_create_assignments", "can_grade_assignments", "can_create_quizzes")),
        ("Communication", ("can_send_messages", "can_send_announcements")),
        ("Reports", ("can_view_reports", "can_download_reports")),
    )
    granted = set(
        TeacherPermission.objects.filter(teacher=request.user).values_list(
            "permission_key", flat=True
        )
    )
    labels = dict(TeacherPermission.PERMISSION_KEYS)
    visible_permissions = [
        (title, [(key, labels[key]) for key in keys if key in granted])
        for title, keys in permission_groups
    ]
    return render(
        request,
        "teacher_workspace/dashboard.html",
        {
            "courses": courses,
            "course_count": courses.count(),
            "permission_groups": visible_permissions,
            "granted_count": len(granted),
            "can_create_course": "can_create_course" in granted,
            "can_view_students": "can_view_students" in granted,
            "can_create_assignments": "can_create_assignments" in granted,
            "can_grade_assignments": "can_grade_assignments" in granted,
            "can_send_announcements": "can_send_announcements" in granted,
        },
    )


@login_required(login_url="accounts:login")
def permissions(request):
    _require_teacher(request.user)
    granted = set(
        TeacherPermission.objects.filter(teacher=request.user).values_list(
            "permission_key", flat=True
        )
    )
    groups = (
        ("Courses", ("can_create_course", "can_edit_course", "can_delete_course", "can_publish_course")),
        ("Lessons & materials", ("can_create_lesson", "can_edit_lesson", "can_delete_lesson", "can_upload_materials")),
        ("Students", ("can_view_students", "can_manage_students", "can_view_student_progress")),
        ("Exams", ("can_create_exams", "can_edit_exams", "can_delete_exams", "can_grade_exams")),
        ("Assignments", ("can_create_assignments", "can_grade_assignments", "can_create_quizzes")),
        ("Communication", ("can_send_messages", "can_send_announcements")),
        ("Reports", ("can_view_reports", "can_download_reports")),
    )
    permission_labels = dict(TeacherPermission.PERMISSION_KEYS)
    permission_groups = [
        {
            "title": title,
            "permissions": [
                (key, permission_labels[key], key in granted)
                for key in keys
                if key in permission_labels
            ],
        }
        for title, keys in groups
    ]
    return render(
        request,
        "teacher_workspace/permissions.html",
        {"permission_groups": permission_groups, "granted_count": len(granted)},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_course")
def course_create(request):
    _require_teacher(request.user)
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.teacher = request.user
        course.save()
        _record_teacher_activity(
            request.user,
            "course.created",
            f"Created course {course.title}.",
        )
        messages.success(request, "Course created. Add sections and lessons before publishing.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/course_form.html",
        {"form": form, "page_title": "Create a course"},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_edit_course")
def course_edit(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    form = CourseForm(request.POST or None, request.FILES or None, instance=course)
    if request.method == "POST" and form.is_valid():
        changed = tuple(form.changed_data)
        course = form.save()
        if changed:
            _record_teacher_activity(
                request.user,
                "course.updated",
                f"Updated course {course.title} ({', '.join(changed)}).",
            )
            messages.success(request, "Course details updated.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/course_form.html",
        {"form": form, "course": course, "page_title": "Edit course"},
    )


@login_required(login_url="accounts:login")
def course_detail(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    granted = set(
        request.user.granted_permissions.values_list("permission_key", flat=True)
    )
    can_view_students = "can_view_students" in granted
    return render(
        request,
        "teacher_workspace/course_detail.html",
        {
            "course": course,
            "sections": course.sections.all().annotate(
                active_lesson_count=Count("lessons", filter=Q(lessons__is_archived=False))
            ),
            "student_count": (
                CourseEnrollment.objects.filter(
                    course=course,
                    payment__status=PaymentTransaction.Status.SUCCESSFUL,
                    payment__course_id=course.pk,
                    payment__user_id=F("student_id"),
                ).count()
                if can_view_students
                else None
            ),
            "can_edit": "can_edit_course" in granted,
            "can_publish": "can_publish_course" in granted,
            "can_archive": "can_delete_course" in granted,
            "can_create_lesson": "can_create_lesson" in granted,
            "can_edit_lesson": "can_edit_lesson" in granted,
            "can_delete_lesson": "can_delete_lesson" in granted,
            "can_create_assignments": "can_create_assignments" in granted,
            "can_grade_assignments": "can_grade_assignments" in granted,
            "can_view_students": can_view_students,
            "can_send_announcements": "can_send_announcements" in granted,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_publish_course")
@require_POST
def course_publish(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    if not course.is_published and not course.sections.filter(
        lessons__is_archived=False
    ).exists():
        messages.error(request, "Add at least one active lesson before publishing.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    course.is_published = not course.is_published
    course.save(update_fields=("is_published", "updated_at"))
    state = "published" if course.is_published else "unpublished"
    _record_teacher_activity(
        request.user,
        f"course.{state}",
        f"{state.title()} course {course.title}.",
    )
    messages.success(request, f"Course {state}.")
    return redirect("teacher_workspace:course_detail", course_id=course.pk)


@login_required(login_url="accounts:login")
@teacher_permission_required("can_delete_course")
@require_POST
def course_archive(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    course.is_archived = True
    course.is_published = False
    course.save(update_fields=("is_archived", "is_published", "updated_at"))
    _record_teacher_activity(
        request.user,
        "course.archived",
        f"Archived course {course.title}. Existing paid students retain access.",
    )
    messages.success(request, "Course archived. Existing enrolled students retain access.")
    return redirect("teacher_workspace:workspace")


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_lesson")
def section_create(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    form = CourseSectionForm(request.POST or None, course=course)
    if request.method == "POST" and form.is_valid():
        section = form.save(commit=False)
        section.course = course
        section.save()
        _record_teacher_activity(
            request.user,
            "section.created",
            f"Created section {section.title} in {course.title}.",
        )
        messages.success(request, "Course section created.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/section_form.html",
        {"form": form, "course": course},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_lesson")
def lesson_create(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    if not course.sections.exists():
        messages.error(request, "Create a course section before adding a lesson.")
        return redirect("teacher_workspace:section_create", course_id=course.pk)
    form = LessonForm(
        request.POST or None,
        request.FILES or None,
        course=course,
        allow_material_upload=request.user.granted_permissions.filter(
            permission_key="can_upload_materials"
        ).exists(),
    )
    if request.method == "POST" and form.is_valid():
        lesson = form.save()
        _record_teacher_activity(
            request.user,
            "lesson.created",
            f"Created lesson {lesson.title} in {course.title}.",
        )
        messages.success(request, "Lesson added.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/lesson_form.html",
        {"form": form, "course": course, "page_title": "Add lesson"},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_edit_lesson")
def lesson_edit(request, lesson_id):
    _require_teacher(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__teacher=request.user,
        section__course__is_archived=False,
    )
    course = lesson.section.course
    form = LessonForm(
        request.POST or None,
        request.FILES or None,
        instance=lesson,
        course=course,
        allow_material_upload=request.user.granted_permissions.filter(
            permission_key="can_upload_materials"
        ).exists(),
    )
    if request.method == "POST" and form.is_valid():
        changed = tuple(form.changed_data)
        lesson = form.save()
        if changed:
            _record_teacher_activity(
                request.user,
                "lesson.updated",
                f"Updated lesson {lesson.title} in {course.title}.",
            )
            messages.success(request, "Lesson updated.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/lesson_form.html",
        {"form": form, "course": course, "lesson": lesson, "page_title": "Edit lesson"},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_delete_lesson")
@require_POST
def lesson_archive(request, lesson_id):
    _require_teacher(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__teacher=request.user,
        section__course__is_archived=False,
    )
    lesson.is_archived = True
    lesson.save(update_fields=("is_archived", "updated_at"))
    _record_teacher_activity(
        request.user,
        "lesson.archived",
        f"Archived lesson {lesson.title} in {lesson.section.course.title}.",
    )
    messages.success(request, "Lesson archived.")
    return redirect(
        "teacher_workspace:course_detail",
        course_id=lesson.section.course_id,
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_assignments")
def assignment_create(request, lesson_id):
    _require_teacher(request.user)
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__teacher=request.user,
        section__course__is_archived=False,
        is_archived=False,
    )
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.lesson = lesson
        assignment.save()
        _record_teacher_activity(
            request.user,
            "assignment.created",
            f"Created assignment {assignment.title} in {lesson.section.course.title}.",
        )
        messages.success(request, "Assignment created.")
        return redirect(
            "teacher_workspace:course_detail",
            course_id=lesson.section.course_id,
        )
    return render(
        request,
        "teacher_workspace/assignment_form.html",
        {"form": form, "lesson": lesson},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_send_announcements")
def announcement_create(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    form = CourseAnnouncementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.course = course
        announcement.teacher = request.user
        announcement.save()
        _record_teacher_activity(
            request.user,
            "announcement.created",
            f"Posted course announcement {announcement.title} in {course.title}.",
        )
        messages.success(request, "Course announcement posted.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/announcement_form.html",
        {"form": form, "course": course},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_view_students")
def course_students(request, course_id):
    _require_teacher(request.user)
    course = _managed_course(request.user, course_id)
    enrollments = (
        CourseEnrollment.objects.filter(
            course=course,
            payment__status=PaymentTransaction.Status.SUCCESSFUL,
            payment__course_id=course.pk,
            payment__user_id=F("student_id"),
        )
        .select_related("student")
    )
    can_view_progress = request.user.granted_permissions.filter(
        permission_key="can_view_student_progress"
    ).exists()
    if can_view_progress:
        enrollments = enrollments.annotate(
            lessons_completed=Count(
                "lesson_progress",
                filter=Q(lesson_progress__lesson__is_archived=False),
                distinct=True,
            ),
            lessons_total=Count(
                "course__sections__lessons",
                filter=Q(course__sections__lessons__is_archived=False),
                distinct=True,
            ),
        )
        for enrollment in enrollments:
            enrollment.progress_percent = (
                round(100 * enrollment.lessons_completed / enrollment.lessons_total)
                if enrollment.lessons_total
                else 0
            )
    return render(
        request,
        "teacher_workspace/course_students.html",
        {
            "course": course,
            "enrollments": enrollments,
            "can_view_progress": can_view_progress,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_grade_assignments")
def assignment_submissions(request):
    _require_teacher(request.user)
    submissions = (
        AssignmentSubmission.objects.filter(
            assignment__lesson__section__course__teacher=request.user,
            assignment__lesson__section__course__is_archived=False,
        )
        .select_related(
            "student",
            "assignment",
            "assignment__lesson",
            "assignment__lesson__section__course",
        )
    )
    return render(
        request,
        "teacher_workspace/assignment_submissions.html",
        {"submissions": submissions},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_grade_assignments")
def submission_grade(request, submission_id):
    _require_teacher(request.user)
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related(
            "assignment__lesson__section__course",
            "student",
        ),
        pk=submission_id,
        assignment__lesson__section__course__teacher=request.user,
        assignment__lesson__section__course__is_archived=False,
    )
    form = AssignmentGradeForm(
        request.POST or None,
        instance=submission,
        assignment=submission.assignment,
    )
    if request.method == "POST" and form.is_valid():
        graded = form.save(commit=False)
        graded.graded_at = timezone.now()
        graded.save()
        _record_teacher_activity(
            request.user,
            "assignment.graded",
            f"Graded {submission.assignment.title} for {submission.student.full_name}.",
        )
        messages.success(request, "Assignment graded and feedback saved.")
        return redirect("teacher_workspace:assignment_submissions")
    return render(
        request,
        "teacher_workspace/submission_grade.html",
        {"form": form, "submission": submission},
    )


@login_required(login_url="accounts:login")
def private_lesson_material(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
    )
    if request.user.role == request.user.Role.TEACHER:
        _require_teacher(request.user)
        if lesson.is_archived or lesson.section.course.teacher_id != request.user.pk:
            raise PermissionDenied
    elif request.user.role == request.user.Role.STUDENT:
        if not request.user.is_active:
            raise PermissionDenied("This account is inactive.")
        if not paid_enrollment_for_user(
            course=lesson.section.course,
            user=request.user,
        ):
            raise PermissionDenied("Verified course enrollment is required.")
    else:
        raise PermissionDenied("Course materials are available to their teacher and students.")
    if not lesson.material:
        messages.error(request, "This lesson does not have an uploaded file.")
        return redirect("lessons:lesson_detail", lesson_id=lesson.pk)
    extension = lesson.material.name.lower().rsplit(".", 1)[-1]
    content_type = {
        "pdf": "application/pdf",
        "mp4": "video/mp4",
        "webm": "video/webm",
        "mov": "video/quicktime",
    }.get(extension, "application/octet-stream")
    response = FileResponse(
        lesson.material.open("rb"),
        content_type=content_type,
        as_attachment=False,
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
