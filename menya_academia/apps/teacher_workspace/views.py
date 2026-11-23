from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Avg, Count, F, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.activity_logs.models import ActivityLog
from apps.courses.forms import CourseAnnouncementForm, CourseForm
from apps.courses.models import Course
from apps.enrollments.models import CourseEnrollment
from apps.enrollments.services import paid_enrollment_for_user
from apps.examinations.models import Question
from apps.lessons.forms import (
    AssignmentForm,
    AssignmentGradeForm,
    CourseSectionForm,
    LessonForm,
)
from apps.lessons.models import AssignmentSubmission, Lesson
from apps.payments.models import PaymentTransaction
from apps.permissions.decorators import teacher_permission_required
from apps.permissions.models import TeacherPermission
from apps.provisual.models import Exam
from apps.teachers.models import TeacherProfile

from .forms import (
    AttendanceRecordForm,
    KinyarwandaQuestionForm,
    StudentMarkForm,
    TeacherExamForm,
    TrafficQuestionForm,
    enrolled_student_queryset,
)
from .models import AttendanceRecord, StudentMark


PERMISSION_GROUPS = (
    ("Courses", ("can_create_course", "can_edit_course", "can_delete_course", "can_publish_course")),
    ("Lessons & materials", ("can_create_lesson", "can_edit_lesson", "can_delete_lesson", "can_upload_materials")),
    ("Students", ("can_view_students", "can_manage_students", "can_view_student_progress")),
    ("Exams", ("can_create_exams", "can_edit_exams", "can_delete_exams", "can_grade_exams")),
    ("Assignments", ("can_create_assignments", "can_grade_assignments", "can_create_quizzes")),
    ("Communication", ("can_send_messages", "can_send_announcements")),
    ("Attendance & marks", ("can_record_attendance", "can_enter_marks", "can_monitor_performance")),
    ("Reports", ("can_view_reports", "can_download_reports")),
)


def _teacher_profile(user):
    try:
        return user.teacher_profile
    except TeacherProfile.DoesNotExist:
        return None


def _require_teacher(user):
    if not user.is_authenticated or not user.is_active or user.role != user.Role.TEACHER:
        raise PermissionDenied("This page is available to active teachers.")
    profile = _teacher_profile(user)
    if not profile or not profile.is_verified_teacher:
        raise PermissionDenied("A teacher account must be approved and assigned by an administrator.")


def _granted_keys(user):
    return set(
        TeacherPermission.objects.filter(teacher=user).values_list("permission_key", flat=True)
    )


def _accessible_courses(user):
    _require_teacher(user)
    profile = _teacher_profile(user)
    assigned_ids = (
        profile.assigned_classes.filter(is_archived=False).values_list("id", flat=True)
        if profile
        else []
    )
    return Course.objects.filter(is_archived=False).filter(
        Q(teacher=user) | Q(id__in=assigned_ids)
    ).distinct()


def _accessible_course(user, course_id):
    return get_object_or_404(
        _accessible_courses(user).prefetch_related("sections__lessons"),
        pk=course_id,
    )


def _course_enrollments(course):
    return (
        CourseEnrollment.objects.filter(
            course=course,
            payment__status=PaymentTransaction.Status.SUCCESSFUL,
            payment__course_id=course.pk,
            payment__user_id=F("student_id"),
        )
        .select_related("student")
        .order_by("student__full_name")
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
    profile = _teacher_profile(request.user)
    granted = _granted_keys(request.user)
    labels = dict(TeacherPermission.PERMISSION_KEYS)
    courses = _accessible_courses(request.user).order_by("-updated_at")
    visible_permissions = [
        (title, [(key, labels.get(key, key), key in granted) for key in keys if key in labels])
        for title, keys in PERMISSION_GROUPS
    ]
    quick_actions = []
    if "can_record_attendance" in granted and courses.exists():
        quick_actions.append(
            {"label": "Record attendance", "url_name": "teacher_workspace:attendance_select", "description": "Mark student attendance for your assigned classes."}
        )
    if "can_enter_marks" in granted and courses.exists():
        quick_actions.append(
            {"label": "Enter marks", "url_name": "teacher_workspace:marks_select", "description": "Record and update student marks."}
        )
    if "can_monitor_performance" in granted and courses.exists():
        quick_actions.append(
            {"label": "Monitor performance", "url_name": "teacher_workspace:performance_select", "description": "Review attendance, marks, and learning progress."}
        )
    if "can_grade_assignments" in granted:
        quick_actions.append(
            {"label": "Grade assignments", "url_name": "teacher_workspace:assignment_submissions", "description": "Review and grade submitted assignments."}
        )
    if "can_create_course" in granted:
        quick_actions.append(
            {"label": "Create course", "url_name": "teacher_workspace:course_create", "description": "Create and prepare a new class/course."}
        )
    pending_submissions = AssignmentSubmission.objects.filter(
        assignment__lesson__section__course__in=courses,
        graded_at__isnull=True,
    ).count() if "can_grade_assignments" in granted else 0
    is_academic = bool(profile and profile.is_academic_teacher)
    is_traffic = bool(profile and profile.is_traffic_rules_teacher)
    return render(
        request,
        "teacher_workspace/dashboard.html",
        {
            "profile": profile,
            "courses": courses,
            "course_count": courses.count(),
            "permission_groups": visible_permissions,
            "granted_count": len(granted),
            "granted_keys": granted,
            "quick_actions": quick_actions,
            "pending_submissions": pending_submissions,
            "is_academic_teacher": is_academic,
            "is_traffic_rules_teacher": is_traffic,
            "can_create_course": "can_create_course" in granted,
            "can_view_students": "can_view_students" in granted,
            "can_create_assignments": "can_create_assignments" in granted,
            "can_grade_assignments": "can_grade_assignments" in granted,
            "can_send_announcements": "can_send_announcements" in granted,
            "can_record_attendance": "can_record_attendance" in granted,
            "can_enter_marks": "can_enter_marks" in granted,
            "can_monitor_performance": "can_monitor_performance" in granted,
            "can_create_exams": "can_create_exams" in granted,
        },
    )


@login_required(login_url="accounts:login")
def permissions(request):
    _require_teacher(request.user)
    granted = _granted_keys(request.user)
    permission_labels = dict(TeacherPermission.PERMISSION_KEYS)
    permission_groups = [
        {
            "title": title,
            "permissions": [
                (key, permission_labels.get(key, key), key in granted)
                for key in keys
                if key in permission_labels
            ],
        }
        for title, keys in PERMISSION_GROUPS
    ]
    return render(
        request,
        "teacher_workspace/permissions.html",
        {"permission_groups": permission_groups, "granted_count": len(granted)},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_course")
def course_create(request):
    form = CourseForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        course = form.save(commit=False)
        course.teacher = request.user
        course.save()
        profile = _teacher_profile(request.user)
        if profile:
            profile.assigned_classes.add(course)
        _record_teacher_activity(request.user, "course.created", f"Created course {course.title}.")
        messages.success(request, "Course created. Add sections and lessons before publishing.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/course_form.html", {"form": form, "page_title": "Create a course"})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_edit_course")
def course_edit(request, course_id):
    course = _accessible_course(request.user, course_id)
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
    return render(request, "teacher_workspace/course_form.html", {"form": form, "course": course, "page_title": "Edit course"})


@login_required(login_url="accounts:login")
def course_detail(request, course_id):
    _require_teacher(request.user)
    course = _accessible_course(request.user, course_id)
    granted = _granted_keys(request.user)
    can_view_students = "can_view_students" in granted
    student_count = _course_enrollments(course).count() if can_view_students else None
    return render(
        request,
        "teacher_workspace/course_detail.html",
        {
            "course": course,
            "sections": course.sections.all().annotate(
                active_lesson_count=Count("lessons", filter=Q(lessons__is_archived=False))
            ),
            "student_count": student_count,
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
            "can_record_attendance": "can_record_attendance" in granted,
            "can_enter_marks": "can_enter_marks" in granted,
            "can_monitor_performance": "can_monitor_performance" in granted,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_publish_course")
@require_POST
def course_publish(request, course_id):
    course = _accessible_course(request.user, course_id)
    if not course.is_published and not course.sections.filter(lessons__is_archived=False).exists():
        messages.error(request, "Add at least one active lesson before publishing.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    course.is_published = not course.is_published
    course.save(update_fields=("is_published", "updated_at"))
    state = "published" if course.is_published else "unpublished"
    _record_teacher_activity(request.user, f"course.{state}", f"{state.title()} course {course.title}.")
    messages.success(request, f"Course {state}.")
    return redirect("teacher_workspace:course_detail", course_id=course.pk)


@login_required(login_url="accounts:login")
@teacher_permission_required("can_delete_course")
@require_POST
def course_archive(request, course_id):
    course = _accessible_course(request.user, course_id)
    course.is_archived = True
    course.is_published = False
    course.save(update_fields=("is_archived", "is_published", "updated_at"))
    _record_teacher_activity(request.user, "course.archived", f"Archived course {course.title}.")
    messages.success(request, "Course archived. Existing enrolled students retain access.")
    return redirect("teacher_workspace:workspace")


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_lesson")
def section_create(request, course_id):
    course = _accessible_course(request.user, course_id)
    form = CourseSectionForm(request.POST or None, course=course)
    if request.method == "POST" and form.is_valid():
        section = form.save(commit=False)
        section.course = course
        section.save()
        _record_teacher_activity(request.user, "section.created", f"Created section {section.title} in {course.title}.")
        messages.success(request, "Course section created.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/section_form.html", {"form": form, "course": course})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_lesson")
def lesson_create(request, course_id):
    course = _accessible_course(request.user, course_id)
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
        _record_teacher_activity(request.user, "lesson.created", f"Created lesson {lesson.title} in {course.title}.")
        messages.success(request, "Lesson added.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/lesson_form.html", {"form": form, "course": course, "page_title": "Add lesson"})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_edit_lesson")
def lesson_edit(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__is_archived=False,
    )
    course = _accessible_course(request.user, lesson.section.course_id)
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
            _record_teacher_activity(request.user, "lesson.updated", f"Updated lesson {lesson.title} in {course.title}.")
            messages.success(request, "Lesson updated.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/lesson_form.html", {"form": form, "course": course, "lesson": lesson, "page_title": "Edit lesson"})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_delete_lesson")
@require_POST
def lesson_archive(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__is_archived=False,
    )
    course = _accessible_course(request.user, lesson.section.course_id)
    lesson.is_archived = True
    lesson.save(update_fields=("is_archived", "updated_at"))
    _record_teacher_activity(request.user, "lesson.archived", f"Archived lesson {lesson.title} in {course.title}.")
    messages.success(request, "Lesson archived.")
    return redirect("teacher_workspace:course_detail", course_id=course.pk)


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_assignments")
def assignment_create(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
        section__course__is_archived=False,
        is_archived=False,
    )
    course = _accessible_course(request.user, lesson.section.course_id)
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.lesson = lesson
        assignment.save()
        _record_teacher_activity(request.user, "assignment.created", f"Created assignment {assignment.title} in {course.title}.")
        messages.success(request, "Assignment created.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/assignment_form.html", {"form": form, "lesson": lesson})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_send_announcements")
def announcement_create(request, course_id):
    course = _accessible_course(request.user, course_id)
    form = CourseAnnouncementForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        announcement = form.save(commit=False)
        announcement.course = course
        announcement.teacher = request.user
        announcement.save()
        _record_teacher_activity(request.user, "announcement.created", f"Posted course announcement {announcement.title} in {course.title}.")
        messages.success(request, "Course announcement posted.")
        return redirect("teacher_workspace:course_detail", course_id=course.pk)
    return render(request, "teacher_workspace/announcement_form.html", {"form": form, "course": course})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_view_students")
def course_students(request, course_id):
    course = _accessible_course(request.user, course_id)
    enrollments = _course_enrollments(course)
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
        {"course": course, "enrollments": enrollments, "can_view_progress": can_view_progress},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_grade_assignments")
def assignment_submissions(request):
    _require_teacher(request.user)
    courses = _accessible_courses(request.user)
    submissions = (
        AssignmentSubmission.objects.filter(
            assignment__lesson__section__course__in=courses,
            assignment__lesson__section__course__is_archived=False,
        )
        .select_related(
            "student",
            "assignment",
            "assignment__lesson",
            "assignment__lesson__section__course",
        )
        .order_by("-submitted_at")
    )
    return render(request, "teacher_workspace/assignment_submissions.html", {"submissions": submissions})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_grade_assignments")
def submission_grade(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related(
            "assignment__lesson__section__course",
            "student",
        ),
        pk=submission_id,
        assignment__lesson__section__course__is_archived=False,
    )
    _accessible_course(request.user, submission.assignment.lesson.section.course_id)
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
    return render(request, "teacher_workspace/submission_grade.html", {"form": form, "submission": submission})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_record_attendance")
def attendance_select(request):
    courses = _accessible_courses(request.user)
    return render(request, "teacher_workspace/attendance_select.html", {"courses": courses})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_record_attendance")
def attendance_manage(request, course_id):
    course = _accessible_course(request.user, course_id)
    records = AttendanceRecord.objects.filter(course=course).select_related("student", "marked_by")[:100]
    selected_date = request.GET.get("date") or timezone.localdate().isoformat()
    initial = {"date": selected_date}
    form = AttendanceRecordForm(request.POST or None, course=course, initial=initial)
    if request.method == "POST" and form.is_valid():
        record = form.save(commit=False)
        record.course = course
        record.marked_by = request.user
        record.save()
        _record_teacher_activity(
            request.user,
            "attendance.recorded",
            f"Recorded {record.get_status_display()} attendance for {record.student.full_name} in {course.title} on {record.date}.",
        )
        messages.success(request, "Attendance recorded.")
        return redirect(f"{request.path}?date={record.date.isoformat()}")
    students = enrolled_student_queryset(course)
    return render(
        request,
        "teacher_workspace/attendance_manage.html",
        {
            "course": course,
            "form": form,
            "records": records,
            "students": students,
            "selected_date": selected_date,
            "status_choices": AttendanceRecord.Status.choices,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_enter_marks")
def marks_select(request):
    courses = _accessible_courses(request.user)
    return render(request, "teacher_workspace/marks_select.html", {"courses": courses})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_enter_marks")
def marks_manage(request, course_id):
    course = _accessible_course(request.user, course_id)
    marks = StudentMark.objects.filter(course=course).select_related("student", "recorded_by")[:100]
    form = StudentMarkForm(request.POST or None, course=course)
    if request.method == "POST" and form.is_valid():
        mark = form.save(commit=False)
        mark.course = course
        mark.recorded_by = request.user
        mark.save()
        _record_teacher_activity(
            request.user,
            "mark.recorded",
            f"Recorded marks for {mark.student.full_name} in {course.title} ({mark.assessment_name}: {mark.score}/{mark.max_score}).",
        )
        messages.success(request, "Mark saved.")
        return redirect("teacher_workspace:marks_manage", course_id=course.pk)
    return render(
        request,
        "teacher_workspace/marks_manage.html",
        {"course": course, "form": form, "marks": marks, "students": enrolled_student_queryset(course)},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_enter_marks")
def mark_edit(request, mark_id):
    mark = get_object_or_404(StudentMark.objects.select_related("course", "student"), pk=mark_id)
    course = _accessible_course(request.user, mark.course_id)
    form = StudentMarkForm(request.POST or None, instance=mark, course=course)
    if request.method == "POST" and form.is_valid():
        updated = form.save(commit=False)
        updated.recorded_by = request.user
        updated.save()
        _record_teacher_activity(
            request.user,
            "mark.updated",
            f"Updated marks for {updated.student.full_name} in {course.title} ({updated.assessment_name}).",
        )
        messages.success(request, "Mark updated.")
        return redirect("teacher_workspace:marks_manage", course_id=course.pk)
    return render(request, "teacher_workspace/mark_form.html", {"form": form, "course": course, "mark": mark})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_monitor_performance")
def performance_select(request):
    courses = _accessible_courses(request.user)
    return render(request, "teacher_workspace/performance_select.html", {"courses": courses})


@login_required(login_url="accounts:login")
@teacher_permission_required("can_monitor_performance")
def performance_course(request, course_id):
    course = _accessible_course(request.user, course_id)
    enrollments = _course_enrollments(course).annotate(
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
        marks_qs = StudentMark.objects.filter(course=course, student=enrollment.student)
        avg = marks_qs.aggregate(avg=Avg("score"))
        enrollment.mark_count = marks_qs.count()
        enrollment.average_score = round(avg["avg"], 2) if avg["avg"] is not None else None
        attendance_qs = AttendanceRecord.objects.filter(course=course, student=enrollment.student)
        enrollment.attendance_total = attendance_qs.count()
        enrollment.attendance_present = attendance_qs.filter(
            status__in=[AttendanceRecord.Status.PRESENT, AttendanceRecord.Status.LATE]
        ).count()
        enrollment.attendance_rate = (
            round(100 * enrollment.attendance_present / enrollment.attendance_total)
            if enrollment.attendance_total
            else None
        )
    recent_marks = StudentMark.objects.filter(course=course).select_related("student")[:10]
    recent_attendance = AttendanceRecord.objects.filter(course=course).select_related("student")[:10]
    return render(
        request,
        "teacher_workspace/performance_course.html",
        {
            "course": course,
            "enrollments": enrollments,
            "recent_marks": recent_marks,
            "recent_attendance": recent_attendance,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_exams")
def exam_create(request):
    profile = _teacher_profile(request.user)
    if request.user.role == request.user.Role.TEACHER and not (
        profile and profile.is_traffic_rules_teacher
    ):
        raise PermissionDenied("Only Traffic Rules Teachers can create traffic-rule exams.")

    form = TeacherExamForm(request.POST or None)
    form.submit_action = "submit" if request.POST.get("action") == "submit" else "draft"
    if request.method == "POST" and form.is_valid():
        exam = form.save(commit=False)
        exam.teacher = request.user
        exam.status = (
            Exam.Status.PENDING_APPROVAL
            if form.submit_action == "submit"
            else Exam.Status.DRAFT
        )
        exam.is_active = False
        exam.slug = ""
        exam.save()
        form.save_m2m()
        exam.question_count = exam.selected_questions.count() or exam.question_count
        exam.save(update_fields=["question_count"])
        _record_teacher_activity(
            request.user,
            "exam.created",
            f"{'Submitted' if exam.status == Exam.Status.PENDING_APPROVAL else 'Saved draft'} exam {exam.title}.",
        )
        if exam.status == Exam.Status.PENDING_APPROVAL:
            messages.success(request, "Exam submitted for administrator approval.")
        else:
            messages.success(request, "Exam draft saved.")
        return redirect("teacher_workspace:workspace")

    teacher_exams = Exam.objects.filter(teacher=request.user).order_by("-updated_at", "-id")
    return render(
        request,
        "teacher_workspace/add_exam.html",
        {
            "form": form,
            "page_title": "Create Exam",
            "teacher_exams": teacher_exams,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_exams")
def question_bank(request):
    profile = _teacher_profile(request.user)
    if request.user.role == request.user.Role.TEACHER and not (
        profile and profile.is_traffic_rules_teacher
    ):
        raise PermissionDenied("Only Traffic Rules Teachers can manage traffic-rule questions.")
    questions = Question.objects.prefetch_related("options").order_by("-id")
    return render(
        request,
        "teacher_workspace/question_bank.html",
        {"questions": questions},
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_exams")
def question_create(request):
    profile = _teacher_profile(request.user)
    if request.user.role == request.user.Role.TEACHER and not (
        profile and profile.is_traffic_rules_teacher
    ):
        raise PermissionDenied("Only Traffic Rules Teachers can create traffic-rule questions.")

    total = 20
    prefixes = [f"q{i}" for i in range(1, total + 1)]
    if request.method == "POST":
        forms = [
            KinyarwandaQuestionForm(request.POST, request.FILES, prefix=prefix)
            for prefix in prefixes
        ]
        # Validate all forms; do not save any if any is invalid.
        all_valid = all(form.is_valid() for form in forms)
        completed = sum(1 for form in forms if form.is_valid())
        if all_valid:
            try:
                with transaction.atomic():
                    created = []
                    for form in forms:
                        question = form.save(
                            commit=False,
                            approval_status=Question.ApprovalStatus.PENDING_APPROVAL,
                        )
                        question.is_active = False
                        question.save()
                        form.save_options(question)
                        created.append(question)
            except Exception:
                messages.error(
                    request,
                    "Habaye ikibazo mu kubika ibibazo. Ongera ugerageze.",
                )
            else:
                _record_teacher_activity(
                    request.user,
                    "questions.bulk_created",
                    f"Submitted {len(created)} PROVISUAL questions for administrator review.",
                )
                messages.success(
                    request,
                    f"Ibibazo {len(created)} byoherejwe gusuzumwa na administrator.",
                )
                return redirect("teacher_workspace:question_bank")
        else:
            messages.error(
                request,
                "Uzuza ibibazo byose 20 mbere yo kohereza. Reba amakosa ari hasi.",
            )
    else:
        forms = [KinyarwandaQuestionForm(prefix=prefix) for prefix in prefixes]
        completed = 0

    return render(
        request,
        "teacher_workspace/provisional_question_bulk_create.html",
        {
            "forms": forms,
            "page_title": "Create PROVISUAL Questions",
            "total_questions": total,
            "completed_questions": completed,
        },
    )


@login_required(login_url="accounts:login")
@teacher_permission_required("can_create_exams")
def question_edit(request, question_id):
    profile = _teacher_profile(request.user)
    if request.user.role == request.user.Role.TEACHER and not (
        profile and profile.is_traffic_rules_teacher
    ):
        raise PermissionDenied("Only Traffic Rules Teachers can edit traffic-rule questions.")
    question = get_object_or_404(Question, pk=question_id)
    form = TrafficQuestionForm(request.POST or None, request.FILES or None, instance=question)
    if request.method == "POST" and form.is_valid():
        question = form.save()
        _record_teacher_activity(
            request.user,
            "question.updated",
            f"Updated traffic-rule question #{question.pk}.",
        )
        messages.success(request, "Question updated.")
        return redirect("teacher_workspace:question_bank")
    return render(
        request,
        "teacher_workspace/question_form.html",
        {"form": form, "page_title": "Edit Question", "question": question},
    )


@login_required(login_url="accounts:login")
def private_lesson_material(request, lesson_id):
    lesson = get_object_or_404(
        Lesson.objects.select_related("section__course"),
        pk=lesson_id,
    )
    if request.user.role == request.user.Role.TEACHER:
        _require_teacher(request.user)
        if lesson.is_archived:
            raise PermissionDenied
        # Allow owner or assigned teacher with access to the class.
        if lesson.section.course not in _accessible_courses(request.user):
            raise PermissionDenied
    elif request.user.role == request.user.Role.STUDENT:
        if not request.user.is_active:
            raise PermissionDenied("This account is inactive.")
        if not paid_enrollment_for_user(course=lesson.section.course, user=request.user):
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
    response = FileResponse(lesson.material.open("rb"), content_type=content_type, as_attachment=False)
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response
