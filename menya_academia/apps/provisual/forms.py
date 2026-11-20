from django import forms

from apps.payments.models import PaymentTransaction


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Full name")
    phone_number = forms.CharField(
        max_length=20,
        label="Phone number (to receive activation code by SMS)",
    )
    provider = forms.ChoiceField(
        choices=PaymentTransaction.Provider.choices,
        label="Payment method",
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields["full_name"].initial = user.full_name
            self.fields["phone_number"].initial = user.phone_number
