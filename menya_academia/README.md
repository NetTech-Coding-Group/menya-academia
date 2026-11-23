# MENYA ACADEMIA

MENYA ACADEMIA is a modular Django learning platform with a PROVISUAL
examination service, teacher applications and approval, teacher-managed
courses, and student learning progress. Email verification and payment
fulfillment are enforced by the backend.

## Requirements

- Python 3.11 or newer
- PostgreSQL for local development and production
- Pillow for validating and processing profile and question images

## Local setup (Windows PowerShell)

From the project directory:

```powershell
Copy-Item .env.example .env
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements\development.txt
```

Install and start PostgreSQL, create a database named `menya_academia`, and set
`DATABASE_URL` in `.env` to your PostgreSQL connection. For example:
`postgresql://postgres:your-password@localhost:5432/menya_academia`. Replace
`your-password` with the password for your PostgreSQL user.

Then run:

```powershell
python manage.py migrate
python manage.py seed_provisual
python manage.py createsuperuser
python manage.py runserver
```

Open `http://127.0.0.1:8000/` (use this exact host consistently rather than
switching between `localhost` and `127.0.0.1`). If you previously had an open
admin login page, close it and reload after starting the server. In development,
account-verification messages
are printed to the runserver console. The Django admin is at `/admin/`; add
road-theory questions there before starting an exam. The default practice exam
requires 30 active questions, each with four options and exactly one correct
answer. The question count, duration, and pass mark can be changed in the
`PROVISUAL Practice Exam` record.

Run the automated tests with:

```powershell
python manage.py test
```

## Administrator and teacher access

Staff administrators can open the custom dashboard at `/admin-panel/`. It
provides live student and teacher totals, user search and profile management,
account activation controls, password-reset initiation, teacher permission
assignment, searchable activity logs, and live teacher-application review.
Admins can approve verified-email applications, reject them with a required
reason, suspend approved teachers, and retrieve supporting files through
admin-only download links. The standard Django user admin remains available for
staff management; teacher accounts created there still require a pending
application review.

Applicants can choose **Become a teacher** or visit `/become-a-teacher/`.
Applications include teaching details and optional private supporting
documents. After email verification, applicants can sign in to
`/application-status/` to see the decision. Only approved teachers can enter
`/teacher/`; approval and teacher permissions are enforced server-side.
Uploaded teacher photos and documents are stored outside the public media
directory.

Teacher capabilities are stored as individual grants, shown to the signed-in
teacher at `/teacher/`, and checked server-side with
`teacher_permission_required` before protected views run. Authenticated
write requests outside the custom admin panel are recorded with their actor,
resolved view, time, and response status; admin-panel actions are logged with
their specific change description.

Approved teachers with the corresponding grants can manage their own courses and lessons,
publish or archive courses, post course announcements, create assignments, and
review and grade submissions. Students can browse the course catalogue, view
their paid courses, complete lessons, track progress, submit assignments, and
read course announcements. Lesson materials are private to the course teacher
and students with a verified enrollment. Student rosters are course-scoped;
progress details require a separate teacher permission.

## Payment integration status

The MTN MoMo and Airtel Money merchant/API credentials and provider onboarding
are not included with the project. Checkout therefore fails closed with a clear
message: it does not send a payment request, mark an order paid, or issue a code.
Do not set `PAYMENTS_ENABLED=true` as a substitute for provider integration.

When official provider access is available, implement the provider request and
authenticated callback/status verification, then call
`apps.payments.services.confirm_verified_payment` only after independently
verifying the provider transaction, amount, and reference. The fulfillment
service is idempotent and creates either an activation code or a course
enrollment for a matching confirmed payment. Mobile-money PINs must never pass
through this application.

Email delivery uses the Brevo transactional HTTP API through
`apps.notifications.email_backends.BrevoEmailBackend`. Configure it with:

- `EMAIL_BACKEND=apps.notifications.email_backends.BrevoEmailBackend`
- `BREVO_API_KEY` - Brevo API key (sent as `api-key` header; never commit it)
- `DEFAULT_FROM_EMAIL` - verified sender email (e.g. `nettechcodinggroup@gmail.com`)
- `DEFAULT_FROM_NAME` - sender display name (e.g. `MENYA ACADEMIA`)

The backend posts JSON to `https://api.brevo.com/v3/smtp/email` and supports
subject, plain text, HTML, multiple recipients, sender name/email, timeouts,
and safe error handling. Do not log API keys or sensitive email content. For
local development without real email delivery, use
`EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`.

## SMS integration (Pindo)

Traffic exam activation codes are sent by SMS through `apps/notifications/services.py`.
Configure Pindo with environment variables (no real credentials in `.env.example`):

- `SMS_PROVIDER_URL` - Pindo single-SMS endpoint: `https://api.pindo.io/v1/sms/`
- `SMS_API_KEY` - Pindo API token (used as `Authorization: Bearer <token>`)
- `SMS_SENDER_ID` - approved Pindo sender ID

Expected Pindo request:

- Method: `POST`
- Headers: `Authorization: Bearer <SMS_API_KEY>`, `Content-Type: application/json`, `Accept: */*`
- JSON payload:

```json
{
  "to": "+2507XXXXXXXX",
  "text": "Your MENYA ACADEMIA activation code is ...",
  "sender": "YOUR_APPROVED_SENDER_ID"
}
```

The existing `send_sms(*, phone_number, message)` interface maps `message` to Pindo's `text` field.
HTTP `201` is treated as successful submission. The service safely inspects the JSON response for SMS ID/status,
logs delivery status without exposing credentials, and does not automatically retry activation-code messages.
When SMS is not configured, development keeps the existing behavior: DEBUG prints the message and the service logs a warning.

## Google and Facebook sign-in

The sign-in and registration pages offer Google and Facebook OAuth. To enable a
provider locally, create an OAuth app with that provider, add the callback URL
shown in `.env.example`, then put its client ID and secret in `.env`. Restart
the server after editing `.env`. Until configured, the provider buttons are
visible but disabled.

Google requires the `openid`, `email`, and `profile` scopes and returns the user
to `/accounts/google/login/callback/`. Facebook requires the `email` permission
and returns the user to `/accounts/facebook/login/callback/`. Use HTTPS callback
URLs outside local development. Provider secrets must never be committed or
shared in chat. Google-confirmed email addresses can match an existing account;
Facebook accounts are not automatically linked to a different account by an
unverified matching email. Social signup fills the profile name from the
provider and leaves phone number for the user to add later.

## Production configuration

Use `.env.example` as a reference for local setup. For production, provide
settings through your hosting platform's protected environment configuration:

- `DJANGO_SETTINGS_MODULE=config.settings.production`
- `DJANGO_SECRET_KEY` to a newly generated, high-entropy secret
- `DJANGO_ALLOWED_HOSTS` to the production hostnames
- `SITE_DOMAIN=menya-academia.onrender.com`, `SITE_NAME=MENYA ACADEMIA`, `SITE_SCHEME=https`
- `DATABASE_URL` to the production PostgreSQL connection
- `EMAIL_BACKEND=apps.notifications.email_backends.BrevoEmailBackend`
- `BREVO_API_KEY`, `DEFAULT_FROM_EMAIL`, and `DEFAULT_FROM_NAME`
- `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
  `FACEBOOK_OAUTH_CLIENT_ID`, and `FACEBOOK_OAUTH_CLIENT_SECRET` (as needed)

Google credentials may also use `GOOGLE_CLIENT_ID` and
`GOOGLE_CLIENT_SECRET`.
Never commit `.env` or provider credentials. Use HTTPS, a production WSGI/ASGI
server, private media storage, database backups, and monitoring. Review the
security, retention, privacy, and payment policies with the project owner
before accepting real users or payments.

## Implemented and pending scope

Implemented: shared custom user model and verified-email registration; profile
editing; role and teacher-permission data models; administrator-managed user,
permission, and audit workflows; course catalogue and teacher-owned course
management; lesson materials and paid-enrollment access checks; student
progress; course announcements; assignments, submissions, and grading;
administrator-managed packages, exams, and questions; payment records and
verified-payment fulfillment; single-use and time-limited activation;
randomized, persisted question order; server-enforced deadlines and grading;
private answer review; anonymous results; and translated account, navigation,
home, and PROVISUAL interfaces in English, French, and Kinyarwanda.

Still required before a public paid launch: official MTN/Airtel provider
adapters and onboarding, SMS provider configuration/credentials, real multilingual translations and
question content for the remaining screens and course material, provider
callback reconciliation, deployment configuration, course-specific exams and
quizzes, teacher/student messaging, reporting, and notification modules. The
monthly price of 100,000 RWF and the initial exam policy should be confirmed
before launch.