from django.db import models


class CrawlResult(models.Model):
    url = models.URLField()
    final_url = models.URLField(blank=True)
    status_code = models.PositiveIntegerField(null=True, blank=True)
    title = models.CharField(max_length=500, blank=True)
    description = models.TextField(blank=True)
    canonical_url = models.URLField(blank=True)
    language = models.CharField(max_length=64, blank=True)
    headings = models.JSONField(default=dict)
    open_graph = models.JSONField(default=dict)
    schema_types = models.JSONField(default=list)
    visible_text = models.TextField(blank=True)
    word_count = models.PositiveIntegerField(default=0)
    body_hash = models.CharField(max_length=64, blank=True)
    page_type = models.CharField(max_length=32, default="unknown")
    topics = models.JSONField(default=list)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.url} ({self.page_type})"
