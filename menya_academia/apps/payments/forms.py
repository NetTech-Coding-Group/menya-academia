from django import forms

from .models import PaymentTransaction


class CourseCheckoutForm(forms.Form):
    provider = forms.ChoiceField(
        choices=PaymentTransaction.Provider.choices,
        widget=forms.RadioSelect,
    )
    phone_number = forms.CharField(max_length=20, min_length=9)

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phone_number"].initial = user.phone_number
