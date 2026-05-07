from __future__ import annotations

import math
import re
from pathlib import Path


def slugify_filename(value: str, fallback: str = "video") -> str:
    cleaned = re.sub(r"[^\w\s.-]", "", value, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = cleaned.strip("._")
    return cleaned[:80] or fallback


def format_duration(seconds: int | None) -> str:
    if seconds is None:
        return "Unknown"

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"

    return f"{minutes}:{secs:02d}"


def file_size_mb(path: Path) -> float:
    size = path.stat().st_size / (1024 * 1024)
    return math.floor(size * 100) / 100


def clamp_progress(value: float) -> float:
    return max(0.0, min(100.0, round(value, 2)))
