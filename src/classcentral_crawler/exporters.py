from __future__ import annotations

import csv
from pathlib import Path

import orjson

from .models import CourseRecord


def export_json(records: list[CourseRecord], path: Path) -> None:
    payload = [r.to_dict() for r in records]
    path.write_bytes(orjson.dumps(payload, option=orjson.OPT_INDENT_2))


def export_csv(records: list[CourseRecord], path: Path) -> None:
    rows = [r.to_dict() for r in records]
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
