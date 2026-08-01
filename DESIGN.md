# Design: Billion URL SEO Crawler

## Goals

The goal is to scale the crawler from a single-URL proof of concept into a production system that can process billions of URLs for a given year/month batch, extract SEO metadata and page topics, store results in a unified schema, and make the data available for lookup, analytics, and model improvement.
The system must optimize for:
-Scale: billions of URLs per monthly batch.
-Reliability: every accepted URL reaches a final state.
-Performance: high crawl throughput with bounded latency.
-Cost: avoid expensive processing unless it adds value.
-Availability: query APIs and stored metadata remain available during crawling.

## High-Level Architecture
<img width="1446" height="174" alt="image" src="https://github.com/user-attachments/assets/967cfe3f-42d7-4572-9334-6d651bc4cac4" />


## Data Flow

1:Assuming Monthly URL input arrives as text files in object storage or rows in MySQL.
2:Ingestion jobs validate URLs, normalize them, assign crawl_month[for tagging], and compute a stable url_hash[deduplicaiton & fast lookup].
3:Deduplication removes repeated URLs within the same batch and avoids unnecessary recrawls based on freshness policy.
4:The scheduler checks robots.txt[crawl rules/website], domain rate limits, and per-host concurrency rules.
5:Crawl jobs are published to queues partitioned by domain or host hash.
6:Stateless crawler workers fetch pages with timeouts, size limits, redirects, and retries.
7:Raw HTML, response headers, and fetch metadata are stored in object storage.
8:Parser workers extract title, description, canonical URL, headings, body text, OpenGraph, schema.org types, and content hashes.
9:Topic workers run TF-IDF for low-cost keyword extraction and BERT embeddings/classification for richer topic understanding via internal policy.
10:Final metadata is written to the lookup store, search index, and data lake.
11:Monitoring tracks throughput, queue age, errors, completeness, cost, and freshness.

## Scaling Strategy
The main scaling method is horizontal scaling: add more stateless workers as queue depth grows. Workers should not store local state. Any worker should be able to process any URL job.
  -Vertical scaling is used selectively:
  -Larger CPU instances for high-throughput HTML parsing.
  -Memory-optimized instances for large pages or batch parsing.
  -GPU or inference-optimized instances only for BERT topic enrichment.
A useful sizing example:
  -1 billion URLs in 30 days requires about 386 URLs/second average.
  -With retries, domain throttling, and peak buffers, design for 1,000+ URLs/second.
  -If one worker safely handles 5 URLs/second, the system needs roughly 200 active workers at peak.
  -Autoscaling should be based on queue age, not only CPU.
  
## Queue and Scheduling Design
The queue layer should support retries, delayed jobs, and dead-letter queues. Kafka, SQS, or Pub/Sub can work.
Jobs should be partitioned by domain or host hash so the system can enforce politeness. Without this, a large worker fleet could accidentally overload one domain.
Each crawl job should include:
{
  "crawl_month": "2026-07",
  "url": "https://example.com/page",
  "url_hash": "sha256...",
  "domain": "example.com",
  "attempt": 1,
  "priority": "normal",
  "parser_version": "v1"
}
The crawler should use at-least-once processing. Exactly-once crawling is expensive and unnecessary. Idempotent writes keyed by url_hash, crawl_month, and parser_version make retries safe.

## Storage

- S3/data lake: raw HTML, response headers, screenshots if needed, parser outputs, historical snapshots.
- Metadata store: PostgreSQL, DynamoDB, or Cassandra depending on query patterns and scale, forfast lookup by URL hash or canonical URL.
- Analytics: Store parsed metadata as Parquet tables using Iceberg or Delta Lake. This is best for batch analytics, trend analysis, model evaluation, and reprocessing.
- Cache/dedupe: Redis or DynamoDB for recently seen URL fingerprints and crawl locks.
- Search index: Use OpenSearch or Elasticsearch for searching by URL, title, description, topic, domain, and page type.

## Unified Metadata Schema

The schema should be versioned because extraction logic, topic models, and classification rules will improve over time.
{
  "crawl_month": "2026-07",
  "requested_url": "https://example.com/page",
  "final_url": "https://example.com/page",
  "url_hash": "sha256...",
  "domain": "example.com",
  "status_code": 200,
  "content_type": "text/html",
  "fetched_at": "2026-07-15T10:30:00Z",
  "title": "Example Page Title",
  "description": "Meta description text",
  "canonical_url": "https://example.com/page",
  "language": "en",
  "headings": {
    "h1": ["Main heading"],
    "h2": ["Section heading"]
  },
  "open_graph": {
    "og:title": "Example Page Title",
    "og:type": "article"
  },
  "schema_org_types": ["Article"],
  "body_hash": "sha256...",
  "word_count": 1240,
  "page_type": "article",
  "topics": [
    {"name": "camping gear", "score": 0.91, "method": "bert"},
    {"name": "outdoor safety", "score": 0.78, "method": "tfidf"}
  ],
  "raw_html_uri": "s3://...",
  "parser_version": "v1",
  "topic_model_version": "bert-v1",
  "error": null
}

## Cost Optimization
The biggest cost risks are network traffic, storage, retries, and BERT inference.
Cost controls:
- Run cheap validation before fetching.
- Deduplicate by normalized URL and body hash.
- Do not run BERT on failed, duplicate, non-HTML, or very low-value pages.
- Use TF-IDF for all pages and BERT only for selected pages or changed content.
- Batch BERT inference on GPU/inference instances.
- Use spot instances for stateless crawler workers.
- Compress raw HTML.
- Apply lifecycle policies to raw HTML, for example keep full raw content for 30-90 days, then archive or delete.
- Avoid screenshots and headless browser rendering unless normal HTML fetch fails for important domains.
- Partition Parquet data to reduce analytics scan costs.

## Reliability and Availability
The system should assume failures are normal: domains block requests, pages timeout, queues duplicate messages, and workers crash.
Reliability controls:
- Idempotent writes for crawl results.
- Retry with exponential backoff.
- Dead-letter queue after repeated failures.
- Per-domain circuit breakers for high timeout/429/403 rates.
- Robots.txt cache with expiry.
- Backpressure when queues grow too old.
- Multi-AZ worker deployment.
- Object storage as source of truth for raw artifacts.
- Parser versioning so old pages can be reprocessed without refetching.
- Separate crawl pipeline from read/query APIs so crawling load does not hurt availability.
  
## Monitoring

Track:

- URLs ingested per minute.
- Queue depth and oldest job age.
- Crawl success rate by domain.
- HTTP status distribution.
- Timeout, DNS, TLS, and connection error rates.
- Robots blocked count.
- Fetch latency P50/P95/P99.
- Parse latency P50/P95/P99.
- TF-IDF and BERT enrichment latency.
- BERT GPU utilization and batch size.
- Metadata completeness rate.
- Raw HTML storage growth.
- Cost per million URLs.
- Dead-letter queue volume.
- Worker CPU, memory, network, and restart count.

Recommended tools:
- CloudWatch or Google Cloud Monitoring for infrastructure metrics.
- Prometheus + Grafana for service dashboards.
- OpenTelemetry for distributed traces.
- OpenSearch/ELK for logs.
- PagerDuty/Opsgenie for alerts.
- Athena/BigQuery/Snowflake for batch quality checks.

## SLOs and SLAs

Example SLOs:

- 99% of accepted crawl jobs start within 15 minutes.
- 95% of successful fetches complete parsing within 30 seconds.
- 99.9% API availability for result lookups.
- Less than 0.1% duplicate crawl jobs per day after normalization.

SLAs should be looser than SLOs and aligned to customer contracts, for example daily batch completion by a published reporting window.Metadata lookup API available 99.5% monthly. Reprocessing requests completed within an agreed batch window.

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
