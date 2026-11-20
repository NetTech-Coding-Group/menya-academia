from django import forms
from django.contrib.auth import get_user_model
from django.db.models import F

from apps.payments.models import PaymentTransaction

from .models import AttendanceRecord, StudentMark


User = get_user_model()


def enrolled_student_queryset(course):
    return (
        User.objects.filter(
            role=User.Role.STUDENT,
            is_active=True,
            course_enrollments__course=course,
            course_enrollments__payment__status=PaymentTransaction.Status.SUCCESSFUL,
            course_enrollments__payment__course_id=course.pk,
            course_enrollments__payment__user_id=F("pk"),
        )
        .distinct()
        .order_by("full_name", "email")
    )


class AttendanceRecordForm(forms.ModelForm):
    class Meta:
        model = AttendanceRecord
        fields = ("student", "date", "status", "remarks")
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.TextInput(attrs={"placeholder": "Optional remark"}),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        if course is not None:
            self.fields["student"].queryset = enrolled_student_queryset(course)
        else:
            self.fields["student"].queryset = User.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get("student")
        date = cleaned_data.get("date")
        if self.course and student and date:
            qs = AttendanceRecord.objects.filter(
                course=self.course, student=student, date=date
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    None,
                    "Attendance for this student and date has already been recorded for this class.",
                )
        return cleaned_data


class StudentMarkForm(forms.ModelForm):
    class Meta:
        model = StudentMark
        fields = (
            "student",
            "assessment_name",
            "assessment_type",
            "term",
            "assessment_date",
            "score",
            "max_score",
            "remarks",
        )
        widgets = {
            "assessment_date": forms.DateInput(attrs={"type": "date"}),
            "remarks": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        if course is not None:
            self.fields["student"].queryset = enrolled_student_queryset(course)
        else:
            self.fields["student"].queryset = User.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        score = cleaned_data.get("score")
        max_score = cleaned_data.get("max_score")
        if score is not None and max_score is not None and score > max_score:
            self.add_error("score", "Score cannot be greater than the maximum score.")
        return cleaned_data
