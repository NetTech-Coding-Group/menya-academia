import json
import logging
import os
import socket
from email.utils import parseaddr
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from django.conf import settings
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
    """Send email via Brevo transactional HTTP API.

    Configure with:
      EMAIL_BACKEND=apps.notifications.email_backends.BrevoEmailBackend
      BREVO_API_KEY=...
      DEFAULT_FROM_EMAIL=...
      DEFAULT_FROM_NAME=...
    """

    api_url = "https://api.brevo.com/v3/smtp/email"
    timeout = 15

    def __init__(self, fail_silently=False, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = self._setting("BREVO_API_KEY")
        self.default_from_email = self._setting("DEFAULT_FROM_EMAIL")
        self.default_from_name = self._setting("DEFAULT_FROM_NAME", "MENYA ACADEMIA") or "MENYA ACADEMIA"
        if timeout is not None:
            self.timeout = timeout

    @staticmethod
    def _setting(name, default=""):
        value = getattr(settings, name, None)
        if value is None:
            value = os.environ.get(name, default)
        return str(value).strip()

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            msg = "BREVO_API_KEY is not configured; cannot send email via Brevo."
            if self.fail_silently:
                logger.warning(msg)
                return 0
            raise RuntimeError(msg)

        self.open()
        sent = 0
        try:
            for message in email_messages:
                if self._send(message):
                    sent += 1
        finally:
            self.close()
        return sent

    def _send(self, message):
        try:
            payload = self._build_payload(message)
        except ValueError as exc:
            logger.warning("Brevo email payload invalid: %s", exc)
            if self.fail_silently:
                return False
            raise

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

        try:
            with urlrequest.urlopen(req, timeout=self.timeout) as response:
                status = getattr(response, "status", response.getcode())
                if 200 <= int(status) < 300:
                    return True
                logger.warning(
                    "Brevo email delivery returned unexpected HTTP %s for recipients=%s.",
                    status,
                    len(getattr(message, "to", []) or []),
                )
                if not self.fail_silently:
                    raise RuntimeError(f"Brevo API returned status {status}.")
                return False
        except HTTPError as exc:
            status = getattr(exc, "code", "unknown")
            logger.warning(
                "Brevo email delivery failed with HTTP %s for recipients=%s.",
                status,
                len(getattr(message, "to", []) or []),
            )
            if not self.fail_silently:
                raise RuntimeError(f"Brevo API returned status {status}.") from exc
            return False
        except (socket.timeout, TimeoutError) as exc:
            logger.warning(
                "Brevo email delivery timed out for recipients=%s.",
                len(getattr(message, "to", []) or []),
            )
            if not self.fail_silently:
                raise RuntimeError("Brevo email delivery timed out.") from exc
            return False
        except URLError as exc:
            logger.warning(
                "Brevo email delivery failed due to network error for recipients=%s.",
                len(getattr(message, "to", []) or []),
            )
            if not self.fail_silently:
                raise RuntimeError("Brevo email delivery failed.") from exc
            return False
        except Exception as exc:
            logger.exception("Unexpected Brevo email delivery failure.")
            if not self.fail_silently:
                raise
            return False

    def _parse_sender(self, from_email):
        raw = (from_email or self.default_from_email or "").strip()
        name, email = parseaddr(raw)
        if not email:
            if "@" in raw and "<" not in raw:
                email = raw
                name = ""
            else:
                email = raw
        if not email:
            raise ValueError("A sender email address is required.")
        return {
            "email": email,
            "name": (name or self.default_from_name or "MENYA ACADEMIA").strip(),
        }

    @staticmethod
    def _format_recipients(addresses, field_name):
        recipients = []
        for addr in addresses or []:
            _, email = parseaddr(addr)
            email = (email or addr or "").strip()
            if email:
                recipients.append({"email": email})
        if not recipients and field_name == "to":
            raise ValueError("At least one recipient email address is required.")
        return recipients

    def _build_payload(self, message):
        sender = self._parse_sender(getattr(message, "from_email", None))
        payload = {
            "sender": sender,
            "to": self._format_recipients(getattr(message, "to", []), "to"),
            "subject": getattr(message, "subject", "") or "",
        }
        cc = self._format_recipients(getattr(message, "cc", []), "cc")
        bcc = self._format_recipients(getattr(message, "bcc", []), "bcc")
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        reply_to = getattr(message, "reply_to", None) or []
        if reply_to:
            _, reply_email = parseaddr(reply_to[0])
            reply_email = (reply_email or reply_to[0]).strip()
            if reply_email:
                payload["replyTo"] = {"email": reply_email}

        text_body = getattr(message, "body", "") or ""
        html_body = None
        for content, mimetype in getattr(message, "alternatives", []) or []:
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
