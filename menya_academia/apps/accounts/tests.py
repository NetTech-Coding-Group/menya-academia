from django.test import Client, TestCase
from django.test import override_settings
from django.urls import reverse

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
