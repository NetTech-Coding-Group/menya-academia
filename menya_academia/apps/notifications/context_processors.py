from .models import Notification


def messaging_notifications(request):
    unread_notifications = 0
    unread_messages = 0
    if request.user.is_authenticated:
        unread_notifications = Notification.objects.filter(recipient=request.user, is_read=False).count()
        try:
            from apps.messaging.services import unread_message_count

            unread_messages = unread_message_count(request.user)
        except Exception:
            unread_messages = 0
    return {
        "unread_notification_count": unread_notifications,
        "unread_message_count": unread_messages,
    }
