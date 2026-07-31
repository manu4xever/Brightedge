from django.urls import path

from .views import crawl_create, crawl_detail


urlpatterns = [
    path("crawl", crawl_create, name="crawl-create"),
    path("crawls/<int:pk>", crawl_detail, name="crawl-detail"),
]
