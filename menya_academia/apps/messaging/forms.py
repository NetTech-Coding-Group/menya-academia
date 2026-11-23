from django import forms

from .models import Conversation


class MessageForm(forms.Form):
    content = forms.CharField(
        label="Message",
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "rows": 3,
                "placeholder": "Write your message...",
                "maxlength": "5000",
                "class": "messaging-input",
            }
        ),
    )

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()
        if not content:
            raise forms.ValidationError("Message cannot be empty.")
        if len(content) > 5000:
            raise forms.ValidationError("Message is too long (maximum 5000 characters).")
        return content


class SupportConversationForm(forms.Form):
    category = forms.ChoiceField(
        choices=Conversation.Category.choices,
        initial=Conversation.Category.OTHER,
        label="Support category",
    )
    subject = forms.CharField(
        max_length=180,
        required=False,
        label="Subject",
        widget=forms.TextInput(attrs={"placeholder": "Briefly describe your issue", "class": "messaging-text-input"}),
    )
    content = forms.CharField(
        label="Message",
        max_length=5000,
        widget=forms.Textarea(
            attrs={
                "rows": 4,
                "placeholder": "Describe your issue...",
                "maxlength": "5000",
                "class": "messaging-input",
            }
        ),
    )

    def clean_content(self):
        content = (self.cleaned_data.get("content") or "").strip()
        if not content:
            raise forms.ValidationError("Message cannot be empty.")
        return content

    def clean_subject(self):
        return (self.cleaned_data.get("subject") or "").strip()[:180]
