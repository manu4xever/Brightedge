from rest_framework import serializers

from .models import CrawlResult


class CrawlRequestSerializer(serializers.Serializer):
    url = serializers.URLField()


class CrawlResultSerializer(serializers.ModelSerializer):
    class Meta:
        model = CrawlResult
        fields = [
            "id",
            "url",
            "final_url",
            "status_code",
            "title",
            "description",
            "canonical_url",
            "language",
            "headings",
            "open_graph",
            "schema_types",
            "visible_text",
            "word_count",
            "body_hash",
            "page_type",
            "topics",
            "error",
            "created_at",
        ]
