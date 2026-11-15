from django.shortcuts import get_object_or_404, redirect, render

from apps.payments.services import (
    PaymentGatewayNotConfigured,
    request_mobile_money_payment,
)

from .forms import CheckoutForm
from .models import ExamPackage


def package_list(request):
    packages = ExamPackage.objects.filter(is_active=True)
    return render(request, "provisual/packages.html", {"packages": packages})


def checkout(request, package_id):
    package = get_object_or_404(ExamPackage, pk=package_id, is_active=True)
    form = CheckoutForm(
        request.POST or None,
        user=request.user if request.user.is_authenticated else None,
    )
    if request.method == "POST" and form.is_valid():
        try:
            request_mobile_money_payment(
                package=package,
                full_name=form.cleaned_data["full_name"],
                phone_number=form.cleaned_data["phone_number"],
                email=form.cleaned_data["email"],
                provider=form.cleaned_data["provider"],
            )
        except PaymentGatewayNotConfigured as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Payment request started.")
            return redirect("activate_code")
    return render(
        request,
        "provisual/checkout.html",
        {"package": package, "form": form},
    )
