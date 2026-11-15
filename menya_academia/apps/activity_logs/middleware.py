from apps.activity_logs.models import ActivityLog


class ActivityLogMiddleware:
    MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            request.method in self.MUTATING_METHODS
            and request.user.is_authenticated
            and not request.path_info.startswith("/admin-panel/")
        ):
            view_name = getattr(request.resolver_match, "view_name", None)
            view_name = view_name or "unmatched endpoint"
            action = f"{request.method.lower()}.{view_name}"[:64]
            ActivityLog.objects.create(
                actor=request.user,
                actor_name=request.user.full_name,
                actor_email=request.user.email,
                actor_role=request.user.role,
                action=action,
                description=f"{request.method} request to {view_name}",
                status=(
                    ActivityLog.Status.SUCCESS
                    if response.status_code < 400
                    else ActivityLog.Status.FAILURE
                ),
            )
        return response
