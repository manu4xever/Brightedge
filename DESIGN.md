# Design: Billion URL SEO Crawler

## Goals

Build a crawler that can process billions of URLs reliably, extract structured SEO metadata, and make results queryable for product, analytics, and data science use cases.

## High-Level Architecture

- URL ingestion API accepts seeds, sitemaps, and batch uploads.
- Scheduler normalizes URLs, deduplicates work, applies robots and domain politeness rules, and publishes crawl jobs.
- Queue layer uses Kafka, SQS, or Pub/Sub with retry and dead-letter topics.
- Worker fleet fetches pages with bounded timeouts, parses HTML, extracts metadata, and emits crawl results.
- Raw HTML and fetch artifacts are stored in S3 or compatible object storage.
- Parsed metadata is stored in an OLTP database for lookups and a data lake for analytics.
- Search indexes support URL, title, topic, and domain-level exploration.

## Data Flow

1. Ingest URL.
2. Normalize and fingerprint URL.
3. Check dedupe store and crawl freshness policy.
4. Enqueue crawl job.
5. Worker fetches HTML with domain-level rate limits.
6. Worker stores raw response in S3.
7. Worker extracts metadata, topics, hashes, and classification.
8. Worker writes structured result to metadata storage.
9. Metrics and traces are emitted for every stage.

## Queues and Workers

Queues should be partitioned by domain or URL host hash so politeness can be enforced without global locks. Workers should be stateless and horizontally scalable. Failed jobs use exponential backoff and move to a dead-letter queue after a small number of attempts.

## Storage

- S3/data lake: raw HTML, response headers, screenshots if needed, parser outputs, historical snapshots.
- Metadata store: PostgreSQL, DynamoDB, or Cassandra depending on query patterns and scale.
- Analytics: Iceberg/Delta tables over object storage for trend analysis and model development.
- Cache/dedupe: Redis or DynamoDB for recently seen URL fingerprints and crawl locks.

## Monitoring

Track:

- Crawl success rate by domain and status code.
- Fetch latency and parse latency.
- Queue depth and job age.
- Worker CPU, memory, and network saturation.
- Robots failures and timeout rates.
- Metadata extraction completeness.
- Dead-letter queue volume.

## SLOs and SLAs

Example SLOs:

- 99% of accepted crawl jobs start within 15 minutes.
- 95% of successful fetches complete parsing within 30 seconds.
- 99.9% API availability for result lookups.
- Less than 0.1% duplicate crawl jobs per day after normalization.

SLAs should be looser than SLOs and aligned to customer contracts, for example daily batch completion by a published reporting window.

## Reliability

- Idempotent crawl result writes keyed by URL fingerprint and crawl timestamp.
- Dead-letter queues for repeat failures.
- Per-domain circuit breakers.
- Backpressure from queues to ingestion.
- Replayable raw artifacts in S3.
- Versioned parser output so extraction logic can evolve safely.

## Security and Compliance

- Respect robots.txt and crawl-delay where required.
- Block private IP ranges and internal hostnames to prevent SSRF.
- Store only needed content and define retention policies.
- Encrypt data at rest and in transit.
- Maintain audit logs for ingestion and data access.
