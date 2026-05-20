from __future__ import annotations

import logging
import os
import subprocess
import sys
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.config import APP_HOST, APP_PORT, FRONTEND_DIST_DIR, OUTPUT_DIR, ensure_directories
from backend.logging_config import configure_logging
from backend.models import ApiMessage, CreateJobRequest, JobCreatedResponse, JobStatusResponse, OpenFolderRequest, OutputFileResponse, OutputsResponse, SearchResponse
from backend.services.processing_service import ProcessingService
from backend.services.youtube_service import YouTubeService
from backend.task_queue import JobManager
from backend.utils import file_size_mb

logger = logging.getLogger(__name__)

job_manager = JobManager()
processing_service = ProcessingService(job_manager)
youtube_service = YouTubeService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_directories()
    configure_logging()
    job_manager.set_processor(processing_service)
    job_manager.start()
    logger.info("Application started on %s:%s", APP_HOST, APP_PORT)
    yield


app = FastAPI(
    title="YouTube Clipper",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=ApiMessage)
async def healthcheck() -> ApiMessage:
    return ApiMessage(message="ok")


@app.get("/api/search", response_model=SearchResponse)
async def search_videos(q: str = Query(..., min_length=2, max_length=200)) -> SearchResponse:
    try:
        items = await run_in_threadpool(youtube_service.search, q)
        return SearchResponse(items=items)
    except Exception as exc:
        logger.exception("Search failed for query '%s'", q)
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc


@app.post("/api/jobs", response_model=JobCreatedResponse)
async def create_job(payload: CreateJobRequest) -> JobCreatedResponse:
    job = job_manager.create_job(
        title=payload.title,
        video_id=payload.video_id,
        video_url=payload.url,
        add_subtitles=payload.add_subtitles,
    )
    return job


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    try:
        return job_manager.get_status(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc


@app.get("/api/outputs", response_model=OutputsResponse)
async def list_outputs() -> OutputsResponse:
    items = [
        OutputFileResponse(
            name=path.name,
            path=str(path),
            size_mb=file_size_mb(path),
            modified_at=datetime.fromtimestamp(path.stat().st_mtime),
        )
        for path in sorted(OUTPUT_DIR.glob("*.mp4"), key=lambda current: current.stat().st_mtime, reverse=True)
    ]
    return OutputsResponse(items=items)


@app.post("/api/open-output-folder", response_model=ApiMessage)
async def open_output_folder(payload: OpenFolderRequest) -> ApiMessage:
    target = Path(payload.path).resolve() if payload.path else OUTPUT_DIR.resolve()
    output_root = OUTPUT_DIR.resolve()

    try:
        target.relative_to(output_root)
    except ValueError:
        if target != output_root:
            raise HTTPException(status_code=400, detail="Path is outside the output directory")

    if not target.exists():
        raise HTTPException(status_code=404, detail="Target path does not exist")

    folder = target if target.is_dir() else target.parent
    if sys.platform.startswith("win"):
        os.startfile(folder)  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(folder)])
    else:
        subprocess.Popen(["xdg-open", str(folder)])

    return ApiMessage(message=f"Opened {folder}")


@app.post("/api/shutdown", response_model=ApiMessage)
async def shutdown_service() -> ApiMessage:
    def delayed_shutdown() -> None:
        time.sleep(0.75)
        os._exit(0)

    threading.Thread(target=delayed_shutdown, name="service-shutdown", daemon=True).start()
    return ApiMessage(message="Service is shutting down")


if FRONTEND_DIST_DIR.exists():
    assets_dir = FRONTEND_DIST_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/", include_in_schema=False)
    async def serve_root() -> FileResponse:
        return FileResponse(FRONTEND_DIST_DIR / "index.html")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        requested_file = FRONTEND_DIST_DIR / full_path
        if requested_file.exists() and requested_file.is_file():
            return FileResponse(requested_file)
        return FileResponse(FRONTEND_DIST_DIR / "index.html")
