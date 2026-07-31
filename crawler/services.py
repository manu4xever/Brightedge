import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from bs4.element import Comment

try:
    from keybert import KeyBERT
except ImportError:
    KeyBERT = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import Pipeline
    from sklearn.svm import LinearSVC
except ImportError:
    TfidfVectorizer = None
    Pipeline = None
    LinearSVC = None


STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "and",
    "are",
    "because",
    "been",
    "being",
    "but",
    "can",
    "for",
    "from",
    "have",
    "how",
    "into",
    "more",
    "not",
    "our",
    "page",
    "that",
    "the",
    "their",
    "this",
    "with",
    "your",
}

CLASSIFIER_LABELS = ("product", "article", "news", "category", "unknown")
MIN_CLASSIFIER_WORDS = 12
MIN_CLASSIFIER_MARGIN = 0.10
FETCH_RETRIES = 1
FETCH_TIMEOUT = httpx.Timeout(connect=30, read=60, write=30, pool=10)

TRAINING_EXAMPLES = [
    (
        "product",
        "Product Offer AggregateRating price sku add to cart buy durable compact toaster kitchen appliance "
        "customer reviews in stock free shipping product page",
    ),
    (
        "product",
        "Wireless headphones product detail page sale price cart checkout specifications color size reviews "
        "brand model ecommerce offer",
    ),
    (
        "product",
        "Running shoe product page price sizes add to bag sku product images ratings shipping returns",
    ),
    (
        "article",
        "Article BlogPosting author published date guide how to introduce friend outdoors camping tips blog post "
        "longform story advice",
    ),
    (
        "article",
        "Tutorial article by author explains strategy lessons practical examples editorial blog content read more",
    ),
    (
        "article",
        "Opinion article essay analysis feature story published writer magazine blog guide",
    ),
    (
        "news",
        "NewsArticle breaking news latest report cnn technology jobs ai study today updated correspondent "
        "headline newsroom",
    ),
    (
        "news",
        "Live updates world news politics investigation officials said report published tuesday news article",
    ),
    (
        "news",
        "Market news latest development reporters coverage breaking story local national news",
    ),
    (
        "category",
        "Category collection listing products grid filters sort by price brand breadcrumbs shop all kitchen toasters",
    ),
    (
        "category",
        "Collection page browse category results product listing pagination filter sizes colors departments",
    ),
    (
        "category",
        "Search results listing category page items grid refine sort compare products",
    ),
    (
        "unknown",
        "Homepage welcome company overview contact privacy terms about us navigation landing page general information",
    ),
    (
        "unknown",
        "Example domain reserved for documentation examples simple webpage without commerce article or news content",
    ),
    (
        "unknown",
        "Login account support help center dashboard settings profile generic web application page",
    ),
]


def crawl_url(url):
    response = fetch_html(url)
    response.raise_for_status()
    html = response.text
    metadata = extract_metadata(html, str(response.url))
    metadata["url"] = url
    metadata["final_url"] = str(response.url)
    metadata["status_code"] = response.status_code
    return metadata


def fetch_html(url):
    last_error = None
    for _ in range(FETCH_RETRIES):
        try:
            return httpx.get(
                url,
                follow_redirects=True,
                timeout=FETCH_TIMEOUT,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/126.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Cache-Control": "no-cache",
                },
            )
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            last_error = exc
    raise last_error


def extract_metadata(html, base_url):
    soup = BeautifulSoup(html, "lxml")
    visible_text = extract_visible_text(soup)
    headings = extract_headings(soup)
    description = meta_content(soup, attrs={"name": "description"})
    canonical_url = extract_canonical_url(soup, base_url)
    open_graph = extract_open_graph(soup)
    schema_types = extract_schema_types(soup, html)

    metadata = {
        "title": title_text(soup),
        "description": description,
        "canonical_url": canonical_url,
        "language": extract_language(soup),
        "headings": headings,
        "open_graph": open_graph,
        "schema_types": schema_types,
        "visible_text": visible_text,
        "word_count": len(words(visible_text)),
        "body_hash": hashlib.sha256(visible_text.encode("utf-8")).hexdigest(),
    }
    metadata["page_type"] = classify_page(metadata, base_url)
    metadata["topics"] = extract_topics(metadata)
    return metadata


def title_text(soup):
    if soup.title and soup.title.string:
        return normalize_space(soup.title.string)[:500]
    og_title = meta_content(soup, attrs={"property": "og:title"})
    return og_title[:500]


def meta_content(soup, attrs):
    tag = soup.find("meta", attrs=attrs)
    if not tag:
        return ""
    return normalize_space(tag.get("content", ""))


def extract_canonical_url(soup, base_url):
    tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if not tag or not tag.get("href"):
        return ""
    return urljoin(base_url, tag["href"])


def extract_language(soup):
    html_tag = soup.find("html")
    if html_tag:
        return normalize_space(html_tag.get("lang") or html_tag.get("xml:lang") or "")
    return ""


def extract_headings(soup):
    return {
        f"h{level}": [normalize_space(tag.get_text(" ", strip=True)) for tag in soup.find_all(f"h{level}")]
        for level in range(1, 7)
    }


def extract_open_graph(soup):
    fields = {}
    for tag in soup.find_all("meta"):
        prop = tag.get("property") or tag.get("name")
        if prop and prop.startswith("og:"):
            fields[prop] = normalize_space(tag.get("content", ""))
    return fields


def extract_schema_types(soup, html=""):
    found = set()
    for raw_jsonld in re.findall(
        r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
        html or "",
        flags=re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(raw_jsonld.strip())
        except json.JSONDecodeError:
            continue
        collect_jsonld_types(data, found)

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.get_text(strip=True) or "{}")
        except json.JSONDecodeError:
            continue
        collect_jsonld_types(data, found)

    for tag in soup.find_all(attrs={"itemtype": True}):
        itemtype = tag.get("itemtype", "")
        if itemtype:
            found.add(itemtype.rstrip("/").split("/")[-1])

    return sorted(found)


def collect_jsonld_types(data, found):
    if isinstance(data, list):
        for item in data:
            collect_jsonld_types(item, found)
        return
    if not isinstance(data, dict):
        return

    json_type = data.get("@type")
    if isinstance(json_type, list):
        found.update(str(item) for item in json_type)
    elif json_type:
        found.add(str(json_type))

    for value in data.values():
        if isinstance(value, (dict, list)):
            collect_jsonld_types(value, found)


def extract_visible_text(soup):
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    parts = []
    for text_node in soup.find_all(string=True):
        if isinstance(text_node, Comment):
            continue
        text = normalize_space(text_node)
        if text and text_node.parent.name not in {"head", "title", "meta", "link"}:
            parts.append(text)
    return normalize_space(" ".join(parts))


def classify_page(metadata, url):
    text = classifier_text(metadata, url)
    heuristic_label = heuristic_classify_page(text)
    classifier = get_page_classifier()

    if classifier is None or len(words(text)) < MIN_CLASSIFIER_WORDS:
        return heuristic_label

    prediction = classifier.predict([text])[0]
    margin = classifier_margin(classifier, text)
    if margin < MIN_CLASSIFIER_MARGIN:
        return heuristic_label if heuristic_label != "unknown" else "unknown"
    return prediction


def classifier_text(metadata, url):
    headings = " ".join(sum(metadata.get("headings", {}).values(), []))
    return normalize_space(
        " ".join(
            [
                metadata.get("title", ""),
                metadata.get("description", ""),
                url,
                metadata.get("canonical_url", ""),
                " ".join(metadata.get("schema_types", [])),
                metadata.get("open_graph", {}).get("og:type", ""),
                headings,
                metadata.get("visible_text", "")[:5000],
            ]
        )
    ).lower()


@lru_cache(maxsize=1)
def get_page_classifier():
    if not all([TfidfVectorizer, Pipeline, LinearSVC]):
        return None

    labels = [label for label, _ in TRAINING_EXAMPLES]
    texts = [text for _, text in TRAINING_EXAMPLES]
    classifier = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                    stop_words="english",
                ),
            ),
            ("model", LinearSVC(class_weight="balanced", random_state=42)),
        ]
    )
    classifier.fit(texts, labels)
    return classifier


def classifier_margin(classifier, text):
    scores = classifier.decision_function([text])[0]
    if not hasattr(scores, "__len__"):
        return abs(float(scores))
    ranked = sorted(float(score) for score in scores)
    if len(ranked) < 2:
        return abs(ranked[-1])
    return ranked[-1] - ranked[-2]


def heuristic_classify_page(text):
    if any(term in text for term in ["product", "sku", "price", "offer", "add to cart", "/product", "/p/"]):
        return "product"
    if any(term in text for term in ["newsarticle", "breaking news", "latest news", "/news/"]):
        return "news"
    if any(term in text for term in ["article", "blogposting", "author", "published", "/blog/", "/article/"]):
        return "article"
    if any(term in text for term in ["category", "collection", "listing", "sort by", "filter", "/category/", "/collections/"]):
        return "category"
    return "unknown"


def extract_topics(metadata, limit=12):
    topic_text = normalize_space(
        " ".join(
            [
                metadata.get("title", ""),
                metadata.get("description", ""),
                " ".join(sum(metadata.get("headings", {}).values(), [])),
                metadata.get("visible_text", "")[:8000],
            ]
        )
    )

    keybert_model = get_keybert_model()
    if keybert_model and len(words(topic_text)) >= 8:
        try:
            keywords = keybert_model.extract_keywords(
                topic_text,
                keyphrase_ngram_range=(1, 2),
                stop_words="english",
                use_mmr=True,
                diversity=0.45,
                top_n=limit * 2,
            )
            topics = dedupe_topics([phrase for phrase, _ in keywords], limit)
            if topics:
                return topics
        except Exception:
            pass

    return fallback_topics(metadata, limit)


@lru_cache(maxsize=1)
def get_keybert_model():
    if KeyBERT is None:
        return None
    try:
        return KeyBERT()
    except Exception:
        return None


def fallback_topics(metadata, limit=12):
    weighted_text = " ".join(
        [
            repeat_text(metadata.get("title", ""), 4),
            repeat_text(metadata.get("description", ""), 3),
            repeat_text(" ".join(sum(metadata.get("headings", {}).values(), [])), 2),
            metadata.get("visible_text", ""),
        ]
    ).lower()
    tokens = [
        word
        for word in words(weighted_text)
        if len(word) > 3 and word not in STOPWORDS and not word.isdigit()
    ]
    candidates = tokens + [
        f"{tokens[index]} {tokens[index + 1]}"
        for index in range(len(tokens) - 1)
        if tokens[index] != tokens[index + 1]
    ]
    counts = Counter(candidates)
    return dedupe_topics([topic for topic, _ in counts.most_common(limit * 3)], limit)


def repeat_text(value, count):
    return " ".join([value] * count)


def dedupe_topics(topics, limit):
    cleaned = []
    seen = set()
    for topic in topics:
        normalized = normalize_space(topic).lower()
        if not normalized or normalized in STOPWORDS or normalized in seen:
            continue
        if any(part in STOPWORDS for part in normalized.split()) and len(normalized.split()) == 1:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
        if len(cleaned) == limit:
            break
    return cleaned


def words(text):
    return re.findall(r"[a-zA-Z][a-zA-Z0-9'-]*", text or "")


def normalize_space(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()
