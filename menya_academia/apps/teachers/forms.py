from pathlib import Path

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from apps.accounts.models import User

from .models import (
    TeacherProfile,
    validate_supporting_document,
)


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def clean(self, data, initial=None):
        if not data:
            if self.required:
                raise forms.ValidationError(self.error_messages["required"])
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        return [
            super(MultipleFileField, self).clean(upload, initial)
            for upload in data
        ]


class TeacherRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full legal name")
    email = forms.EmailField(label="Email address")
    phone_number = forms.CharField(max_length=20, label="Phone number")
    password1 = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput,
    )
    password2 = forms.CharField(
        label="Confirm password",
        strip=False,
        widget=forms.PasswordInput,
    )
    teaching_subject = forms.ChoiceField(
        choices=TeacherProfile.Subject.choices,
        label="Teaching subject",
    )
    qualifications = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Qualifications",
    )
    teaching_experience = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Teaching experience",
    )
    institution = forms.CharField(
        required=False,
        max_length=180,
        label="School or institution",
    )
    profile_photo = forms.ImageField(required=False, label="Profile photo")
    supporting_documents = MultipleFileField(
        required=False,
        widget=MultipleFileInput(attrs={"multiple": True}),
        label="Supporting documents",
        help_text="Optional. PDF, JPG, or PNG, up to 10 MB per file.",
    )
    terms_accepted = forms.BooleanField(
        required=True,
        label="I accept the Terms and Conditions.",
    )

    def __init__(self, *args, files=None, **kwargs):
        if files is not None:
            kwargs["files"] = files
        super().__init__(*args, **kwargs)
        self.uploaded_files = files

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password1(self):
        password = self.cleaned_data["password1"]
        candidate = User(
            full_name=self.cleaned_data.get("full_name", ""),
            email=self.cleaned_data.get("email", ""),
            phone_number=self.cleaned_data.get("phone_number", ""),
        )
        validate_password(password, candidate)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password1") != cleaned_data.get("password2"):
            self.add_error("password2", "The passwords do not match.")

        documents = (
            self.uploaded_files.getlist("supporting_documents")
            if self.uploaded_files
            else []
        )
        if len(documents) > 5:
            self.add_error("supporting_documents", "Upload no more than 5 documents.")
        for document in documents:
            try:
                validate_supporting_document(document)
            except ValidationError as error:
                self.add_error("supporting_documents", error)
        return cleaned_data

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if photo and photo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Profile photos must be 5 MB or smaller.")
        if photo and Path(photo.name).suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise forms.ValidationError("Upload a JPG, PNG, or WebP profile photo.")
        return photo

    def save(self):
        from .services import create_teacher_application

        return create_teacher_application(
            data=self.cleaned_data,
            documents=(
                self.uploaded_files.getlist("supporting_documents")
                if self.uploaded_files
                else []
            ),
        )
