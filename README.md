# Class Central Crawler (Playwright + Python)

Robust crawler for `classcentral.com` that:
- Crawls listing pages (pagination + load-more/infinite-scroll patterns)
- Detects potential internal API endpoints from browser network traffic
- Prefers API extraction when possible, then falls back to DOM extraction
- Visits each course page and extracts structured fields
- Parses JSON-LD (`application/ld+json`) when available
- Uses retry logic + rate limiting
- Deduplicates URLs
- Exports to JSON and CSV

## Project structure

```text
.
├── requirements.txt
├── README.md
└── src/
    └── classcentral_crawler/
        ├── __init__.py
        ├── config.py
        ├── crawler.py
        ├── exporters.py
        ├── logger.py
        ├── main.py
        ├── models.py
        ├── parsers.py
        └── rate_limiter.py
```

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
```

## Run

```bash
PYTHONPATH=src python -m classcentral_crawler.main --output-dir output --max-pages 200 --concurrency 5 --rate 1.5
```

Optional:
- `--headed`: run browser with UI
- `--max-pages`: cap listing/API pagination depth
- `--concurrency`: concurrent detail-page workers
- `--rate`: global request rate (req/sec)

## Extracted fields

- `title`
- `provider_platform`
- `university`
- `instructors`
- `description`
- `rating`
- `review_count`
- `language`
- `level`
- `duration`
- `price`
- `certificate_availability`
- `enrollment_link`
- `image_url`
- `raw_jsonld`

## Output

- `output/courses.json`
- `output/courses.csv`

## Notes on robustness

- Listing URL extraction uses both scrolling/load-more and page-based `?page=` probing.
- Browser network responses are observed for candidate API endpoints (`xhr/fetch`), and JSON payloads are recursively scanned for course links/slugs.
- Tenacity-based retries are enabled for HTTP requests.
- Async rate limiter smooths request burst behavior.
- URL deduplication prevents repeated course crawls.
