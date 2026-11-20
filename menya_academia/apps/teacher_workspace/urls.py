from django.urls import path

from . import views


app_name = "teacher_workspace"

urlpatterns = [
    path("", views.workspace, name="workspace"),
    path("permissions/", views.permissions, name="permissions"),
    path("courses/create/", views.course_create, name="course_create"),
    path("courses/<uuid:course_id>/", views.course_detail, name="course_detail"),
    path("courses/<uuid:course_id>/edit/", views.course_edit, name="course_edit"),
    path("courses/<uuid:course_id>/publish/", views.course_publish, name="course_publish"),
    path("courses/<uuid:course_id>/archive/", views.course_archive, name="course_archive"),
    path("courses/<uuid:course_id>/sections/create/", views.section_create, name="section_create"),
    path("courses/<uuid:course_id>/lessons/create/", views.lesson_create, name="lesson_create"),
    path("courses/<uuid:course_id>/students/", views.course_students, name="course_students"),
    path("courses/<uuid:course_id>/announcements/create/", views.announcement_create, name="announcement_create"),
    path("attendance/", views.attendance_select, name="attendance_select"),
    path("attendance/<uuid:course_id>/", views.attendance_manage, name="attendance_manage"),
    path("marks/", views.marks_select, name="marks_select"),
    path("marks/<uuid:course_id>/", views.marks_manage, name="marks_manage"),
    path("marks/record/<uuid:mark_id>/edit/", views.mark_edit, name="mark_edit"),
    path("performance/", views.performance_select, name="performance_select"),
    path("performance/<uuid:course_id>/", views.performance_course, name="performance_course"),
    path("lessons/<uuid:lesson_id>/edit/", views.lesson_edit, name="lesson_edit"),
    path("lessons/<uuid:lesson_id>/archive/", views.lesson_archive, name="lesson_archive"),
    path("lessons/<uuid:lesson_id>/assignments/create/", views.assignment_create, name="assignment_create"),
    path("lessons/<uuid:lesson_id>/material/", views.private_lesson_material, name="private_lesson_material"),
    path("assignment-submissions/", views.assignment_submissions, name="assignment_submissions"),
    path("assignment-submissions/<int:submission_id>/grade/", views.submission_grade, name="submission_grade"),
]
