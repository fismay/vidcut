from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ChunkInfo:
    index: int
    start: float
    duration: float
    path: Path


class FFmpegService:
    SHORTS_WIDTH = 1080
    SHORTS_HEIGHT = 1920

    def run(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        logger.info("Running command: %s", " ".join(args))
        return subprocess.run(args, check=True, capture_output=True, text=True)

    def get_duration(self, video_path: Path) -> float:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(video_path),
        ]
        result = self.run(command)
        return float(result.stdout.strip())

    def has_audio_stream(self, video_path: Path) -> bool:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "csv=p=0",
            str(video_path),
        ]
        result = self.run(command)
        return bool(result.stdout.strip())

    def copy_video(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-c",
            "copy",
            str(destination),
        ]
        self.run(command)

    def remove_segments(self, source: Path, keep_ranges: list[tuple[float, float]], destination: Path) -> None:
        if not keep_ranges:
            raise ValueError("No keep ranges were produced after SponsorBlock filtering")

        full_duration = self.get_duration(source)
        if len(keep_ranges) == 1 and keep_ranges[0][0] <= 0.01 and abs(keep_ranges[0][1] - full_duration) <= 0.25:
            self.copy_video(source, destination)
            return

        destination.parent.mkdir(parents=True, exist_ok=True)
        has_audio = self.has_audio_stream(source)
        filter_parts: list[str] = []
        concat_inputs: list[str] = []

        for index, (start, end) in enumerate(keep_ranges):
            filter_parts.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[v{index}]")
            concat_inputs.append(f"[v{index}]")
            if has_audio:
                filter_parts.append(f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS[a{index}]")
                concat_inputs.append(f"[a{index}]")

        if has_audio:
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(keep_ranges)}:v=1:a=1[outv][outa]")
        else:
            filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(keep_ranges)}:v=1:a=0[outv]")

        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[outv]",
        ]

        if has_audio:
            command.extend(["-map", "[outa]"])

        command.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(destination),
            ]
        )
        self.run(command)

    def split_into_chunks(self, source: Path, output_dir: Path, stem: str, chunk_seconds: int) -> list[ChunkInfo]:
        duration = self.get_duration(source)
        output_dir.mkdir(parents=True, exist_ok=True)

        chunks: list[ChunkInfo] = []
        cursor = 0.0
        index = 1

        while cursor < duration - 0.25:
            current_duration = min(float(chunk_seconds), max(duration - cursor, 0.0))
            chunk_path = output_dir / f"{stem}_chunk{index:02d}.mp4"
            command = [
                "ffmpeg",
                "-y",
                "-ss",
                f"{cursor:.3f}",
                "-i",
                str(source),
                "-t",
                f"{current_duration:.3f}",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-c:a",
                "aac",
                "-movflags",
                "+faststart",
                str(chunk_path),
            ]
            self.run(command)
            chunks.append(ChunkInfo(index=index, start=cursor, duration=current_duration, path=chunk_path))
            cursor += current_duration
            index += 1

        return chunks

    def extract_audio(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(destination),
        ]
        self.run(command)

    def render_vertical_short(self, source: Path, destination: Path, subtitles_path: Path | None = None) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        filter_complex = self._build_vertical_filter(subtitles_path)
        has_audio = self.has_audio_stream(source)
        command = [
            "ffmpeg",
            "-y",
            "-i",
            str(source),
            "-filter_complex",
            filter_complex,
            "-map",
            "[vout]",
        ]

        if has_audio:
            command.extend(["-map", "0:a?"])

        command.extend(["-c:v", "libx264", "-preset", "medium", "-crf", "18"])
        if has_audio:
            command.extend(["-c:a", "aac"])
        command.extend(["-movflags", "+faststart", str(destination)])
        self.run(command)

    def _build_vertical_filter(self, subtitles_path: Path | None) -> str:
        base = (
            f"[0:v]split=2[bgsrc][fgsrc];"
            f"[bgsrc]scale={self.SHORTS_WIDTH}:{self.SHORTS_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={self.SHORTS_WIDTH}:{self.SHORTS_HEIGHT},boxblur=28:10[bg];"
            f"[fgsrc]scale={self.SHORTS_WIDTH}:{self.SHORTS_HEIGHT}:force_original_aspect_ratio=decrease[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
        )

        if subtitles_path is None:
            return f"{base}[vout]"

        subtitle_filter_path = subtitles_path.as_posix().replace(":", r"\:").replace("'", r"\'")
        subtitle_style = (
            "Alignment=5,"
            "FontName=Arial,"
            "FontSize=22,"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BackColour=&H64000000,"
            "BorderStyle=1,"
            "Outline=3,"
            "Shadow=0,"
            "MarginV=0"
        )
        return f"{base},subtitles='{subtitle_filter_path}':force_style='{subtitle_style}'[vout]"
