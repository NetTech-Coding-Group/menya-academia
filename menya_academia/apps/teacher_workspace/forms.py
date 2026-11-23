from django import forms
from django.contrib.auth import get_user_model
from django.db.models import F

from apps.examinations.models import AnswerOption, Question
from apps.payments.models import PaymentTransaction
from apps.provisual.models import Exam

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


class TeacherExamForm(forms.ModelForm):
    selected_questions = forms.ModelMultipleChoiceField(
        queryset=Question.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Select Questions from the Existing Question Bank",
        help_text="Choose the multiple-choice questions to include in this exam.",
    )

    class Meta:
        model = Exam
        fields = (
            "title",
            "description",
            "category",
            "question_count",
            "duration_minutes",
            "pass_mark",
            "instructions",
            "selected_questions",
        )
        labels = {
            "title": "Exam Title",
            "description": "Exam Description",
            "category": "Examination Category / Subject",
            "question_count": "Number of Questions",
            "duration_minutes": "Examination Duration (minutes)",
            "pass_mark": "Passing Mark (%)",
            "instructions": "Exam Instructions",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "instructions": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["title"].required = True
        self.fields["category"].required = True
        self.fields["question_count"].required = True
        self.fields["duration_minutes"].required = True
        self.fields["pass_mark"].required = True
        self.fields["selected_questions"].queryset = (
            Question.objects.filter(is_active=True)
            .prefetch_related("options")
            .order_by("id")
        )
        self.fields["selected_questions"].label_from_instance = self._question_label

    @staticmethod
    def _question_label(question):
        text = question.text_en or question.text_rw or question.text_fr
        text = (text or "").strip()
        if len(text) > 120:
            text = text[:117] + "..."
        return f"Q{question.pk}: {text}"

    def clean(self):
        cleaned_data = super().clean()
        selected_questions = cleaned_data.get("selected_questions")
        selected_count = selected_questions.count() if selected_questions is not None else 0
        question_count = cleaned_data.get("question_count")
        duration = cleaned_data.get("duration_minutes")
        pass_mark = cleaned_data.get("pass_mark")

        if selected_questions is not None:
            selected_questions = selected_questions.prefetch_related("options")
            invalid = []
            for question in selected_questions:
                options = list(question.options.all())
                if len(options) != 4 or sum(1 for option in options if option.is_correct) != 1:
                    invalid.append(str(question.pk))
            if invalid:
                self.add_error(
                    "selected_questions",
                    "Some selected questions are incomplete. Each question must have 4 options and exactly 1 correct answer.",
                )

        if question_count is not None and selected_count and question_count != selected_count:
            self.add_error(
                "question_count",
                f"Number of Questions must match the number of selected questions ({selected_count}).",
            )
        if question_count is not None and question_count < 1:
            self.add_error("question_count", "Number of Questions must be at least 1.")
        if duration is not None and duration < 1:
            self.add_error("duration_minutes", "Examination Duration must be at least 1 minute.")
        if pass_mark is not None and not (1 <= pass_mark <= 100):
            self.add_error("pass_mark", "Passing Mark must be between 1 and 100.")

        action = getattr(self, "submit_action", "draft")
        if action == "submit":
            if not cleaned_data.get("title"):
                self.add_error("title", "Exam Title is required.")
            if not cleaned_data.get("category"):
                self.add_error("category", "Examination Category / Subject is required.")
            if selected_count < 1:
                self.add_error("selected_questions", "Select at least one question before submitting for approval.")
            if question_count is None:
                self.add_error("question_count", "Number of Questions is required.")
            if duration is None:
                self.add_error("duration_minutes", "Examination Duration is required.")
            if pass_mark is None:
                self.add_error("pass_mark", "Passing Mark is required.")

        # Keep question_count consistent when questions are selected.
        if selected_count and not self.errors.get("question_count"):
            cleaned_data["question_count"] = selected_count
        return cleaned_data

class KinyarwandaQuestionForm(forms.ModelForm):
    option_a_rw = forms.CharField(max_length=255, label="Igisubizo A (Kinyarwanda)")
    option_b_rw = forms.CharField(max_length=255, label="Igisubizo B (Kinyarwanda)")
    option_c_rw = forms.CharField(max_length=255, label="Igisubizo C (Kinyarwanda)")
    option_d_rw = forms.CharField(max_length=255, label="Igisubizo D (Kinyarwanda)")
    correct_option = forms.ChoiceField(
        choices=AnswerOption.Letter.choices,
        widget=forms.RadioSelect,
        label="Igisubizo cy'ukuri",
    )

    class Meta:
        model = Question
        fields = ("text_rw", "image", "explanation_rw", "is_active")
        labels = {
            "text_rw": "Ikibazo (Kinyarwanda)",
            "image": "Ifoto (si ngombwa)",
            "explanation_rw": "Ibisobanuro (Kinyarwanda)",
            "is_active": "Irakora",
        }
        widgets = {
            "text_rw": forms.Textarea(attrs={"rows": 3}),
            "explanation_rw": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["text_rw"].required = True
        self.fields["explanation_rw"].required = True
        self.fields["is_active"].initial = True
        if self.instance and self.instance.pk:
            for option in self.instance.options.all():
                prefix = f"option_{option.letter.lower()}_rw"
                if prefix in self.fields:
                    self.fields[prefix].initial = option.text_rw
                if option.is_correct:
                    self.fields["correct_option"].initial = option.letter

    def clean(self):
        cleaned_data = super().clean()
        text_rw = (cleaned_data.get("text_rw") or "").strip()
        explanation_rw = (cleaned_data.get("explanation_rw") or "").strip()
        if not text_rw:
            self.add_error("text_rw", "Andika ikibazo mu Kinyarwanda.")
        if not explanation_rw:
            self.add_error("explanation_rw", "Andika ibisobanuro mu Kinyarwanda.")
        correct = cleaned_data.get("correct_option")
        if not correct:
            self.add_error("correct_option", "Hitamo igisubizo kimwe cy'ukuri.")
        for letter in ("A", "B", "C", "D"):
            key = f"option_{letter.lower()}_rw"
            if not (cleaned_data.get(key) or "").strip():
                self.add_error(key, f"Uzuza igisubizo {letter} mu Kinyarwanda.")
        image = cleaned_data.get("image")
        if image and hasattr(image, "size") and image.size > 5 * 1024 * 1024:
            self.add_error("image", "Ifoto ntigomba kurenza 5MB.")
        return cleaned_data

    def save(self, commit=True, approval_status=None, clear_other_languages=True):
        question = super().save(commit=False)
        if clear_other_languages:
            # PROVISUAL creation interface is Kinyarwanda-only.
            question.text_en = ""
            question.text_fr = ""
            question.explanation_en = ""
            question.explanation_fr = ""
        if approval_status is not None:
            question.approval_status = approval_status
        if commit:
            question.save()
            self._save_options(question, clear_other_languages=clear_other_languages)
        return question

    def _save_options(self, question, clear_other_languages=True):
        correct = self.cleaned_data["correct_option"]
        for letter in ("A", "B", "C", "D"):
            defaults = {
                "text_rw": self.cleaned_data.get(f"option_{letter.lower()}_rw", "").strip(),
                "is_correct": letter == correct,
            }
            if clear_other_languages:
                defaults["text_en"] = ""
                defaults["text_fr"] = ""
            AnswerOption.objects.update_or_create(
                question=question,
                letter=letter,
                defaults=defaults,
            )

    def save_options(self, question):
        self._save_options(question)


# Backward-compatible alias for older imports; PROVISUAL interface is Kinyarwanda-only.
TrafficQuestionForm = KinyarwandaQuestionForm
