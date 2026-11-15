from django.urls import path

from . import views


app_name = "teachers"

urlpatterns = [
    path("become-a-teacher/", views.register_teacher, name="register"),
    path(
        "application-status/",
        views.application_status,
        name="application_status",
    ),
]
