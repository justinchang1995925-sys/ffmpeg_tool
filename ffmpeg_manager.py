"""FFmpeg discovery and Windows one-click installer helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_WINDOWS_BUILD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
CONFIG_FILE = Path(".ffmpeg_tool_config.json")


def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_executable(path: Path) -> bool:
    return path.exists() and path.is_file()


def _configured_bin_dir() -> Path | None:
    config = _load_config()
    bin_dir = config.get("ffmpeg_bin_dir")
    if not bin_dir:
        return None
    path = Path(bin_dir)
    return path if path.exists() else None


def discover_binaries() -> dict:
    """Find ffmpeg/ffprobe from saved config, environment variables, or PATH."""
    candidates = []
    configured = _configured_bin_dir()
    if configured:
        candidates.append(configured)

    env_path = os.environ.get("FFMPEG_BIN")
    if env_path:
        candidates.append(Path(env_path))

    for bin_dir in candidates:
        ffmpeg = bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        ffprobe = bin_dir / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if _is_executable(ffmpeg):
            return {
                "installed": True,
                "ffmpeg": str(ffmpeg),
                "ffprobe": str(ffprobe) if _is_executable(ffprobe) else None,
                "source": "configured",
                "bin_dir": str(bin_dir),
            }

    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    return {
        "installed": bool(ffmpeg_path),
        "ffmpeg": ffmpeg_path,
        "ffprobe": ffprobe_path,
        "source": "PATH" if ffmpeg_path else "not found",
        "bin_dir": str(Path(ffmpeg_path).parent) if ffmpeg_path else None,
    }


def _download_file(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:
        total = int(response.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        with target.open("wb") as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                if total and downloaded > total:
                    raise RuntimeError("Downloaded more data than expected.")


def _find_bin_dir(root: Path) -> Path:
    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    for ffmpeg in root.rglob(exe_name):
        if ffmpeg.parent.name.lower() == "bin":
            return ffmpeg.parent
    raise FileNotFoundError("安装包中未找到 ffmpeg 可执行文件。")


def _append_user_path(bin_dir: Path) -> str:
    """Append FFmpeg bin directory to the current user's PATH on Windows."""
    bin_text = str(bin_dir)
    current_path = os.environ.get("PATH", "")
    path_parts = [part for part in current_path.split(os.pathsep) if part]
    if any(Path(part).resolve() == bin_dir.resolve() for part in path_parts if Path(part).exists()):
        return "PATH 已包含 FFmpeg bin 目录。"

    os.environ["PATH"] = current_path + os.pathsep + bin_text if current_path else bin_text

    if os.name != "nt":
        return "已更新当前进程 PATH；非 Windows 系统请手动写入 shell 配置。"

    existing_user_path = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('Path','User')"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    new_user_path = existing_user_path + os.pathsep + bin_text if existing_user_path else bin_text
    result = subprocess.run(["setx", "Path", new_user_path], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "写入用户 PATH 失败。")
    return "已写入用户 PATH；新打开的终端会自动生效。"


def install_ffmpeg(install_dir: str, download_url: str = DEFAULT_WINDOWS_BUILD_URL) -> dict:
    """Download, extract, configure PATH, and persist FFmpeg location."""
    target_root = Path(install_dir).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "ffmpeg.zip"
        _download_file(download_url, zip_path)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(target_root)

    bin_dir = _find_bin_dir(target_root)
    path_message = _append_user_path(bin_dir)
    _save_config({"ffmpeg_bin_dir": str(bin_dir), "download_url": download_url})

    return {
        "bin_dir": str(bin_dir),
        "ffmpeg": str(bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")),
        "ffprobe": str(bin_dir / ("ffprobe.exe" if os.name == "nt" else "ffprobe")),
        "path_message": path_message,
    }
