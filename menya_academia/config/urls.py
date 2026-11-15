from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from apps.accounts.views import set_language


urlpatterns = [
    path("admin/", admin.site.urls),
    path("i18n/setlang/", set_language, name="set_language"),
    path("admin-panel/", include("apps.administrators.urls")),
    path("teacher/", include("apps.teacher_workspace.urls")),
    path("", include("apps.teachers.urls")),
    path("courses/", include("apps.courses.urls")),
    path("", include("apps.enrollments.urls")),
    path("lessons/", include("apps.lessons.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("provisual/", include("apps.provisual.urls")),
    path("", include("apps.examinations.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)