from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class CrawlConfig:
    base_url: str = "https://www.classcentral.com"
    listing_path: str = "/subject"
    output_dir: Path = Path("output")
    max_listing_pages: int = 200
    headless: bool = True
    concurrency: int = 5
    rate_limit_per_sec: float = 1.5
    max_retries: int = 4
    timeout_seconds: int = 35

    @property
    def listing_url(self) -> str:
        return f"{self.base_url}{self.listing_path}"
