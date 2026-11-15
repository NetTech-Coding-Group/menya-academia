from django.urls import path

from . import views


app_name = "enrollments"

urlpatterns = [
    path("my-courses/", views.my_courses, name="my_courses"),
    path("learn/<uuid:enrollment_id>/", views.course_learning, name="course_learning"),
    path(
        "learn/<uuid:enrollment_id>/lessons/<uuid:lesson_id>/complete/",
        views.mark_lesson_complete,
        name="mark_lesson_complete",
    ),
]
