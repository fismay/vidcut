from __future__ import annotations

import gc
import logging
from pathlib import Path

from faster_whisper import WhisperModel

from backend.config import MODEL_CACHE_DIR, WHISPER_COMPUTE_TYPE, WHISPER_CPU_THREADS, WHISPER_DEVICE, WHISPER_MODEL
from backend.services.ffmpeg_service import FFmpegService

logger = logging.getLogger(__name__)


class SubtitleService:
    def __init__(self, ffmpeg_service: FFmpegService) -> None:
        self._ffmpeg = ffmpeg_service
        self._model: WhisperModel | None = None

    def _get_model(self) -> WhisperModel:
        if self._model is None:
            logger.info("Loading faster-whisper model '%s' on %s", WHISPER_MODEL, WHISPER_DEVICE)
            self._model = WhisperModel(
                WHISPER_MODEL,
                device=WHISPER_DEVICE,
                compute_type=WHISPER_COMPUTE_TYPE,
                cpu_threads=WHISPER_CPU_THREADS,
                download_root=str(MODEL_CACHE_DIR),
            )
        return self._model

    def transcribe_to_srt(self, source_video: Path, output_dir: Path) -> Path | None:
        output_dir.mkdir(parents=True, exist_ok=True)
        audio_path = output_dir / f"{source_video.stem}.wav"
        srt_path = output_dir / f"{source_video.stem}.srt"

        try:
            self._ffmpeg.extract_audio(source_video, audio_path)
            model = self._get_model()
            segments, _ = model.transcribe(
                str(audio_path),
                beam_size=1,
                best_of=1,
                vad_filter=True,
                condition_on_previous_text=False,
                word_timestamps=False,
                temperature=0.0,
            )

            line_count = self._write_srt(segments, srt_path)
            if line_count == 0:
                logger.warning("Whisper produced no subtitle lines for %s", source_video.name)
                return None
            return srt_path
        except Exception:
            logger.exception("Subtitle generation failed for chunk %s", source_video)
            return None
        finally:
            if audio_path.exists():
                audio_path.unlink(missing_ok=True)
            gc.collect()

    def _write_srt(self, segments, output_path: Path) -> int:
        index = 1
        with output_path.open("w", encoding="utf-8") as handle:
            for segment in segments:
                text = (segment.text or "").strip()
                if not text:
                    continue
                handle.write(f"{index}\n")
                handle.write(f"{self._format_timestamp(segment.start)} --> {self._format_timestamp(segment.end)}\n")
                handle.write(f"{text}\n\n")
                index += 1

        return index - 1

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        millis = max(0, int(seconds * 1000))
        hours, remainder = divmod(millis, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        secs, remainder = divmod(remainder, 1_000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{remainder:03d}"
