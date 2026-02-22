from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .config import CrawlConfig
from .crawler import ClassCentralCrawler
from .exporters import export_csv, export_json
from .logger import configure_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Crawl Class Central courses")
    parser.add_argument("--output-dir", default="output")
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--rate", type=float, default=1.5, help="Requests per second")
    parser.add_argument("--headed", action="store_true", help="Run browser with UI")
    return parser.parse_args()


async def _run() -> None:
    args = parse_args()
    configure_logging()

    config = CrawlConfig(
        output_dir=Path(args.output_dir),
        max_listing_pages=args.max_pages,
        concurrency=args.concurrency,
        rate_limit_per_sec=args.rate,
        headless=not args.headed,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)
    crawler = ClassCentralCrawler(config)
    records = await crawler.run()

    export_json(records, config.output_dir / "courses.json")
    export_csv(records, config.output_dir / "courses.csv")

    print(f"Scraped {len(records)} courses")
    print(f"JSON: {config.output_dir / 'courses.json'}")
    print(f"CSV:  {config.output_dir / 'courses.csv'}")


if __name__ == "__main__":
    asyncio.run(_run())
