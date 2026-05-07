from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_DIST_DIR = FRONTEND_DIR / "dist"
OUTPUT_DIR = BASE_DIR / "output"
WORK_DIR = BASE_DIR / "workspace"
LOG_DIR = BASE_DIR / "logs"
MODEL_CACHE_DIR = BASE_DIR / "models"

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_URL = f"http://{APP_HOST}:{APP_PORT}"

CHUNK_DURATION_SECONDS = int(os.getenv("CHUNK_DURATION_SECONDS", "180"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", str(max(os.cpu_count() // 2, 1) if os.cpu_count() else 4)))

SPONSORBLOCK_API_URL = os.getenv("SPONSORBLOCK_API_URL", "https://sponsor.ajay.app/api/skipSegments")
SPONSORBLOCK_CATEGORIES = ["sponsor", "selfpromo", "interaction"]
MAX_SEARCH_RESULTS = int(os.getenv("MAX_SEARCH_RESULTS", "10"))
LOG_FILE = LOG_DIR / "app.log"


def ensure_directories() -> None:
    for path in (OUTPUT_DIR, WORK_DIR, LOG_DIR, MODEL_CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)
