from django import forms

from .models import Course, CourseAnnouncement


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = (
            "title",
            "education_level",
            "short_description",
            "description",
            "price_rwf",
            "cover_image",
        )
        widgets = {
            "short_description": forms.Textarea(attrs={"rows": 2}),
            "description": forms.Textarea(attrs={"rows": 7}),
            "price_rwf": forms.NumberInput(attrs={"min": 1}),
        }

    def clean_cover_image(self):
        image = self.cleaned_data.get("cover_image")
        if image and image.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Course images must be 5 MB or smaller.")
        return image


class CourseAnnouncementForm(forms.ModelForm):
    class Meta:
        model = CourseAnnouncement
        fields = ("title", "message")
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}
