from django import forms
from django.contrib.auth.password_validation import validate_password

from apps.accounts.models import User
from apps.courses.models import Course
from apps.permissions.models import TeacherPermission
from apps.teachers.models import TeacherProfile


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = (
            "full_name",
            "username",
            "email",
            "phone_number",
            "role",
            "preferred_language",
            "is_email_verified",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = tuple(
            (value, label)
            for value, label in User.Role.choices
            if value != User.Role.ADMIN
        )


class TeacherAdminCreateForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name")
    username = forms.CharField(max_length=50, label="Username")
    email = forms.EmailField(label="Email address")
    phone_number = forms.CharField(max_length=20, label="Phone number")
    password1 = forms.CharField(
        label="Temporary password",
        widget=forms.PasswordInput,
        strip=False,
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput,
        strip=False,
    )
    preferred_language = forms.ChoiceField(
        choices=User.Language.choices,
        initial=User.Language.ENGLISH,
        label="Preferred language",
    )
    is_email_verified = forms.BooleanField(
        required=False,
        initial=True,
        label="Email verified",
    )
    is_active = forms.BooleanField(required=False, initial=True, label="Account active")
    teaching_subject = forms.ChoiceField(
        choices=TeacherProfile.Subject.choices,
        label="Primary subject",
    )
    teacher_role_title = forms.CharField(
        max_length=120,
        required=False,
        label="Assigned role/title",
        help_text="Example: Class Teacher, Subject Teacher, Head of Department.",
    )
    assigned_subjects = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Assigned subjects",
        help_text="Enter one subject per line or separate subjects with commas.",
    )
    responsibilities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Responsibilities",
        help_text="Describe the teacher's duties and responsibilities.",
    )
    assigned_classes = forms.ModelMultipleChoiceField(
        queryset=Course.objects.filter(is_archived=False).order_by("title"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Assigned classes/courses",
    )
    qualifications = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Qualifications",
    )
    teaching_experience = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Teaching experience",
    )
    institution = forms.CharField(max_length=180, required=False, label="Institution")
    permissions = forms.MultipleChoiceField(
        choices=TeacherPermission.PERMISSION_KEYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissions",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_classes"].queryset = Course.objects.filter(
            is_archived=False
        ).order_by("title")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("This username is already in use.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "The passwords do not match.")
        if password1 and not self.errors.get("password1"):
            candidate = User(
                full_name=cleaned_data.get("full_name", ""),
                email=cleaned_data.get("email", ""),
                username=cleaned_data.get("username", ""),
                phone_number=cleaned_data.get("phone_number", ""),
            )
            try:
                validate_password(password1, candidate)
            except forms.ValidationError as error:
                self.add_error("password1", error)
        return cleaned_data


class TeacherAdminEditForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name")
    username = forms.CharField(max_length=50, label="Username")
    email = forms.EmailField(label="Email address")
    phone_number = forms.CharField(max_length=20, label="Phone number")
    preferred_language = forms.ChoiceField(
        choices=User.Language.choices, label="Preferred language"
    )
    is_email_verified = forms.BooleanField(required=False, label="Email verified")
    is_active = forms.BooleanField(required=False, label="Account active")
    teaching_subject = forms.ChoiceField(
        choices=TeacherProfile.Subject.choices, label="Primary subject"
    )
    teacher_role_title = forms.CharField(
        max_length=120, required=False, label="Assigned role/title"
    )
    assigned_subjects = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Assigned subjects",
        help_text="Enter one subject per line or separate subjects with commas.",
    )
    responsibilities = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
        label="Responsibilities",
    )
    assigned_classes = forms.ModelMultipleChoiceField(
        queryset=Course.objects.filter(is_archived=False).order_by("title"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Assigned classes/courses",
    )
    qualifications = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="Qualifications"
    )
    teaching_experience = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Teaching experience",
    )
    institution = forms.CharField(max_length=180, required=False, label="Institution")
    permissions = forms.MultipleChoiceField(
        choices=TeacherPermission.PERMISSION_KEYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissions",
    )

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher
        self.fields["assigned_classes"].queryset = Course.objects.filter(
            is_archived=False
        ).order_by("title")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = User.objects.filter(email__iexact=email)
        if self.teacher:
            qs = qs.exclude(pk=self.teacher.pk)
        if qs.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        qs = User.objects.filter(username__iexact=username)
        if self.teacher:
            qs = qs.exclude(pk=self.teacher.pk)
        if qs.exists():
            raise forms.ValidationError("This username is already in use.")
        return username



class PermissionAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(
            role=User.Role.TEACHER,
            is_staff=False,
            teacher_profile__application_status__in=[
                TeacherProfile.ApplicationStatus.APPROVED,
                TeacherProfile.ApplicationStatus.SUSPENDED,
            ],
        ).order_by("full_name", "email"),
        empty_label="Select a teacher",
    )
    permissions = forms.MultipleChoiceField(
        choices=TeacherPermission.PERMISSION_KEYS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )


class TeacherApplicationRejectionForm(forms.Form):
    rejection_reason = forms.CharField(
        label="Reason for rejection",
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=2000,
    )


class ActivityLogFilterForm(forms.Form):
    search = forms.CharField(required=False, max_length=100)
    role = forms.ChoiceField(
        required=False,
        choices=(("", "All roles"), *User.Role.choices),
    )
    action = forms.ChoiceField(
        required=False,
        choices=(("", "All activity"),),
    )
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_from > date_to:
            self.add_error("date_to", "The end date must be on or after the start date.")
        return cleaned_data
