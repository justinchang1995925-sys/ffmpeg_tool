"""FFmpeg discovery and Windows one-click installer helpers."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

WINDOWS_USER_PATH_LIMIT = 2040
DOWNLOAD_RETRIES = 3
DOWNLOAD_TIMEOUT = 120

DEFAULT_WINDOWS_BUILD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def _data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


CONFIG_FILE = _data_dir() / ".ffmpeg_tool_config.json"


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


def cleanup_storage(upload_dir: Path, output_dir: Path, max_age_days: int) -> dict:
    """Delete files older than max_age_days. If max_age_days <= 0, only return stats."""
    stats = {"uploads": 0, "outputs": 0, "deleted": 0}
    cutoff = time.time() - max_age_days * 86400 if max_age_days > 0 else None

    for folder, key in ((upload_dir, "uploads"), (output_dir, "outputs")):
        if not folder.exists():
            continue
        for path in folder.iterdir():
            if not path.is_file() or path.name == ".gitkeep":
                continue
            stats[key] += 1
            if cutoff is not None and path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                stats["deleted"] += 1
    return stats


def _download_file(url: str, target: Path, progress_callback=None) -> None:
    last_error: Exception | None = None
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            if progress_callback and attempt > 1:
                progress_callback(5, f"下载失败，正在重试（{attempt}/{DOWNLOAD_RETRIES}）...")
            with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT) as response:
                total = int(response.headers.get("Content-Length", "0") or 0)
                downloaded = 0
                with target.open("wb") as output:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        output.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            if total:
                                percent = 5 + int(downloaded / total * 80)
                                message = (
                                    f"正在下载 FFmpeg：{downloaded / 1024 / 1024:.1f} / "
                                    f"{total / 1024 / 1024:.1f} MB"
                                )
                            else:
                                percent = min(84, 5 + int(downloaded / (1024 * 1024 * 3)))
                                message = f"正在下载 FFmpeg：{downloaded / 1024 / 1024:.1f} MB"
                            progress_callback(percent, message)
                        if total and downloaded > total:
                            raise RuntimeError("Downloaded more data than expected.")
            return
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if target.exists():
                target.unlink(missing_ok=True)
    raise RuntimeError(f"下载失败（已重试 {DOWNLOAD_RETRIES} 次）：{last_error}")


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
    if len(new_user_path) > WINDOWS_USER_PATH_LIMIT:
        return (
            "用户 PATH 过长，已跳过 setx 写入。程序将通过配置文件直接使用 FFmpeg，"
            "无需依赖系统 PATH。"
        )

    result = subprocess.run(["setx", "Path", new_user_path], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout or "写入用户 PATH 失败。")
    return "已写入用户 PATH；新打开的终端会自动生效。"


def install_ffmpeg(install_dir: str, download_url: str = DEFAULT_WINDOWS_BUILD_URL, progress_callback=None) -> dict:
    """Download, extract, configure PATH, and persist FFmpeg location."""
    if progress_callback:
        progress_callback(2, "正在准备安装目录...")
    target_root = Path(install_dir).expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "ffmpeg.zip"
        if progress_callback:
            progress_callback(5, "正在连接下载服务器...")
        _download_file(download_url, zip_path, progress_callback)
        if progress_callback:
            progress_callback(88, "下载完成，正在解压安装包...")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(target_root)

    if progress_callback:
        progress_callback(94, "正在查找 FFmpeg 可执行文件...")
    bin_dir = _find_bin_dir(target_root)
    if progress_callback:
        progress_callback(97, "正在配置用户 PATH 环境变量...")
    path_message = _append_user_path(bin_dir)
    _save_config({"ffmpeg_bin_dir": str(bin_dir), "download_url": download_url})
    if progress_callback:
        progress_callback(100, "FFmpeg 安装完成。")

    return {
        "bin_dir": str(bin_dir),
        "ffmpeg": str(bin_dir / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")),
        "ffprobe": str(bin_dir / ("ffprobe.exe" if os.name == "nt" else "ffprobe")),
        "path_message": path_message,
    }
