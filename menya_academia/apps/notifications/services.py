import json
import logging
import os
from urllib import request as urlrequest
from urllib.error import URLError

from django.conf import settings


logger = logging.getLogger(__name__)


class SmsDeliveryError(Exception):
    pass


def send_sms(*, phone_number, message):
    """Send an SMS to a phone number.

    If an HTTP SMS gateway is configured (SMS_PROVIDER_URL), a JSON POST is sent.
    Otherwise, in DEBUG the message is printed to the console; in non-debug without
    a gateway the delivery is logged as not configured.
    """
    phone_number = (phone_number or "").strip()
    message = (message or "").strip()
    if not phone_number:
        raise SmsDeliveryError("A phone number is required to send an SMS.")
    if not message:
        raise SmsDeliveryError("An SMS message is required.")

    provider_url = os.environ.get("SMS_PROVIDER_URL", "").strip()
    api_key = os.environ.get("SMS_API_KEY", "").strip()
    sender_id = os.environ.get("SMS_SENDER_ID", "MENYA").strip() or "MENYA"

    if provider_url:
        payload = json.dumps(
            {
                "to": phone_number,
                "message": message,
                "sender": sender_id,
            }
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        req = urlrequest.Request(provider_url, data=payload, headers=headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=10) as response:
                status = getattr(response, "status", 200)
                if status >= 400:
                    raise SmsDeliveryError(f"SMS gateway returned status {status}.")
        except URLError as exc:
            logger.exception("SMS delivery failed for %s", phone_number)
            raise SmsDeliveryError("SMS delivery failed.") from exc
        logger.info("SMS sent to %s", phone_number)
        return True

    text = f"[SMS to {phone_number}] {message}"
    if getattr(settings, "DEBUG", False):
        print(text)
    logger.warning("SMS gateway not configured. Message for %s was not delivered by gateway.", phone_number)
    return False


def send_exam_activation_code(*, payment, activation_code):
    """Send a traffic exam activation code to the payer's phone number by SMS only."""
    message = (
        f"MENYA ACADEMIA: Your traffic exam activation code is {activation_code.code}. "
        "Use this code to start your exam. Do not share it."
    )
    return send_sms(phone_number=payment.phone_number, message=message)
