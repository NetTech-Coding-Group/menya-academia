from django.urls import path

from . import views

app_name = "messaging"

urlpatterns = [
    path("", views.inbox, name="inbox"),
    path("contact-admin/", views.contact_admin, name="contact_admin"),
    path("start/teacher/<uuid:teacher_id>/", views.start_teacher_conversation, name="start_teacher_conversation"),
    path("<uuid:conversation_id>/", views.conversation_detail, name="conversation_detail"),
    path("<uuid:conversation_id>/send/", views.send_message, name="send_message"),
    path("<uuid:conversation_id>/messages/", views.conversation_messages, name="conversation_messages"),
    path("<uuid:conversation_id>/status/", views.update_support_status, name="update_support_status"),
]
