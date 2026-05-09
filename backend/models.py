from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    video_id: str
    title: str
    url: str
    thumbnail: str | None = None
    duration_seconds: int | None = None
    duration_label: str = "Unknown"
    uploader: str | None = None


class SearchResponse(BaseModel):
    items: list[SearchResult]


class CreateJobRequest(BaseModel):
    video_id: str = Field(..., min_length=3)
    title: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    thumbnail: str | None = None
    duration_seconds: int | None = None
    add_subtitles: bool = True


class JobFileInfo(BaseModel):
    name: str
    path: str
    size_mb: float
    subtitles_embedded: bool = True


class JobLogEntry(BaseModel):
    timestamp: datetime
    level: Literal["info", "warning", "error"]
    message: str


class JobStatusResponse(BaseModel):
    job_id: str
    title: str
    video_id: str
    add_subtitles: bool = True
    status: Literal["queued", "running", "completed", "failed", "partial"]
    stage: str
    progress: float = Field(ge=0, le=100)
    message: str
    error: str | None = None
    files: list[JobFileInfo] = Field(default_factory=list)
    logs: list[JobLogEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    current_part: int = 0
    total_parts: int = 0


class JobCreatedResponse(BaseModel):
    job_id: str
    status: str


class OutputFileResponse(BaseModel):
    name: str
    path: str
    size_mb: float
    modified_at: datetime


class OutputsResponse(BaseModel):
    items: list[OutputFileResponse]


class OpenFolderRequest(BaseModel):
    path: str | None = None


class ApiMessage(BaseModel):
    message: str
