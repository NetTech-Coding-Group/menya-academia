from django.urls import path

from . import views


app_name = "courses"

urlpatterns = [
    path("", views.catalog, name="catalog"),
    path("<slug:slug>/", views.course_detail, name="detail"),
    path("<slug:slug>/checkout/", views.checkout, name="checkout"),
]
