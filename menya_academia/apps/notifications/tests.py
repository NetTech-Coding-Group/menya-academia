import io
import json
from socket import timeout as SocketTimeout
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.payments.models import PaymentTransaction
from apps.provisual.models import ExamPackage

from .services import SmsDeliveryError, send_exam_activation_code, send_sms


class SendSmsTests(SimpleTestCase):
    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
        DEBUG=False,
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_successful_sms_request_sends_pindo_payload(self, mock_urlopen):
        response = Mock()
        response.status = 201
        response.getcode.return_value = 201
        response.read.return_value = json.dumps(
            {"sms_id": "sms-123", "status": "sent"}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = response

        result = send_sms(phone_number="+250788000001", message="Hello from MENYA")

        self.assertTrue(result)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.pindo.io/v1/sms/")
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.headers.get("Authorization"), "Bearer test-token")
        self.assertEqual(request.headers.get("Content-type"), "application/json")
        self.assertEqual(request.headers.get("Accept"), "*/*")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {
                "to": "+250788000001",
                "text": "Hello from MENYA",
                "sender": "MENYA",
            },
        )

    @override_settings(SMS_PROVIDER_URL="", SMS_API_KEY="", SMS_SENDER_ID="MENYA", DEBUG=False)
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_missing_provider_url_preserves_unconfigured_behavior(self, mock_urlopen):
        with self.assertLogs("apps.notifications.services", level="WARNING") as logs:
            result = send_sms(phone_number="+250788000001", message="Hello")

        self.assertFalse(result)
        mock_urlopen.assert_not_called()
        self.assertTrue(any("SMS gateway not configured" in msg for msg in logs.output))

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_missing_api_key_raises_clear_error(self, mock_urlopen):
        with self.assertLogs("apps.notifications.services", level="ERROR"):
            with self.assertRaises(SmsDeliveryError) as ctx:
                send_sms(phone_number="+250788000001", message="Hello")

        self.assertIn("not configured correctly", str(ctx.exception))
        mock_urlopen.assert_not_called()

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_http_401_returns_authentication_error(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.pindo.io/v1/sms/",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"invalid token"}'),
        )

        with self.assertRaises(SmsDeliveryError) as ctx:
            send_sms(phone_number="+250788000001", message="Hello")

        self.assertIn("authentication failed", str(ctx.exception).lower())

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_http_400_response_is_handled(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.pindo.io/v1/sms/",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"bad request"}'),
        )

        with self.assertRaises(SmsDeliveryError):
            send_sms(phone_number="+250788000001", message="Hello")

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_http_500_response_is_handled(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.pindo.io/v1/sms/",
            code=500,
            msg="Server Error",
            hdrs=None,
            fp=io.BytesIO(b'{"error":"server error"}'),
        )

        with self.assertRaises(SmsDeliveryError) as ctx:
            send_sms(phone_number="+250788000001", message="Hello")

        self.assertIn("unavailable", str(ctx.exception).lower())

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_network_timeout_is_handled(self, mock_urlopen):
        mock_urlopen.side_effect = SocketTimeout("timed out")

        with self.assertRaises(SmsDeliveryError) as ctx:
            send_sms(phone_number="+250788000001", message="Hello")

        self.assertIn("timed out", str(ctx.exception).lower())

    @override_settings(
        SMS_PROVIDER_URL="https://api.pindo.io/v1/sms/",
        SMS_API_KEY="test-token",
        SMS_SENDER_ID="MENYA",
    )
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_connection_error_is_handled(self, mock_urlopen):
        mock_urlopen.side_effect = URLError("connection refused")

        with self.assertRaises(SmsDeliveryError):
            send_sms(phone_number="+250788000001", message="Hello")

    @override_settings(SMS_PROVIDER_URL="", SMS_API_KEY="", SMS_SENDER_ID="MENYA")
    @patch("apps.notifications.services.urlrequest.urlopen")
    def test_invalid_phone_number_is_rejected(self, mock_urlopen):
        with self.assertRaises(SmsDeliveryError) as ctx:
            send_sms(phone_number="invalid-phone", message="Hello")

        self.assertIn("valid phone number", str(ctx.exception).lower())
        mock_urlopen.assert_not_called()


class ExamActivationCodeSmsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="learner@example.com",
            username="learner",
            full_name="Learner One",
            phone_number="+250788000001",
            password="test-password",
            role=User.Role.STUDENT,
        )
        self.package = ExamPackage.objects.create(
            name="Single Examination",
            package_type=ExamPackage.PackageType.SINGLE,
            price_rwf=200,
            duration_days=1,
            max_exam_attempts=1,
            is_active=True,
        )
        self.payment = PaymentTransaction.objects.create(
            package=self.package,
            user=self.user,
            full_name=self.user.full_name,
            phone_number="+250788000001",
            email=self.user.email,
            amount_rwf=200,
            provider=PaymentTransaction.Provider.MTN_MOMO,
        )

    @patch("apps.notifications.services.send_sms")
    def test_send_exam_activation_code_uses_sms_service(self, mock_send_sms):
        class DummyCode:
            code = "ACADEMIA-TEST-CODE"

        mock_send_sms.return_value = True

        result = send_exam_activation_code(payment=self.payment, activation_code=DummyCode())

        self.assertTrue(result)
        mock_send_sms.assert_called_once()
        _, kwargs = mock_send_sms.call_args
        self.assertEqual(kwargs["phone_number"], "+250788000001")
        self.assertIn("ACADEMIA-TEST-CODE", kwargs["message"])


@override_settings(
    EMAIL_BACKEND="apps.notifications.email_backends.BrevoEmailBackend",
    BREVO_API_KEY="test-brevo-key",
    DEFAULT_FROM_EMAIL="nettechcodinggroup@gmail.com",
    DEFAULT_FROM_NAME="MENYA ACADEMIA",
)
class BrevoEmailBackendTests(SimpleTestCase):
    def _mock_response(self, status=201, payload=None):
        response = Mock()
        response.status = status
        response.getcode.return_value = status
        body = {} if payload is None else payload
        response.read.return_value = json.dumps(body).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        return response

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_successful_brevo_api_response(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(201, {"messageId": "<msg@brevo>"})

        message = EmailMessage(
            subject="Hello",
            body="Plain text body",
            from_email="nettechcodinggroup@gmail.com",
            to=["user@example.com"],
        )
        sent = message.send(fail_silently=False)

        self.assertEqual(sent, 1)
        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
        self.assertEqual(request.headers.get("Api-key"), "test-brevo-key")
        self.assertEqual(request.headers.get("Content-type"), "application/json")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["sender"]["email"], "nettechcodinggroup@gmail.com")
        self.assertEqual(payload["sender"]["name"], "MENYA ACADEMIA")
        self.assertEqual(payload["to"], [{"email": "user@example.com"}])
        self.assertEqual(payload["subject"], "Hello")
        self.assertEqual(payload["textContent"], "Plain text body")

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_successful_brevo_api_response_with_html(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(201, {"messageId": "<msg@brevo>"})

        message = EmailMultiAlternatives(
            subject="Reset",
            body="Plain text",
            from_email="nettechcodinggroup@gmail.com",
            to=["user@example.com"],
        )
        message.attach_alternative("<p>HTML</p>", "text/html")
        sent = message.send(fail_silently=False)

        self.assertEqual(sent, 1)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["textContent"], "Plain text")
        self.assertEqual(payload["htmlContent"], "<p>HTML</p>")

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_authentication_failure(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.brevo.com/v3/smtp/email",
            code=401,
            msg="Unauthorized",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"unauthorized"}'),
        )

        message = EmailMessage("Hi", "Body", "nettechcodinggroup@gmail.com", ["user@example.com"])
        with self.assertRaises(RuntimeError):
            message.send(fail_silently=False)

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_invalid_sender(self, mock_urlopen):
        mock_urlopen.side_effect = HTTPError(
            url="https://api.brevo.com/v3/smtp/email",
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(b'{"message":"invalid sender"}'),
        )

        message = EmailMessage("Hi", "Body", "bad-sender", ["user@example.com"])
        with self.assertRaises(RuntimeError):
            message.send(fail_silently=False)

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_network_timeout(self, mock_urlopen):
        mock_urlopen.side_effect = SocketTimeout("timed out")

        message = EmailMessage("Hi", "Body", "nettechcodinggroup@gmail.com", ["user@example.com"])
        with self.assertRaises(RuntimeError) as ctx:
            message.send(fail_silently=False)

        self.assertIn("timed out", str(ctx.exception).lower())

    @override_settings(BREVO_API_KEY="")
    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_missing_api_key(self, mock_urlopen):
        message = EmailMessage("Hi", "Body", "nettechcodinggroup@gmail.com", ["user@example.com"])
        with self.assertRaises(RuntimeError) as ctx:
            message.send(fail_silently=False)

        self.assertIn("BREVO_API_KEY", str(ctx.exception))
        mock_urlopen.assert_not_called()

    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_multiple_recipients(self, mock_urlopen):
        mock_urlopen.return_value = self._mock_response(201, {"messageId": "<msg@brevo>"})

        message = EmailMessage(
            subject="Hi",
            body="Body",
            from_email="nettechcodinggroup@gmail.com",
            to=["a@example.com", "b@example.com"],
            cc=["c@example.com"],
            bcc=["d@example.com"],
        )
        sent = message.send(fail_silently=False)

        self.assertEqual(sent, 1)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["to"], [{"email": "a@example.com"}, {"email": "b@example.com"}])
        self.assertEqual(payload["cc"], [{"email": "c@example.com"}])
        self.assertEqual(payload["bcc"], [{"email": "d@example.com"}])


@override_settings(
    EMAIL_BACKEND="apps.notifications.email_backends.BrevoEmailBackend",
    BREVO_API_KEY="test-brevo-key",
    DEFAULT_FROM_EMAIL="nettechcodinggroup@gmail.com",
    DEFAULT_FROM_NAME="MENYA ACADEMIA",
    SITE_DOMAIN="127.0.0.1:8000",
    SITE_SCHEME="http",
)
class BrevoPasswordResetIntegrationTests(TestCase):
    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_password_reset_email_sent_through_brevo(self, mock_urlopen):
        response = Mock()
        response.status = 201
        response.getcode.return_value = 201
        response.read.return_value = json.dumps({"messageId": "<msg@brevo>"}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = response

        user = User.objects.create_user(
            email="reset@example.com",
            username="resetuser",
            full_name="Reset User",
            phone_number="+250788000099",
            password="test-password",
            role=User.Role.STUDENT,
        )

        resp = self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(mock_urlopen.called)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertEqual(payload["sender"]["email"], "nettechcodinggroup@gmail.com")
        self.assertEqual(payload["to"], [{"email": "reset@example.com"}])
        self.assertIn("textContent", payload)
        self.assertIn("http://127.0.0.1:8000/accounts/reset/", payload["textContent"])

    @override_settings(SITE_DOMAIN="menya-academia.onrender.com", SITE_SCHEME="https")
    @patch("apps.notifications.email_backends.urlrequest.urlopen")
    def test_password_reset_email_uses_configured_production_domain(self, mock_urlopen):
        response = Mock()
        response.status = 201
        response.getcode.return_value = 201
        response.read.return_value = json.dumps({"messageId": "<msg@brevo>"}).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        mock_urlopen.return_value = response

        user = User.objects.create_user(
            email="prod-reset@example.com",
            username="prodresetuser",
            full_name="Prod Reset User",
            phone_number="+250788000098",
            password="test-password",
            role=User.Role.STUDENT,
        )

        resp = self.client.post(reverse("accounts:password_reset"), {"email": user.email})
        self.assertEqual(resp.status_code, 302)
        payload = json.loads(mock_urlopen.call_args.args[0].data.decode("utf-8"))
        self.assertIn("https://menya-academia.onrender.com/accounts/reset/", payload["textContent"])
        self.assertNotIn("example.com", payload["textContent"])

        import re
        from django.urls import resolve

        match = re.search(r"https://menya-academia\.onrender\.com(/accounts/reset/[^\s]+)", payload["textContent"])
        self.assertIsNotNone(match)
        match = resolve(match.group(1))
        self.assertEqual(match.view_name, "accounts:password_reset_confirm")