from django.contrib import admin
from django.urls import include, path

from crawler.views import healthz, homepage


urlpatterns = [
    path("", homepage, name="homepage"),
    path("healthz", healthz, name="healthz"),
    path("admin/", admin.site.urls),
    path("api/v1/", include("crawler.urls")),
]
