from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from .models import TeacherProfile


def register_teacher(request):
    if request.user.is_authenticated and (
        request.user.is_superuser
        or (request.user.is_staff and request.user.role == request.user.Role.ADMIN)
    ):
        return redirect("administrators:teacher_create")
    if request.user.is_authenticated:
        raise PermissionDenied("Only administrators can register and add teachers.")
    messages.info(
        request,
        "Teacher accounts are created by administrators. Please contact the school administrator.",
    )
    return redirect("accounts:login")


@login_required(login_url="accounts:login")
def application_status(request):
    if not request.user.is_active:
        raise PermissionDenied("This account is inactive.")
    try:
        profile = request.user.teacher_profile
    except TeacherProfile.DoesNotExist:
        return redirect("home")
    if request.user.role != request.user.Role.TEACHER:
        return redirect("home")
    return render(
        request,
        "teachers/application_status.html",
        {"profile": profile},
    )
