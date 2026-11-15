from functools import wraps

from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from apps.teachers.models import TeacherProfile


def teacher_permission_required(permission_key):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")

            if not request.user.is_active:
                raise PermissionDenied("This account is inactive.")

            if request.user.is_superuser or (
                request.user.is_staff and request.user.role == "ADMIN"
            ):
                return view_func(request, *args, **kwargs)

            if request.user.role == "TEACHER":
                if not TeacherProfile.objects.filter(
                    user=request.user,
                    application_status=TeacherProfile.ApplicationStatus.APPROVED,
                ).exists():
                    raise PermissionDenied(
                        "A teacher application must be approved before using the workspace."
                    )
                if request.user.granted_permissions.filter(
                    permission_key=permission_key
                ).exists():
                    return view_func(request, *args, **kwargs)

            raise PermissionDenied("You do not have permission to perform this action.")

        return _wrapped_view

    return decorator