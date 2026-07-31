# POC Plan

## Schedule

Week 1:

- Build single-URL crawler API and UI.
- Extract SEO metadata, headings, schema.org types, visible text, body hash, classification, and topics.
- Store results in SQLite.

Week 2:

- Add test fixtures for product, article, news, category, and unknown pages.
- Improve parser edge cases.
- Add Docker packaging and deployment notes.

Week 3:

- Run evaluation on a small URL set.
- Review extraction accuracy and failure modes.
- Prepare demo and release checklist.

## Blockers

- Python and project dependencies must be available in the runtime environment.
- Network access is required for live crawls.
- Some sites block automated requests or require JavaScript rendering.
- Robots.txt and legal crawl policy need product confirmation for production use.

## Evaluation

Measure:

- Crawl success rate.
- Metadata completeness.
- Page type classification accuracy.
- Topic relevance.
- Average fetch and parse latency.
- Error quality for blocked, timeout, and invalid URLs.

Use a labeled sample across product pages, articles, news pages, category pages, and generic homepages.

## Release Plan

1. Ship the local POC with Docker.
2. Demo UI and API responses.
3. Review evaluation results.
4. Decide production scope for queueing, storage, monitoring, and security.
5. Create implementation tickets for a scalable worker architecture.
