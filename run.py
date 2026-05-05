from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import venv
import webbrowser
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
VENV_DIR = BASE_DIR / ".venv"
FRONTEND_DIR = BASE_DIR / "frontend"
APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
APP_URL = f"http://{APP_HOST}:{APP_PORT}"


def print_step(message: str) -> None:
    print(f"[setup] {message}")


def python_executable() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def ensure_venv() -> None:
    if VENV_DIR.exists():
        return
    print_step("Creating virtual environment")
    venv.create(VENV_DIR, with_pip=True)


def run_command(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd or BASE_DIR, check=True)


def ensure_binary(binary_name: str, install_hint: str) -> None:
    if shutil.which(binary_name):
        return
    raise RuntimeError(f"'{binary_name}' was not found in PATH. {install_hint}")


def install_backend_dependencies() -> None:
    python_bin = python_executable()
    print_step("Installing Python dependencies")
    run_command([str(python_bin), "-m", "pip", "install", "--upgrade", "pip"])
    run_command([str(python_bin), "-m", "pip", "install", "-r", "requirements.txt"])


def install_frontend_dependencies() -> None:
    print_step("Installing frontend dependencies")
    run_command(["npm", "install"], cwd=FRONTEND_DIR)


def build_frontend() -> None:
    print_step("Building frontend")
    run_command(["npm", "run", "build"], cwd=FRONTEND_DIR)


def launch_backend() -> subprocess.Popen[bytes]:
    python_bin = python_executable()
    print_step("Starting FastAPI server")
    return subprocess.Popen(
        [str(python_bin), "-m", "uvicorn", "backend.main:app", "--host", APP_HOST, "--port", str(APP_PORT)],
        cwd=BASE_DIR,
    )


def wait_for_server() -> None:
    import urllib.request

    deadline = time.time() + 90
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{APP_URL}/api/health", timeout=2):
                return
        except Exception:
            time.sleep(1)
    raise RuntimeError("Server did not become ready in time")


def main() -> None:
    try:
        ensure_binary("ffmpeg", "Install FFmpeg and add it to PATH. Windows build: https://www.gyan.dev/ffmpeg/builds/")
        ensure_binary("ffprobe", "Install FFmpeg package that includes ffprobe and add it to PATH.")
        ensure_binary("npm", "Install Node.js LTS from https://nodejs.org/")
        ensure_venv()
        install_backend_dependencies()
        install_frontend_dependencies()
        build_frontend()

        process = launch_backend()
        try:
            wait_for_server()
            print_step(f"Opening {APP_URL}")
            webbrowser.open(APP_URL)
            print_step("Service is running. Press Ctrl+C in this window to stop it.")
            process.wait()
        except KeyboardInterrupt:
            print_step("Stopping service")
            process.terminate()
            process.wait(timeout=15)
        except Exception:
            process.terminate()
            process.wait(timeout=15)
            raise
    except Exception as exc:
        print(f"[error] {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
