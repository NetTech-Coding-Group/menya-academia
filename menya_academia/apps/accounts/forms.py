from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.password_validation import validate_password

from .models import User


class RegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput, strip=False
    )
    password2 = forms.CharField(
        label="Confirm password", widget=forms.PasswordInput, strip=False
    )

    class Meta:
        model = User
        fields = ("full_name", "username", "email", "phone_number", "preferred_language")

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        validate_password(password, self.instance)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", "The passwords do not match.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(label="Email address")

    def clean(self):
        cleaned_data = super().clean()
        if self.user_cache is not None and not self.user_cache.is_email_verified:
            self.add_error(
                None,
                "Verify your email address before signing in. Check your inbox for the verification link.",
            )
        return cleaned_data


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "phone_number", "preferred_language", "avatar")

    def clean_avatar(self):
        image = self.cleaned_data.get("avatar")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Profile images must be 5 MB or smaller.")
        return image


class AdminUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "full_name",
            "phone_number",
            "role",
            "preferred_language",
            "is_email_verified",
            "is_active",
            "is_staff",
            "is_superuser",
        )
