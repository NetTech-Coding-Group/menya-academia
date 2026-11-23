from unittest.mock import Mock, patch

from django.core import signing
from django.core.cache import cache
from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse
from allauth.account.models import EmailAddress

from .models import User


class AdminCsrfLoginTests(TestCase):
    def test_fresh_admin_login_form_has_matching_csrf_cookie_and_token(self):
        client = Client(enforce_csrf_checks=True, HTTP_HOST="127.0.0.1:8000")
        response = client.get("/admin/login/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("menya_csrftoken", client.cookies)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

        csrf_token = response.cookies["menya_csrftoken"].value
        response = client.post(
            "/admin/login/",
            {
                "username": "not-an-account@example.com",
                "password": "invalid-password",
                "csrfmiddlewaretoken": csrf_token,
            },
            HTTP_HOST="127.0.0.1:8000",
            HTTP_REFERER="http://127.0.0.1:8000/admin/login/",
        )

        self.assertNotEqual(response.status_code, 403)


class SignInTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="learner@example.com",
            username="learner",
            full_name="Test Learner",
            phone_number="+250788000000",
            password="Secure-test-password-2026",
            is_email_verified=True,
        )

    def test_sign_in_form_renders_csrf_token_and_picture(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, "images/learning-road.svg")
        self.assertContains(response, "data-password-toggle")
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, "Continue with Facebook")

    @override_settings(
        SOCIAL_LOGIN_GOOGLE_ENABLED=False,
        SOCIAL_LOGIN_FACEBOOK_ENABLED=False,
    )
    def test_social_login_buttons_are_disabled_until_provider_credentials_exist(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'type="button" disabled')
        self.assertContains(response, "provider credentials are configured")

    @override_settings(
        SOCIAL_LOGIN_GOOGLE_ENABLED=True,
        SOCIAL_LOGIN_FACEBOOK_ENABLED=False,
    )
    def test_google_sign_in_does_not_show_setup_notice_when_facebook_is_unconfigured(self):
        response = self.client.get(reverse("accounts:login"))
        self.assertContains(response, 'action="/accounts/google/login/')
        self.assertContains(response, "Continue with Google")
        self.assertNotContains(response, "provider credentials are configured")

    def test_sign_in_session_expires_when_browser_closes_by_default(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.user.email,
                "password": "Secure-test-password-2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.session.get_expiry_age(), 0)

    def test_remember_me_keeps_session(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.user.email,
                "password": "Secure-test-password-2026",
                "remember_me": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertGreater(self.client.session.get_expiry_age(), 0)


class LanguageSelectionTests(TestCase):
    def test_language_switch_keeps_current_page_and_translates_interface(self):
        response = self.client.post(
            reverse("set_language"),
            {"language": "fr", "next": reverse("home")},
        )

        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.cookies["django_language"].value, "fr")
        response = self.client.get(reverse("home"))
        self.assertContains(response, ">Accueil</a>")
        self.assertContains(response, "Développez vos connaissances.")

        response = self.client.post(
            reverse("set_language"),
            {"language": "rw", "next": reverse("home")},
        )
        self.assertRedirects(response, reverse("home"))
        self.assertEqual(self.client.cookies["django_language"].value, "rw")
        response = self.client.get(reverse("home"))
        self.assertContains(response, ">Ahabanza</a>")
        self.assertContains(response, "Ongera ubumenyi.")

    def test_account_language_is_used_when_no_language_cookie_exists(self):
        user = User.objects.create_user(
            email="language@example.com",
            username="language-user",
            full_name="Language User",
            phone_number="+250788000001",
            password="Secure-test-password-2026",
            preferred_language="fr",
        )
        client = Client()
        client.force_login(user)

        response = client.get(reverse("home"))

        self.assertContains(response, ">Accueil</a>")


@override_settings(
    SITE_DOMAIN="menya-academia.onrender.com",
    SITE_SCHEME="https",
    DEFAULT_FROM_EMAIL="nettechcodinggroup@gmail.com",
)
class EmailVerificationTests(TestCase):
    def setUp(self):
        cache.clear()

    def create_user(self, *, email="verify@example.com", verified=False, **kwargs):
        defaults = {
            "username": "verifyuser",
            "full_name": "Verify User",
            "phone_number": "+250788000010",
            "password": "Secure-test-password-2026",
            "role": User.Role.STUDENT,
            "is_email_verified": verified,
        }
        defaults.update(kwargs)
        user = User.objects.create_user(email=email, **defaults)
        EmailAddress.objects.update_or_create(
            user=user,
            email=user.email,
            defaults={"primary": True, "verified": verified},
        )
        return user

    def verification_token(self, user):
        return signing.TimestampSigner(salt="accounts.email-verification").sign(str(user.pk))

    def test_valid_verification_link_marks_correct_account_verified(self):
        user = self.create_user(email="a@example.com", username="auser", verified=False)
        other = self.create_user(email="b@example.com", username="buser", verified=False)

        response = self.client.get(reverse("accounts:verify_email", args=(self.verification_token(user),)))

        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        other.refresh_from_db()
        self.assertTrue(user.is_email_verified)
        self.assertFalse(other.is_email_verified)
        self.assertTrue(EmailAddress.objects.get(user=user, email=user.email).verified)
        self.assertFalse(EmailAddress.objects.get(user=other, email=other.email).verified)

    def test_invalid_verification_token_is_rejected(self):
        user = self.create_user(verified=False)
        response = self.client.get(reverse("accounts:verify_email", args=("invalid-token",)))
        self.assertRedirects(response, reverse("accounts:register"))
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_expired_verification_token_is_rejected(self):
        user = self.create_user(verified=False)
        with patch("django.core.signing.time.time", return_value=1_700_000_000):
            token = self.verification_token(user)
        with patch("django.core.signing.time.time", return_value=1_700_000_000 + 60 * 60 * 25):
            response = self.client.get(reverse("accounts:verify_email", args=(token,)))
        self.assertRedirects(response, reverse("accounts:register"))
        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    def test_already_verified_token_is_harmless(self):
        user = self.create_user(verified=True)
        token = self.verification_token(user)
        response = self.client.get(reverse("accounts:verify_email", args=(token,)))
        self.assertRedirects(response, reverse("accounts:login"))
        user.refresh_from_db()
        self.assertTrue(user.is_email_verified)

    def test_unverified_user_cannot_sign_in(self):
        self.create_user(email="unverified@example.com", username="unverified", verified=False)
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "unverified@example.com", "password": "Secure-test-password-2026"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Verify your email address before signing in")

    def test_verified_user_can_sign_in(self):
        self.create_user(email="verified@example.com", username="verified", verified=True)
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "verified@example.com", "password": "Secure-test-password-2026"},
        )
        self.assertEqual(response.status_code, 302)

    def test_password_reset_does_not_change_email_verification_status(self):
        user = self.create_user(email="resetverify@example.com", username="resetverify", verified=False)
        with patch("apps.notifications.email_backends.urlrequest.urlopen") as mock_urlopen:
            mock_resp = Mock()
            mock_resp.status = 201
            mock_resp.getcode.return_value = 201
            mock_resp.read.return_value = b'{"messageId":"<id>"}'
            mock_resp.__enter__ = Mock(return_value=mock_resp)
            mock_resp.__exit__ = Mock(return_value=False)
            mock_urlopen.return_value = mock_resp
            with override_settings(
                EMAIL_BACKEND="apps.notifications.email_backends.BrevoEmailBackend",
                BREVO_API_KEY="test-key",
            ):
                self.client.post(reverse("accounts:password_reset"), {"email": user.email})

        user.refresh_from_db()
        self.assertFalse(user.is_email_verified)

    @patch("apps.accounts.views.send_mail")
    def test_resend_verification_sends_for_unverified_user(self, mock_send_mail):
        user = self.create_user(email="resend@example.com", username="resend", verified=False)
        response = self.client.post(reverse("accounts:resend_verification"), {"email": user.email})
        self.assertRedirects(response, reverse("accounts:login"))
        mock_send_mail.assert_called_once()
        args = mock_send_mail.call_args.args
        self.assertEqual(args[3], [user.email])
        self.assertIn("https://menya-academia.onrender.com/accounts/verify/", args[1])

    @patch("apps.accounts.views.send_mail")
    def test_resend_verification_does_not_send_for_verified_user(self, mock_send_mail):
        self.create_user(email="already@example.com", username="already", verified=True)
        response = self.client.post(reverse("accounts:resend_verification"), {"email": "already@example.com"})
        self.assertRedirects(response, reverse("accounts:login"))
        mock_send_mail.assert_not_called()

    @patch("apps.accounts.views.send_mail")
    def test_resend_verification_unknown_email_is_generic(self, mock_send_mail):
        response = self.client.post(reverse("accounts:resend_verification"), {"email": "missing@example.com"})
        self.assertRedirects(response, reverse("accounts:login"))
        mock_send_mail.assert_not_called()

    @patch("apps.accounts.views.send_mail")
    def test_register_verification_link_uses_configured_site_domain(self, mock_send_mail):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "full_name": "New User",
                "username": "newuser",
                "email": "new@example.com",
                "phone_number": "+250788000099",
                "preferred_language": "en",
                "password1": "Secure-test-password-2026",
                "password2": "Secure-test-password-2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        mock_send_mail.assert_called_once()
        body = mock_send_mail.call_args.args[1]
        self.assertIn("https://menya-academia.onrender.com/accounts/verify/", body)
        self.assertNotIn("example.com", body)

    @override_settings(
        RESEND_VERIFICATION_EMAIL_LIMIT=2,
        RESEND_VERIFICATION_IP_LIMIT=10,
        RESEND_VERIFICATION_WINDOW_SECONDS=600,
    )
    @patch("apps.accounts.views.send_mail")
    def test_resend_verification_is_rate_limited_per_email(self, mock_send_mail):
        self.create_user(email="limit@example.com", username="limituser", verified=False)
        url = reverse("accounts:resend_verification")

        for _ in range(2):
            response = self.client.post(url, {"email": "limit@example.com"}, REMOTE_ADDR="10.0.0.1")
            self.assertRedirects(response, reverse("accounts:login"))

        response = self.client.post(url, {"email": "limit@example.com"}, REMOTE_ADDR="10.0.0.1")
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(mock_send_mail.call_count, 2)

    @override_settings(
        RESEND_VERIFICATION_EMAIL_LIMIT=10,
        RESEND_VERIFICATION_IP_LIMIT=2,
        RESEND_VERIFICATION_WINDOW_SECONDS=600,
    )
    @patch("apps.accounts.views.send_mail")
    def test_resend_verification_is_rate_limited_per_ip(self, mock_send_mail):
        self.create_user(email="ip1@example.com", username="ipuser1", verified=False)
        self.create_user(email="ip2@example.com", username="ipuser2", verified=False)
        self.create_user(email="ip3@example.com", username="ipuser3", verified=False)
        url = reverse("accounts:resend_verification")

        self.client.post(url, {"email": "ip1@example.com"}, REMOTE_ADDR="10.0.0.9")
        self.client.post(url, {"email": "ip2@example.com"}, REMOTE_ADDR="10.0.0.9")
        response = self.client.post(url, {"email": "ip3@example.com"}, REMOTE_ADDR="10.0.0.9")

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertEqual(mock_send_mail.call_count, 2)

    @override_settings(
        RESEND_VERIFICATION_EMAIL_LIMIT=1,
        RESEND_VERIFICATION_IP_LIMIT=10,
        RESEND_VERIFICATION_WINDOW_SECONDS=600,
    )
    @patch("apps.accounts.views.send_mail")
    def test_rate_limited_resend_does_not_send_email(self, mock_send_mail):
        self.create_user(email="nosend@example.com", username="nosend", verified=False)
        url = reverse("accounts:resend_verification")
        self.client.post(url, {"email": "nosend@example.com"}, REMOTE_ADDR="10.0.0.2")
        self.client.post(url, {"email": "nosend@example.com"}, REMOTE_ADDR="10.0.0.2")
        self.assertEqual(mock_send_mail.call_count, 1)

    @override_settings(
        RESEND_VERIFICATION_EMAIL_LIMIT=1,
        RESEND_VERIFICATION_IP_LIMIT=10,
        RESEND_VERIFICATION_WINDOW_SECONDS=600,
    )
    @patch("apps.accounts.views.send_mail")
    def test_different_emails_have_separate_rate_limits(self, mock_send_mail):
        self.create_user(email="one@example.com", username="one", verified=False)
        self.create_user(email="two@example.com", username="two", verified=False)
        url = reverse("accounts:resend_verification")

        self.client.post(url, {"email": "one@example.com"}, REMOTE_ADDR="10.0.0.3")
        self.client.post(url, {"email": "one@example.com"}, REMOTE_ADDR="10.0.0.3")  # rate limited
        self.client.post(url, {"email": "two@example.com"}, REMOTE_ADDR="10.0.0.3")

        self.assertEqual(mock_send_mail.call_count, 2)
        emailed = [call.args[3][0] for call in mock_send_mail.call_args_list]
        self.assertEqual(emailed, ["one@example.com", "two@example.com"])

    @override_settings(
        RESEND_VERIFICATION_EMAIL_LIMIT=1,
        RESEND_VERIFICATION_IP_LIMIT=10,
        RESEND_VERIFICATION_WINDOW_SECONDS=600,
    )
    @patch("apps.accounts.views.send_mail")
    def test_rate_limited_unknown_and_verified_accounts_still_get_generic_response(self, mock_send_mail):
        self.create_user(email="verified-limit@example.com", username="vlimit", verified=True)
        url = reverse("accounts:resend_verification")
        # exhaust limit with unknown email
        self.client.post(url, {"email": "unknown-limit@example.com"}, REMOTE_ADDR="10.0.0.4")
        resp_unknown = self.client.post(url, {"email": "unknown-limit@example.com"}, REMOTE_ADDR="10.0.0.4")
        resp_verified = self.client.post(url, {"email": "verified-limit@example.com"}, REMOTE_ADDR="10.0.0.5")
        self.assertRedirects(resp_unknown, reverse("accounts:login"))
        self.assertRedirects(resp_verified, reverse("accounts:login"))
        mock_send_mail.assert_not_called()

    @patch("apps.accounts.views.send_mail", side_effect=RuntimeError("BREVO_API_KEY=secret"))
    def test_resend_delivery_exception_is_logged_safely(self, mock_send_mail):
        self.create_user(email="boom@example.com", username="boom", verified=False)
        with self.assertLogs("apps.accounts.views", level="ERROR") as logs:
            response = self.client.post(reverse("accounts:resend_verification"), {"email": "boom@example.com"})
        self.assertRedirects(response, reverse("accounts:login"))
        joined = "\n".join(logs.output)
        self.assertIn("Verification email delivery failed during resend request", joined)
        self.assertNotIn("secret", joined)
        self.assertNotIn("BREVO_API_KEY=secret", joined)
