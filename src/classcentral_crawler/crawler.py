from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from typing import Any
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import BrowserContext, Page, async_playwright
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .config import CrawlConfig
from .models import CourseRecord
from .parsers import parse_course
from .rate_limiter import AsyncRateLimiter

logger = logging.getLogger(__name__)


class ClassCentralCrawler:
    def __init__(self, config: CrawlConfig) -> None:
        self.config = config
        self.rate_limiter = AsyncRateLimiter(config.rate_limit_per_sec)
        self.seen_urls: set[str] = set()

    @retry(
        reraise=True,
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(4),
        retry=retry_if_exception_type(httpx.HTTPError),
    )
    async def _fetch(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        await self.rate_limiter.wait()
        response = await client.get(url)
        response.raise_for_status()
        return response

    @staticmethod
    def _course_links_from_html(html: str, base_url: str) -> set[str]:
        soup = BeautifulSoup(html, "lxml")
        urls: set[str] = set()
        for a in soup.select("a[href*='/course/']"):
            href = a.get("href")
            if not href:
                continue
            abs_url = urljoin(base_url, href.split("?")[0])
            urls.add(abs_url)
        return urls

    async def _discover_network_api(self, page: Page) -> list[str]:
        found: list[str] = []

        def on_response(resp: Any) -> None:
            req = resp.request
            resource_type = req.resource_type
            if resource_type not in {"xhr", "fetch"}:
                return
            u = resp.url
            if "classcentral.com" in u and any(x in u.lower() for x in ["search", "course", "catalog", "api"]):
                found.append(u)

        page.on("response", on_response)
        await page.goto(self.config.listing_url, wait_until="networkidle")
        await page.mouse.wheel(0, 5000)
        await page.wait_for_timeout(2000)
        deduped = sorted(set(found))
        logger.info("Potential API endpoints discovered: %s", deduped[:10])
        return deduped

    async def _collect_listing_urls_dom(self, page: Page) -> set[str]:
        await page.goto(self.config.listing_url, wait_until="networkidle")
        # Load-more / infinite scroll
        for _ in range(30):
            load_more = page.locator("button:has-text('Load more'), a:has-text('Load more')")
            if await load_more.count() > 0 and await load_more.first.is_visible():
                await load_more.first.click()
                await page.wait_for_timeout(1500)
                continue
            await page.mouse.wheel(0, 7000)
            await page.wait_for_timeout(1200)

        urls = self._course_links_from_html(await page.content(), self.config.base_url)

        # traditional pagination by query ?page=
        for p in range(2, self.config.max_listing_pages + 1):
            paged = f"{self.config.listing_url}?page={p}"
            await page.goto(paged, wait_until="domcontentloaded")
            html = await page.content()
            page_urls = self._course_links_from_html(html, self.config.base_url)
            if not page_urls:
                break
            before = len(urls)
            urls.update(page_urls)
            if len(urls) == before:
                stagnant = True
            else:
                stagnant = False
            if stagnant and p > 5:
                break
        return urls

    async def _collect_listing_urls_api(self, client: httpx.AsyncClient, endpoints: Iterable[str]) -> set[str]:
        urls: set[str] = set()
        for ep in endpoints:
            parsed = urlparse(ep)
            query = parse_qs(parsed.query)
            if "page" not in query:
                query["page"] = ["1"]
            for page in range(1, self.config.max_listing_pages + 1):
                query["page"] = [str(page)]
                qs = "&".join(f"{k}={v[0]}" for k, v in query.items())
                endpoint = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{qs}"
                try:
                    response = await self._fetch(client, endpoint)
                except Exception:
                    break
                try:
                    payload = response.json()
                except json.JSONDecodeError:
                    break
                links = self._extract_course_links_from_json(payload)
                if not links:
                    break
                urls.update(links)
        return urls

    def _extract_course_links_from_json(self, payload: Any) -> set[str]:
        found: set[str] = set()

        def walk(node: Any) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, str) and "/course/" in v:
                        found.add(urljoin(self.config.base_url, v.split("?")[0]))
                    if k.lower() in {"slug", "course_slug"} and isinstance(v, str):
                        found.add(urljoin(self.config.base_url, f"/course/{v}"))
                    walk(v)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return found

    async def collect_course_urls(self, context: BrowserContext) -> set[str]:
        page = await context.new_page()
        endpoints = await self._discover_network_api(page)
        urls = await self._collect_listing_urls_dom(page)
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True) as client:
            api_urls = await self._collect_listing_urls_api(client, endpoints)
        urls.update(api_urls)
        await page.close()
        self.seen_urls = urls
        logger.info("Collected %s unique course URLs", len(urls))
        return urls

    async def _scrape_single_course(self, client: httpx.AsyncClient, url: str) -> CourseRecord | None:
        try:
            response = await self._fetch(client, url)
            return parse_course(url, response.text, self.config.base_url)
        except Exception as exc:
            logger.warning("Failed %s: %s", url, exc)
            return None

    async def scrape_courses(self, urls: Iterable[str]) -> list[CourseRecord]:
        sem = asyncio.Semaphore(self.config.concurrency)

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True) as client:
            async def run(url: str) -> CourseRecord | None:
                async with sem:
                    return await self._scrape_single_course(client, url)

            results = await asyncio.gather(*(run(url) for url in urls))
        return [r for r in results if r]

    async def run(self) -> list[CourseRecord]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.config.headless)
            context = await browser.new_context()
            urls = await self.collect_course_urls(context)
            records = await self.scrape_courses(sorted(urls))
            await context.close()
            await browser.close()
        return records
