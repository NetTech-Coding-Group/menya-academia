import io
import json
from socket import timeout as SocketTimeout
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from django.test import SimpleTestCase, TestCase, override_settings

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