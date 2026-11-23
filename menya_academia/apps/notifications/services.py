import json
import logging
import os
import re
from socket import timeout as SocketTimeout
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.conf import settings


logger = logging.getLogger(__name__)

PINDO_SMS_ENDPOINT = "https://api.pindo.io/v1/sms/"
PHONE_NUMBER_PATTERN = re.compile(r"^\+?[0-9]{8,15}$")


class SmsDeliveryError(Exception):
    pass


def _sms_setting(name, default=""):
    value = getattr(settings, name, None)
    if value is None:
        value = os.environ.get(name, default)
    return str(value).strip()


def _normalize_phone_number(phone_number):
    normalized = re.sub(r"[\s\-()]+", "", (phone_number or "").strip())
    if not normalized:
        raise SmsDeliveryError("A phone number is required to send an SMS.")
    if not PHONE_NUMBER_PATTERN.match(normalized):
        raise SmsDeliveryError("A valid phone number is required to send an SMS.")
    return normalized


def _safe_json_body(response):
    try:
        body = response.read()
    except Exception:
        return {}
    if not body:
        return {}
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        return {}
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def _response_id_status(payload):
    if not isinstance(payload, dict):
        return None, None
    sms_id = payload.get("sms_id") or payload.get("id") or payload.get("message_id")
    status = payload.get("status")
    data = payload.get("data")
    if isinstance(data, dict):
        sms_id = sms_id or data.get("sms_id") or data.get("id") or data.get("message_id")
        status = status or data.get("status")
    return sms_id, status


def send_sms(*, phone_number, message):
    """Send an SMS using the configured provider (Pindo-compatible).

    When SMS_PROVIDER_URL is not configured, preserve current behavior: print the
    message in DEBUG, log a warning, and return False. Never log API credentials.
    """
    phone_number = _normalize_phone_number(phone_number)
    message = (message or "").strip()
    if not message:
        raise SmsDeliveryError("An SMS message is required.")

    provider_url = _sms_setting("SMS_PROVIDER_URL")
    api_key = _sms_setting("SMS_API_KEY")
    sender_id = _sms_setting("SMS_SENDER_ID", "MENYA") or "MENYA"

    if not provider_url:
        text = f"[SMS to {phone_number}] {message}"
        if getattr(settings, "DEBUG", False):
            print(text)
        logger.warning(
            "SMS gateway not configured. Message for %s was not delivered by gateway.",
            phone_number,
        )
        return False

    if not api_key:
        logger.error("SMS gateway is configured but SMS_API_KEY is missing.")
        raise SmsDeliveryError("SMS gateway is not configured correctly.")

    payload = json.dumps(
        {
            "to": phone_number,
            "text": message,
            "sender": sender_id,
        }
    ).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "*/*",
    }
    req = urlrequest.Request(provider_url, data=payload, headers=headers, method="POST")

    try:
        with urlrequest.urlopen(req, timeout=10) as response:
            status = getattr(response, "status", response.getcode())
            response_payload = _safe_json_body(response)
    except HTTPError as exc:
        status = getattr(exc, "code", None)
        response_payload = _safe_json_body(exc)
        _, provider_status = _response_id_status(response_payload)
        logger.warning(
            "SMS delivery failed for %s (HTTP %s, status=%s).",
            phone_number,
            status,
            provider_status,
        )
        if status == 401:
            raise SmsDeliveryError("SMS authentication failed.") from exc
        if status == 400:
            raise SmsDeliveryError("SMS request was rejected by the provider.") from exc
        if status is not None and status >= 500:
            raise SmsDeliveryError("SMS provider is unavailable.") from exc
        raise SmsDeliveryError(f"SMS delivery failed (HTTP {status}).") from exc
    except (SocketTimeout, TimeoutError) as exc:
        logger.warning("SMS delivery timed out for %s.", phone_number)
        raise SmsDeliveryError("SMS delivery timed out.") from exc
    except URLError as exc:
        logger.warning("SMS delivery failed for %s due to a network error.", phone_number)
        raise SmsDeliveryError("SMS delivery failed.") from exc
    except Exception as exc:
        logger.exception("Unexpected SMS delivery failure for %s.", phone_number)
        raise SmsDeliveryError("SMS delivery failed.") from exc

    if status != 201:
        logger.warning("SMS provider returned unexpected HTTP %s for %s.", status, phone_number)
        raise SmsDeliveryError(f"SMS delivery failed (HTTP {status}).")

    sms_id, provider_status = _response_id_status(response_payload)
    logger.info(
        "SMS submitted to %s (provider_status=%s, sms_id=%s).",
        phone_number,
        provider_status or "unknown",
        sms_id or "unknown",
    )
    return True


def create_notification(*, recipient, actor=None, notification_type="MESSAGE", title, message, url=""):
    from .models import Notification

    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        notification_type=notification_type,
        title=title[:180],
        message=(message or "")[:512],
        url=(url or "")[:500],
    )


def notify_new_message(*, message_obj):
    from apps.messaging.models import Conversation

    conversation = message_obj.conversation
    sender = message_obj.sender
    recipients = []
    if conversation.conversation_type == Conversation.Type.STUDENT_TEACHER:
        if sender.id == conversation.student_id and conversation.teacher_id:
            recipients = [conversation.teacher]
        elif sender.id == conversation.teacher_id:
            recipients = [conversation.student]
    elif conversation.conversation_type == Conversation.Type.STUDENT_ADMIN:
        if sender.role == sender.Role.STUDENT:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            recipients = list(
                User.objects.filter(is_active=True, role=User.Role.ADMIN).exclude(pk=sender.pk)
            )
        else:
            recipients = [conversation.student]

    title = "New message"
    if conversation.conversation_type == Conversation.Type.STUDENT_TEACHER and conversation.course_id:
        title = f"New message: {conversation.course.title}"
    elif conversation.conversation_type == Conversation.Type.STUDENT_ADMIN:
        title = "New support message"

    preview = (message_obj.content or "").strip()
    if len(preview) > 140:
        preview = preview[:137] + "..."

    url = ""
    try:
        from django.urls import reverse

        url = reverse("messaging:conversation_detail", kwargs={"conversation_id": conversation.pk})
    except Exception:
        url = ""

    for recipient in recipients:
        if not recipient or recipient.pk == sender.pk:
            continue
        # Avoid duplicate unread notifications for the same conversation/recipient.
        from .models import Notification

        existing = Notification.objects.filter(
            recipient=recipient,
            notification_type=Notification.Type.MESSAGE,
            url=url,
            is_read=False,
        ).first()
        if existing:
            existing.actor = sender
            existing.title = title[:180]
            existing.message = f"{sender.full_name}: {preview}"[:512]
            existing.created_at = message_obj.created_at
            existing.save(update_fields=["actor", "title", "message", "created_at"])
            continue
        create_notification(
            recipient=recipient,
            actor=sender,
            notification_type=Notification.Type.MESSAGE,
            title=title,
            message=f"{sender.full_name}: {preview}",
            url=url,
        )


def send_exam_activation_code(*, payment, activation_code):
    """Send a traffic exam activation code to the payer's phone number by SMS only."""
    message = (
        f"MENYA ACADEMIA: Your traffic exam activation code is {activation_code.code}. "
        "Use this code to start your exam. Do not share it."
    )
    return send_sms(phone_number=payment.phone_number, message=message)
