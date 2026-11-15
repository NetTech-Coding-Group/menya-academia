from django.urls import path

from . import views


app_name = "provisual"

urlpatterns = [
    path("", views.package_list, name="packages"),
    path("checkout/<int:package_id>/", views.checkout, name="checkout"),
]
