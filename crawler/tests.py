from unittest.mock import Mock, patch

import httpx
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .services import extract_metadata, fallback_topics


SAMPLE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Example Product Page</title>
  <meta name="description" content="Buy a durable analytics notebook for teams.">
  <link rel="canonical" href="/products/notebook">
  <meta property="og:type" content="product">
  <meta property="og:title" content="Notebook">
  <script type="application/ld+json">{"@type": "Product", "name": "Notebook"}</script>
</head>
<body>
  <h1>Analytics Notebook</h1>
  <h2>Built for product teams</h2>
  <p>This notebook helps product analytics teams plan launches and measure outcomes.</p>
</body>
</html>
"""

ARTICLE_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>How to Introduce Your Indoorsy Friend to the Outdoors</title>
  <meta name="description" content="A practical camping article with tips for beginners.">
  <meta property="og:type" content="article">
  <script type="application/ld+json">{"@type": "BlogPosting", "author": "REI Staff"}</script>
</head>
<body>
  <h1>How to Introduce Your Indoorsy Friend to the Outdoors</h1>
  <p>Published by an author with camping advice, hiking tips, and outdoor planning ideas.</p>
</body>
</html>
"""

NEWS_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Google Study Says AI Is Changing Tech Jobs</title>
  <meta name="description" content="Latest technology news report about AI and the workforce.">
  <script type="application/ld+json">{"@type": "NewsArticle", "datePublished": "2025-09-23"}</script>
</head>
<body>
  <h1>Google Study Says AI Is Changing Tech Jobs</h1>
  <p>Breaking news coverage from reporters with updates and analysis from the newsroom.</p>
</body>
</html>
"""

CATEGORY_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Kitchen Toasters - Shop All</title>
  <meta name="description" content="Browse toaster products by price, brand, and rating.">
</head>
<body>
  <h1>Kitchen Toasters</h1>
  <nav>Home Kitchen Appliances Toasters</nav>
  <p>Category listing with product grid, filters, sort by price, and pagination.</p>
</body>
</html>
"""

UNKNOWN_HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>Example Domain</title>
  <meta name="description" content="A simple domain for examples and documentation.">
</head>
<body>
  <h1>Example Domain</h1>
  <p>This domain is for use in illustrative examples in documents.</p>
</body>
</html>
"""


class MetadataExtractionTests(TestCase):
    @patch("crawler.services.get_keybert_model", return_value=None)
    def test_extracts_core_metadata(self, mock_keybert):
        metadata = extract_metadata(SAMPLE_HTML, "https://example.com/products/notebook")

        self.assertEqual(metadata["title"], "Example Product Page")
        self.assertEqual(metadata["canonical_url"], "https://example.com/products/notebook")
        self.assertEqual(metadata["language"], "en")
        self.assertEqual(metadata["page_type"], "product")
        self.assertIn("Product", metadata["schema_types"])
        self.assertGreater(metadata["word_count"], 0)
        self.assertEqual(len(metadata["body_hash"]), 64)
        self.assertIn("product", metadata["topics"])

    @patch("crawler.services.get_keybert_model", return_value=None)
    def test_classifies_article_page(self, mock_keybert):
        metadata = extract_metadata(ARTICLE_HTML, "https://blog.example.com/camp/outdoor-guide")

        self.assertEqual(metadata["page_type"], "article")

    @patch("crawler.services.get_keybert_model", return_value=None)
    def test_classifies_news_page(self, mock_keybert):
        metadata = extract_metadata(NEWS_HTML, "https://www.example.com/2025/09/23/tech/google-ai-jobs")

        self.assertEqual(metadata["page_type"], "news")

    @patch("crawler.services.get_keybert_model", return_value=None)
    def test_classifies_category_page(self, mock_keybert):
        metadata = extract_metadata(CATEGORY_HTML, "https://shop.example.com/category/kitchen/toasters")

        self.assertEqual(metadata["page_type"], "category")

    @patch("crawler.services.get_keybert_model", return_value=None)
    def test_classifies_unknown_page(self, mock_keybert):
        metadata = extract_metadata(UNKNOWN_HTML, "https://example.com")

        self.assertEqual(metadata["page_type"], "unknown")

    def test_fallback_topics_returns_phrases_without_common_boilerplate(self):
        topics = fallback_topics(
            {
                "title": "Camping Gear Checklist",
                "description": "A camping gear guide for beginner hikers.",
                "headings": {"h1": ["Camping Gear"], "h2": ["Beginner Hiking Tips"]},
                "visible_text": "Camping gear helps beginner hikers plan safer outdoor trips.",
            },
            limit=6,
        )

        self.assertTrue(any("camping" in topic for topic in topics))
        self.assertNotIn("the", topics)
        self.assertFalse(any("gearchecklist" in topic for topic in topics))


class CrawlApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_healthz(self):
        response = self.client.get(reverse("healthz"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("crawler.services.get_keybert_model", return_value=None)
    @patch("crawler.services.httpx.get")
    def test_post_crawl_saves_result(self, mock_get, mock_keybert):
        mock_response = Mock()
        mock_response.text = SAMPLE_HTML
        mock_response.url = "https://example.com/products/notebook"
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        response = self.client.post("/api/v1/crawl", {"url": "https://example.com/products/notebook"}, format="json")

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["page_type"], "product")
        self.assertEqual(data["status_code"], 200)

        detail = self.client.get(f"/api/v1/crawls/{data['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], data["id"])

    @patch("crawler.services.httpx.get", side_effect=httpx.ReadTimeout("The read operation timed out"))
    def test_post_crawl_returns_clear_timeout_error(self, mock_get):
        response = self.client.post("/api/v1/crawl", {"url": "https://example.com/slow"}, format="json")

        self.assertEqual(response.status_code, 504)
        self.assertIn("Timed out while fetching", response.json()["error"])
