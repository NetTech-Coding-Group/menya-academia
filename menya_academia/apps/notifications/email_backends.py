import json
import logging
import os
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Send email via Resend HTTP API instead of SMTP.

    Configure with:
      EMAIL_BACKEND=apps.notifications.email_backends.ResendEmailBackend
      RESEND_API_KEY=...
      DEFAULT_FROM_EMAIL=...
    """

    api_url = "https://api.resend.com/emails"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = os.environ.get("RESEND_API_KEY", "").strip()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            msg = "RESEND_API_KEY is not configured; cannot send email via Resend."
            if self.fail_silently:
                logger.warning(msg)
                return 0
            raise RuntimeError(msg)

        sent = 0
        for message in email_messages:
            try:
                payload = self._build_payload(message)
                body = json.dumps(payload).encode("utf-8")
                req = urlrequest.Request(
                    self.api_url,
                    data=body,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    method="POST",
                )
                with urlrequest.urlopen(req, timeout=15) as response:
                    status = getattr(response, "status", 200)
                    if status >= 400:
                        raise RuntimeError(f"Resend API returned status {status}.")
                sent += 1
            except (HTTPError, URLError, RuntimeError, ValueError) as exc:
                logger.exception("Resend email delivery failed for %s", message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _build_payload(self, message):
        from_email = message.from_email or os.environ.get("DEFAULT_FROM_EMAIL", "")
        payload = {
            "from": from_email,
            "to": list(message.to),
            "subject": message.subject or "",
        }
        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if getattr(message, "reply_to", None):
            payload["reply_to"] = list(message.reply_to)

        text_body = message.body or ""
        html_body = None
        # Django EmailMultiAlternatives
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_body = content
                break

        if html_body:
            payload["html"] = html_body
            if text_body:
                payload["text"] = text_body
        else:
            payload["text"] = text_body or " "
        return payload


class BrevoEmailBackend(BaseEmailBackend):
    """Send email via Brevo (Sendinblue) HTTP API.

    Configure with:
      EMAIL_BACKEND=apps.notifications.email_backends.BrevoEmailBackend
      BREVO_API_KEY=...
      DEFAULT_FROM_EMAIL=...
    """

    api_url = "https://api.brevo.com/v3/smtp/email"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = os.environ.get("BREVO_API_KEY", "").strip()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            msg = "BREVO_API_KEY is not configured; cannot send email via Brevo."
            if self.fail_silently:
                logger.warning(msg)
                return 0
            raise RuntimeError(msg)

        sent = 0
        for message in email_messages:
            try:
                payload = self._build_payload(message)
                body = json.dumps(payload).encode("utf-8")
                req = urlrequest.Request(
                    self.api_url,
                    data=body,
                    headers={
                        "api-key": self.api_key,
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                    },
                    method="POST",
                )
                with urlrequest.urlopen(req, timeout=15) as response:
                    status = getattr(response, "status", 200)
                    if status >= 400:
                        raise RuntimeError(f"Brevo API returned status {status}.")
                sent += 1
            except (HTTPError, URLError, RuntimeError, ValueError) as exc:
                logger.exception("Brevo email delivery failed for %s", message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _build_payload(self, message):
        from_email = message.from_email or os.environ.get("DEFAULT_FROM_EMAIL", "")
        sender_name = os.environ.get("DEFAULT_FROM_NAME", "MENYA ACADEMIA").strip() or "MENYA ACADEMIA"
        payload = {
            "sender": {"email": from_email, "name": sender_name},
            "to": [{"email": addr} for addr in message.to],
            "subject": message.subject or "",
        }
        if message.cc:
            payload["cc"] = [{"email": addr} for addr in message.cc]
        if message.bcc:
            payload["bcc"] = [{"email": addr} for addr in message.bcc]
        if getattr(message, "reply_to", None):
            payload["replyTo"] = {"email": message.reply_to[0]}

        text_body = message.body or ""
        html_body = None
        for content, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                html_body = content
                break
        if html_body:
            payload["htmlContent"] = html_body
        if text_body:
            payload["textContent"] = text_body
        if not html_body and not text_body:
            payload["textContent"] = " "
        return payload
