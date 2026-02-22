from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .models import CourseRecord


def _text(soup: BeautifulSoup, selector: str) -> str | None:
    node = soup.select_one(selector)
    if not node:
        return None
    text = node.get_text(" ", strip=True)
    return text or None


def _extract_jsonld(soup: BeautifulSoup) -> dict[str, Any] | None:
    for script in soup.select("script[type='application/ld+json']"):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in {"Course", "EducationalOccupationalProgram", "Product"}:
                return item
    return None


def parse_course(url: str, html: str, base_url: str) -> CourseRecord:
    soup = BeautifulSoup(html, "lxml")
    jsonld = _extract_jsonld(soup)

    title = _text(soup, "h1") or (jsonld or {}).get("name")
    description = _text(soup, "meta[name='description']") or (jsonld or {}).get("description")
    if description and description.startswith("<meta"):
        description = None

    if not description:
        meta_desc = soup.select_one("meta[name='description']")
        if meta_desc:
            description = meta_desc.get("content")

    instructors = [n.get_text(" ", strip=True) for n in soup.select("[data-name='instructors'] a, .instructor a, .course-instructors a")]
    instructors = [x for x in instructors if x]
    if not instructors and jsonld:
        teaches = jsonld.get("provider") or jsonld.get("creator")
        if isinstance(teaches, dict):
            name = teaches.get("name")
            if name:
                instructors = [name]

    provider = _text(soup, "[data-name='provider'] a, .course-provider a, a[data-track*='provider']")
    university = _text(soup, "[data-name='institution'] a, .course-institution a")

    rating_text = _text(soup, "[itemprop='ratingValue'], .rating .value")
    rating = None
    if rating_text:
        match = re.search(r"\d+(?:\.\d+)?", rating_text)
        if match:
            rating = float(match.group(0))
    elif jsonld and isinstance(jsonld.get("aggregateRating"), dict):
        rv = jsonld["aggregateRating"].get("ratingValue")
        if rv:
            rating = float(rv)

    review_count = None
    review_text = _text(soup, "[itemprop='reviewCount'], .rating .count")
    if review_text:
        digits = re.sub(r"\D", "", review_text)
        if digits:
            review_count = int(digits)
    elif jsonld and isinstance(jsonld.get("aggregateRating"), dict):
        rc = jsonld["aggregateRating"].get("reviewCount")
        if rc:
            review_count = int(str(rc))

    enrollment_link = None
    for selector in ["a[data-name='go-to-class']", "a.btn-go-to-class", "a[href*='classcentral.com/redirect']"]:
        node = soup.select_one(selector)
        if node and node.get("href"):
            enrollment_link = urljoin(base_url, node["href"])
            break

    image_url = None
    og_img = soup.select_one("meta[property='og:image']")
    if og_img:
        image_url = og_img.get("content")
    if not image_url and jsonld and isinstance(jsonld.get("image"), str):
        image_url = jsonld.get("image")

    def grab_fact(label: str) -> str | None:
        node = soup.find(string=re.compile(label, re.I))
        if not node:
            return None
        if node.parent:
            text = node.parent.get_text(" ", strip=True)
            text = re.sub(label, "", text, flags=re.I).strip(" :-")
            if text and len(text) < 200:
                return text
        return None

    language = grab_fact("Language")
    level = grab_fact("Level")
    duration = grab_fact("Duration")
    price = grab_fact("Price")
    certificate = grab_fact("Certificate")

    if jsonld and not price:
        offers = jsonld.get("offers")
        if isinstance(offers, dict):
            val = offers.get("price")
            curr = offers.get("priceCurrency")
            if val is not None:
                price = f"{curr or ''} {val}".strip()

    return CourseRecord(
        url=url,
        title=title,
        provider_platform=provider,
        university=university,
        instructors=instructors,
        description=description,
        rating=rating,
        review_count=review_count,
        language=language,
        level=level,
        duration=duration,
        price=price,
        certificate_availability=certificate,
        enrollment_link=enrollment_link,
        image_url=image_url,
        raw_jsonld=jsonld,
    )
