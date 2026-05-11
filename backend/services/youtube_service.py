from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from yt_dlp import YoutubeDL

from backend.config import MAX_SEARCH_RESULTS
from backend.models import SearchResult
from backend.utils import format_duration, slugify_filename

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    title: str
    video_id: str
    duration_seconds: int | None
    path: Path


class YtDlpLogger:
    def debug(self, message: str) -> None:
        if message.startswith("[debug]"):
            return
        logger.info("yt-dlp: %s", message)

    def warning(self, message: str) -> None:
        logger.warning("yt-dlp: %s", message)

    def error(self, message: str) -> None:
        logger.error("yt-dlp: %s", message)


class SafeYoutubeDL(YoutubeDL):
    def to_stderr(self, message, only_once=False):  # type: ignore[override]
        if message:
            logger.warning("yt-dlp stderr: %s", message)

    def to_stdout(self, message, skip_eol=False, quiet=None):  # type: ignore[override]
        if message:
            logger.info("yt-dlp stdout: %s", message)

    def report_warning(self, message, *args, **kwargs):  # type: ignore[override]
        if message:
            logger.warning("yt-dlp warning: %s", message)


class NullOutputStream:
    encoding = "utf-8"

    def write(self, data):
        return len(data) if data is not None else 0

    def flush(self):
        return None

    def isatty(self):
        return False


class YouTubeService:
    def _create_ydl(self, options: dict) -> SafeYoutubeDL:
        ydl = SafeYoutubeDL(options)
        sink = NullOutputStream()
        ydl._out_files.out = sink
        ydl._out_files.error = sink
        ydl._screen_file = sink
        return ydl

    def search(self, query: str, max_results: int = MAX_SEARCH_RESULTS) -> list[SearchResult]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "noplaylist": True,
            "nocheckcertificate": True,
            "logger": YtDlpLogger(),
        }

        search_term = f"ytsearch{max_results}:{query}"
        with self._create_ydl(options) as ydl:
            info = ydl.extract_info(search_term, download=False)

        items: list[SearchResult] = []
        for entry in info.get("entries", []):
            if not entry:
                continue
            duration = entry.get("duration")
            thumbnails = entry.get("thumbnails") or []
            thumbnail = thumbnails[-1].get("url") if thumbnails else entry.get("thumbnail")
            items.append(
                SearchResult(
                    video_id=entry.get("id", ""),
                    title=entry.get("title") or "Untitled video",
                    url=entry.get("webpage_url") or f"https://www.youtube.com/watch?v={entry.get('id', '')}",
                    thumbnail=thumbnail,
                    duration_seconds=duration,
                    duration_label=format_duration(duration),
                    uploader=entry.get("channel") or entry.get("uploader"),
                )
            )

        return items

    def download(
        self,
        *,
        video_id: str,
        title: str,
        target_dir: Path,
        progress_callback: callable,
    ) -> DownloadResult:
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_title = slugify_filename(title, fallback=video_id)
        final_template = target_dir / f"{safe_title}.%(ext)s"
        download_url = f"https://www.youtube.com/watch?v={video_id}"

        logger.info("Downloading video %s", video_id)

        def hook(payload: dict) -> None:
            status = payload.get("status")
            if status == "downloading":
                total_bytes = payload.get("total_bytes") or payload.get("total_bytes_estimate") or 0
                downloaded_bytes = payload.get("downloaded_bytes") or 0
                ratio = downloaded_bytes / total_bytes if total_bytes else 0
                speed = payload.get("speed")
                speed_label = f"{round(speed / 1024 / 1024, 2)} MB/s" if speed else "calculating speed"
                progress_callback(ratio, f"Downloading source video ({speed_label})")
            elif status == "finished":
                progress_callback(1.0, "Download complete, merging streams")

        options = {
            "format": "bv*+ba/b",
            "merge_output_format": "mp4",
            "outtmpl": str(final_template),
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [hook],
            "noplaylist": True,
            "nocheckcertificate": True,
            "retries": 3,
            "logger": YtDlpLogger(),
        }

        with self._create_ydl(options) as ydl:
            info = ydl.extract_info(download_url, download=True)

        candidates = sorted(target_dir.glob(f"{safe_title}*"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not candidates:
            raise FileNotFoundError("yt-dlp did not produce a downloaded file")

        final_path = candidates[0]
        normalized_path = target_dir / f"{safe_title}.mp4"
        if final_path != normalized_path:
            final_path.replace(normalized_path)
            final_path = normalized_path

        return DownloadResult(
            title=info.get("title") or title,
            video_id=info.get("id") or video_id,
            duration_seconds=info.get("duration"),
            path=final_path,
        )
