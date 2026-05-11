from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import requests

from backend.config import SPONSORBLOCK_API_URL, SPONSORBLOCK_CATEGORIES

logger = logging.getLogger(__name__)


@dataclass
class SponsorSegment:
    start: float
    end: float
    category: str


class SponsorBlockService:
    def fetch_segments(self, video_id: str) -> list[SponsorSegment]:
        params = {
            "videoID": video_id,
            "categories": json.dumps(SPONSORBLOCK_CATEGORIES),
        }

        response = requests.get(SPONSORBLOCK_API_URL, params=params, timeout=15)
        if response.status_code == 404:
            return []

        response.raise_for_status()
        payload = response.json()

        segments: list[SponsorSegment] = []
        for item in payload:
            segment = item.get("segment") or []
            if len(segment) != 2:
                continue
            start = max(0.0, float(segment[0]))
            end = max(start, float(segment[1]))
            segments.append(SponsorSegment(start=start, end=end, category=item.get("category", "unknown")))

        return self._merge_segments(segments)

    def build_keep_ranges(self, duration: float, segments: list[SponsorSegment]) -> list[tuple[float, float]]:
        if not segments:
            return [(0.0, duration)]

        keep_ranges: list[tuple[float, float]] = []
        cursor = 0.0

        for segment in segments:
            if segment.start > cursor:
                keep_ranges.append((cursor, min(segment.start, duration)))
            cursor = max(cursor, min(segment.end, duration))

        if cursor < duration:
            keep_ranges.append((cursor, duration))

        return [(start, end) for start, end in keep_ranges if end - start > 0.3]

    def _merge_segments(self, segments: list[SponsorSegment]) -> list[SponsorSegment]:
        if not segments:
            return []

        ordered = sorted(segments, key=lambda item: item.start)
        merged = [ordered[0]]

        for current in ordered[1:]:
            previous = merged[-1]
            if current.start <= previous.end + 0.05:
                previous.end = max(previous.end, current.end)
                previous.category = f"{previous.category},{current.category}"
            else:
                merged.append(current)

        logger.info("SponsorBlock returned %s merged segments", len(merged))
        return merged
