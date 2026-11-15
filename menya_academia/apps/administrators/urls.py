from django.urls import path

from . import views


app_name = "administrators"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("users/", views.user_list, name="user_list"),
    path("users/<uuid:user_id>/", views.user_detail, name="user_detail"),
    path("users/<uuid:user_id>/edit/", views.user_edit, name="user_edit"),
    path("users/<uuid:user_id>/status/", views.user_status, name="user_status"),
    path("users/<uuid:user_id>/delete/", views.user_delete, name="user_delete"),
    path("users/<uuid:user_id>/password-reset/", views.user_password_reset, name="user_password_reset"),
    path("teacher-permissions/", views.teacher_permissions, name="teacher_permissions"),
    path(
        "teacher-applications/",
        views.teacher_application_list,
        name="teacher_application_list",
    ),
    path(
        "teacher-applications/<int:application_id>/",
        views.teacher_application_detail,
        name="teacher_application_detail",
    ),
    path(
        "teacher-applications/<int:application_id>/approve/",
        views.teacher_application_approve,
        name="teacher_application_approve",
    ),
    path(
        "teacher-applications/<int:application_id>/reject/",
        views.teacher_application_reject,
        name="teacher_application_reject",
    ),
    path(
        "teacher-applications/<int:application_id>/suspend/",
        views.teacher_application_suspend,
        name="teacher_application_suspend",
    ),
    path(
        "teacher-applications/<int:application_id>/photo/",
        views.teacher_application_photo,
        name="teacher_application_photo",
    ),
    path(
        "teacher-documents/<int:document_id>/",
        views.teacher_application_document,
        name="teacher_application_document",
    ),
    path("activity-logs/", views.activity_logs, name="activity_logs"),
]
