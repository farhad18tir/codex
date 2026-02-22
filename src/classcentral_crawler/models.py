from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CourseRecord:
    url: str
    title: str | None = None
    provider_platform: str | None = None
    university: str | None = None
    instructors: list[str] = field(default_factory=list)
    description: str | None = None
    rating: float | None = None
    review_count: int | None = None
    language: str | None = None
    level: str | None = None
    duration: str | None = None
    price: str | None = None
    certificate_availability: str | None = None
    enrollment_link: str | None = None
    image_url: str | None = None
    raw_jsonld: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["instructors"] = "; ".join(self.instructors)
        return data
