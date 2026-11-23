from django.contrib import admin

from .models import Conversation, Message


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation_type", "student", "teacher", "course", "status", "last_message_at", "updated_at")
    list_filter = ("conversation_type", "status", "category")
    search_fields = ("student__email", "student__full_name", "teacher__email", "teacher__full_name", "subject")
    autocomplete_fields = ("student", "teacher", "course")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "sender", "created_at", "is_read")
    list_filter = ("is_read", "created_at")
    search_fields = ("sender__email", "sender__full_name", "content")
    autocomplete_fields = ("conversation", "sender")
