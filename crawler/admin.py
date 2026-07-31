from django.contrib import admin

from .models import CrawlResult


@admin.register(CrawlResult)
class CrawlResultAdmin(admin.ModelAdmin):
    list_display = ("id", "url", "page_type", "status_code", "created_at")
    search_fields = ("url", "title", "description")
    list_filter = ("page_type", "status_code", "created_at")
