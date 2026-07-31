from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="CrawlResult",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("url", models.URLField()),
                ("final_url", models.URLField(blank=True)),
                ("status_code", models.PositiveIntegerField(blank=True, null=True)),
                ("title", models.CharField(blank=True, max_length=500)),
                ("description", models.TextField(blank=True)),
                ("canonical_url", models.URLField(blank=True)),
                ("language", models.CharField(blank=True, max_length=64)),
                ("headings", models.JSONField(default=dict)),
                ("open_graph", models.JSONField(default=dict)),
                ("schema_types", models.JSONField(default=list)),
                ("visible_text", models.TextField(blank=True)),
                ("word_count", models.PositiveIntegerField(default=0)),
                ("body_hash", models.CharField(blank=True, max_length=64)),
                ("page_type", models.CharField(default="unknown", max_length=32)),
                ("topics", models.JSONField(default=list)),
                ("error", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
