from django import forms

from apps.accounts.models import User
from apps.permissions.models import TeacherPermission


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


class PermissionAssignmentForm(forms.Form):
    teacher = forms.ModelChoiceField(
        queryset=User.objects.filter(
            role=User.Role.TEACHER,
            is_staff=False,
            teacher_profile__application_status="APPROVED",
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
