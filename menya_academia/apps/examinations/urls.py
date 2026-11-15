from django.urls import path

from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("provisual/start/", views.activate, name="activate_code"),
    path("provisual/community-results/", views.community_results, name="community_results"),
    path("exams/<uuid:attempt_id>/", views.take_exam, name="exam_take"),
    path("exams/<uuid:attempt_id>/answer/", views.save_exam_answer, name="exam_save_answer"),
    path("exams/<uuid:attempt_id>/submit/", views.submit_exam, name="exam_submit"),
    path("exams/<uuid:attempt_id>/results/", views.exam_results, name="exam_results"),
    path("exams/<uuid:attempt_id>/review/", views.exam_review, name="exam_review"),
]
