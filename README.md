# SEO Crawler Assignment

A small Django + Django REST Framework app that crawls one URL, extracts SEO metadata, classifies the page with local rules, extracts topics with local keyword heuristics, stores the result in SQLite, and returns structured JSON.

## Features

- `GET /healthz`
- `POST /api/v1/crawl`
- `GET /api/v1/crawls/<id>`
- Simple homepage UI at `/`
- HTML fetch with `httpx`
- HTML parsing with BeautifulSoup and `lxml`
- SQLite persistence
- TF-IDF + LinearSVC page classification
- KeyBERT topic extraction with a local keyword fallback

## Setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

KeyBERT may download a small sentence-transformers embedding model the first time topic extraction runs. If that model is unavailable, the app falls back to local keyword/keyphrase extraction.

Open `http://127.0.0.1:8000/`.

## Docker

```bash
docker compose up --build
```

Open `http://127.0.0.1:8000/`.

## API Examples

Health check:

```bash
curl http://127.0.0.1:8000/healthz
```

Crawl a URL:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/crawl \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}'
```

Fetch a saved crawl:

```bash
curl http://127.0.0.1:8000/api/v1/crawls/1
```

## Response Shape

```json
{
  "id": 1,
  "url": "https://example.com",
  "final_url": "https://example.com",
  "status_code": 200,
  "title": "Example Domain",
  "description": "",
  "canonical_url": "",
  "language": "en",
  "headings": {"h1": ["Example Domain"], "h2": [], "h3": [], "h4": [], "h5": [], "h6": []},
  "open_graph": {},
  "schema_types": [],
  "visible_text": "Example Domain This domain is for use...",
  "word_count": 20,
  "body_hash": "sha256...",
  "page_type": "unknown",
  "topics": ["example", "domain"],
  "error": "",
  "created_at": "2026-07-31T00:00:00Z"
}
```

## Tests

```bash
python manage.py test
```
