from __future__ import annotations

import logging
import shutil
from pathlib import Path

from backend.config import CHUNK_DURATION_SECONDS, OUTPUT_DIR, WORK_DIR
from backend.models import JobFileInfo
from backend.services.ffmpeg_service import FFmpegService
from backend.services.sponsorblock_service import SponsorBlockService
from backend.services.subtitle_service import SubtitleService
from backend.services.youtube_service import YouTubeService
from backend.task_queue import JobManager
from backend.utils import file_size_mb, slugify_filename

logger = logging.getLogger(__name__)


class ProcessingService:
    def __init__(self, job_manager: JobManager) -> None:
        self.job_manager = job_manager
        self.youtube = YouTubeService()
        self.sponsorblock = SponsorBlockService()
        self.ffmpeg = FFmpegService()
        self.subtitles = SubtitleService(self.ffmpeg)

    def process(self, job_id: str) -> None:
        record = self.job_manager.get_record(job_id)
        safe_title = slugify_filename(record.title, fallback=record.video_id)
        add_subtitles = record.add_subtitles
        job_dir = WORK_DIR / job_id
        downloads_dir = job_dir / "downloads"
        chunks_dir = job_dir / "chunks"
        subtitles_dir = job_dir / "subtitles"
        cleaned_dir = job_dir / "cleaned"

        partial = False
        produced_files = 0

        try:
            self.job_manager.add_log(job_id, f"Starting pipeline for video {record.video_id}")
            self.job_manager.add_log(job_id, "Final output will be rendered as a vertical 9:16 Shorts clip")
            if add_subtitles:
                self.job_manager.add_log(job_id, "AI subtitles are enabled and will be placed in the center of the frame")
            else:
                self.job_manager.add_log(job_id, "AI subtitles are disabled for this job")
            self.job_manager.update(job_id, stage="download", progress=5, message="Downloading source video")

            download_result = self.youtube.download(
                video_id=record.video_id,
                title=record.title,
                target_dir=downloads_dir,
                progress_callback=lambda ratio, message: self.job_manager.update(
                    job_id,
                    stage="download",
                    progress=5 + ratio * 25,
                    message=message,
                ),
            )

            safe_title = slugify_filename(download_result.title, fallback=record.video_id)
            self.job_manager.set_title(job_id, download_result.title)
            self.job_manager.add_log(job_id, f"Downloaded video as {download_result.path.name}")

            source_path = download_result.path
            duration = self.ffmpeg.get_duration(source_path)

            self.job_manager.update(job_id, stage="sponsorblock", progress=32, message="Checking SponsorBlock markers")
            keep_ranges = [(0.0, duration)]
            try:
                sponsor_segments = self.sponsorblock.fetch_segments(record.video_id)
                if sponsor_segments:
                    keep_ranges = self.sponsorblock.build_keep_ranges(duration, sponsor_segments)
                    cleaned_path = cleaned_dir / f"{safe_title}_cleaned.mp4"
                    self.job_manager.add_log(job_id, f"Removing {len(sponsor_segments)} sponsor segments")
                    self.ffmpeg.remove_segments(source_path, keep_ranges, cleaned_path)
                    source_path = cleaned_path
                else:
                    self.job_manager.add_log(job_id, "SponsorBlock data was not found, keeping full video")
            except Exception as exc:
                partial = True
                logger.exception("SponsorBlock step failed for job %s", job_id)
                self.job_manager.add_log(job_id, f"SponsorBlock step failed, continuing without cuts: {exc}", level="warning")

            self.job_manager.update(job_id, stage="cutting", progress=42, message="Cutting video into ~3 minute clips")
            chunks = self.ffmpeg.split_into_chunks(source_path, chunks_dir, safe_title, CHUNK_DURATION_SECONDS)
            self.job_manager.set_total_parts(job_id, len(chunks))
            self.job_manager.add_log(job_id, f"Created {len(chunks)} temporary chunks")

            if not chunks:
                raise RuntimeError("FFmpeg did not produce any chunks")

            for index, chunk in enumerate(chunks, start=1):
                progress_start = 42 + ((index - 1) / len(chunks)) * 50
                progress_end = 42 + (index / len(chunks)) * 50

                final_output = OUTPUT_DIR / f"{safe_title}_part{index:02d}.mp4"
                subtitles_embedded = False

                try:
                    subtitle_path = None
                    if add_subtitles:
                        self.job_manager.update(
                            job_id,
                            stage="subtitles",
                            progress=progress_start,
                            current_part=index,
                            message=f"Generating centered subtitles for chunk {index}/{len(chunks)}",
                        )
                        subtitle_path = self.subtitles.transcribe_to_srt(chunk.path, subtitles_dir)
                        subtitles_embedded = subtitle_path is not None
                        if subtitle_path is None:
                            partial = True
                            self.job_manager.add_log(
                                job_id,
                                f"Subtitles failed for chunk {index}, continuing with a vertical clip without subtitles",
                                level="warning",
                            )
                    else:
                        self.job_manager.update(
                            job_id,
                            stage="rendering",
                            progress=progress_start,
                            current_part=index,
                            message=f"Rendering vertical clip {index}/{len(chunks)} without subtitles",
                        )

                    self.job_manager.update(
                        job_id,
                        stage="rendering",
                        progress=min(progress_start + 6, progress_end),
                        current_part=index,
                        message=f"Rendering vertical Shorts clip {index}/{len(chunks)}",
                    )
                    self.ffmpeg.render_vertical_short(chunk.path, final_output, subtitle_path=subtitle_path)

                    produced_files += 1
                    self.job_manager.add_file(
                        job_id,
                        JobFileInfo(
                            name=final_output.name,
                            path=str(final_output),
                            size_mb=file_size_mb(final_output),
                            subtitles_embedded=subtitles_embedded,
                        ),
                    )
                except Exception as exc:
                    partial = True
                    logger.exception("Chunk processing failed for job %s part %s", job_id, index)
                    self.job_manager.add_log(job_id, f"Chunk {index} failed: {exc}", level="error")
                finally:
                    self.job_manager.update(
                        job_id,
                        stage="subtitles",
                        progress=progress_end,
                        current_part=index,
                        message=f"Processed chunk {index}/{len(chunks)}",
                    )
                    chunk.path.unlink(missing_ok=True)
                    subtitle_candidate = subtitles_dir / f"{chunk.path.stem}.srt"
                    subtitle_candidate.unlink(missing_ok=True)

            if produced_files == 0:
                raise RuntimeError("No final clips were produced")

            if partial:
                self.job_manager.complete(job_id, f"Completed with warnings: {produced_files} clips saved", partial=True)
            else:
                self.job_manager.complete(job_id, f"Completed successfully: {produced_files} clips saved")
        except Exception as exc:
            logger.exception("Video processing failed for job %s", job_id)
            self.job_manager.fail(job_id, str(exc))
        finally:
            shutil.rmtree(job_dir, ignore_errors=True)
