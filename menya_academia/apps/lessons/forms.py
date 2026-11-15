from django import forms

from .models import (
    Assignment,
    AssignmentSubmission,
    CourseSection,
    Lesson,
)


class CourseSectionForm(forms.ModelForm):
    class Meta:
        model = CourseSection
        fields = ("title", "position")
        widgets = {"position": forms.NumberInput(attrs={"min": 1})}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course

    def clean_position(self):
        position = self.cleaned_data["position"]
        if position < 1:
            raise forms.ValidationError("Section position must be at least 1.")
        sections = CourseSection.objects.filter(course=self.course, position=position)
        if self.instance.pk:
            sections = sections.exclude(pk=self.instance.pk)
        if sections.exists():
            raise forms.ValidationError("This section position is already in use.")
        return position


class LessonForm(forms.ModelForm):
    section = forms.ModelChoiceField(
        queryset=CourseSection.objects.none(),
        label="Course section",
    )

    class Meta:
        model = Lesson
        fields = (
            "section",
            "title",
            "description",
            "kind",
            "content",
            "video_url",
            "material",
            "position",
        )
        widgets = {
            "content": forms.Textarea(attrs={"rows": 7}),
            "position": forms.NumberInput(attrs={"min": 1}),
        }

    def __init__(self, *args, course, allow_material_upload=True, **kwargs):
        super().__init__(*args, **kwargs)
        self.course = course
        self.fields["section"].queryset = course.sections.all()
        if not allow_material_upload:
            self.fields.pop("material")

    def clean(self):
        cleaned_data = super().clean()
        section = cleaned_data.get("section")
        position = cleaned_data.get("position")
        if position is not None and position < 1:
            self.add_error("position", "Lesson position must be at least 1.")
        if section and position:
            lessons = Lesson.objects.filter(section=section, position=position)
            if self.instance.pk:
                lessons = lessons.exclude(pk=self.instance.pk)
            if lessons.exists():
                self.add_error("position", "This lesson position is already in use.")
        return cleaned_data

    def clean_material(self):
        material = self.cleaned_data.get("material")
        if material and material.size > 100 * 1024 * 1024:
            raise forms.ValidationError("Learning materials must be 100 MB or smaller.")
        return material


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ("title", "instructions", "max_points", "due_at")
        widgets = {
            "instructions": forms.Textarea(attrs={"rows": 6}),
            "due_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "max_points": forms.NumberInput(attrs={"min": 1, "max": 32767}),
        }


class AssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("answer",)
        widgets = {
            "answer": forms.Textarea(
                attrs={"rows": 8, "placeholder": "Write your answer here"}
            )
        }


class AssignmentGradeForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ("score", "feedback")
        widgets = {
            "score": forms.NumberInput(attrs={"min": 0}),
            "feedback": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, assignment, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        self.fields["score"].required = True
        self.fields["score"].widget.attrs["max"] = assignment.max_points

    def clean_score(self):
        score = self.cleaned_data["score"]
        if score > self.assignment.max_points:
            raise forms.ValidationError(
                f"Score cannot exceed {self.assignment.max_points} points."
            )
        return score
