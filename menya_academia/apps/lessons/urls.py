from django.urls import path

from . import views


app_name = "lessons"

urlpatterns = [
    path("<uuid:lesson_id>/", views.lesson_detail, name="lesson_detail"),
    path(
        "assignments/<uuid:assignment_id>/submit/",
        views.assignment_submit,
        name="assignment_submit",
    ),
]
