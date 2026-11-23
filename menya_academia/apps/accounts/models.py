import uuid
from pathlib import Path

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models


def avatar_upload_path(instance, filename):
    extension = Path(filename).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".img"
    return f"avatars/{uuid.uuid4().hex}{extension}"


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(
        self,
        email,
        username,
        full_name,
        phone_number,
        password=None,
        **extra_fields,
    ):
        if not email:
            raise ValueError("An email address is required.")
        if not username:
            raise ValueError("A username is required.")
        if not full_name:
            raise ValueError("A full name is required.")
        if not phone_number:
            raise ValueError("A phone number is required.")

        user = self.model(
            email=self.normalize_email(email).lower(),
            username=username.strip(),
            full_name=full_name.strip(),
            phone_number=phone_number.strip(),
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email,
        username,
        full_name,
        phone_number,
        password=None,
        **extra_fields,
    ):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusers must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_superuser=True.")
        return self.create_user(
            email,
            username,
            full_name,
            phone_number,
            password=password,
            **extra_fields,
        )


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        STUDENT = "STUDENT", "Student / Candidate"
        TEACHER = "TEACHER", "Teacher"
        ADMIN = "ADMIN", "Administrator"
        PARENT = "PARENT", "Parent"

    class Language(models.TextChoices):
        ENGLISH = "en", "English"
        FRENCH = "fr", "French"
        KINYARWANDA = "rw", "Kinyarwanda"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    username = models.CharField(max_length=50, unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, db_index=True)
    role = models.CharField(max_length=15, choices=Role.choices, default=Role.STUDENT)
    preferred_language = models.CharField(
        max_length=5, choices=Language.choices, default=Language.ENGLISH
    )
    avatar = models.ImageField(upload_to=avatar_upload_path, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    must_change_password = models.BooleanField(
        default=False,
        help_text="Requires the user to change their password at next sign-in.",
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "full_name", "phone_number"]

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    def get_full_name(self):
        return self.full_name

    def get_short_name(self):
        return self.full_name
