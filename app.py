from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ffmpeg_features import (
    FEATURES,
    FORMAT_PRESETS,
    get_feature,
    grouped_features,
    validate_container_codec,
)
from ffmpeg_manager import DEFAULT_WINDOWS_BUILD_URL, cleanup_storage, discover_binaries, install_ffmpeg

FFPROBE_TIMEOUT = 60
DEFAULT_RUN_TIMEOUT = 3600
STDERR_TAIL_LINES = 30
CLEANUP_MAX_AGE_DAYS = 7


def _resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


RESOURCE_DIR = _resource_dir()
DATA_DIR = _data_dir()
UPLOAD_DIR = DATA_DIR / "uploads"
OUTPUT_DIR = DATA_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(
    __name__,
    template_folder=str(RESOURCE_DIR / "templates"),
    static_folder=str(RESOURCE_DIR / "static"),
)
app.secret_key = os.environ.get("FFMPEG_TOOL_SECRET", "local-ffmpeg-tool")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024

INSTALL_STATUS = {
    "running": False,
    "percent": 0,
    "message": "未开始安装。",
    "status": "idle",
    "error": "",
    "result": None,
}
INSTALL_LOCK = threading.Lock()

RUN_STATUS = {
    "running": False,
    "percent": 0,
    "message": "等待处理。",
    "status": "idle",
    "command": "",
    "stdout": "",
    "stderr": "",
    "stderr_tail": "",
    "output_file": None,
    "success": False,
    "elapsed": 0,
    "batch_total": 0,
    "batch_index": 0,
    "batch_results": [],
}
RUN_LOCK = threading.Lock()


def _set_install_status(**updates) -> None:
    with INSTALL_LOCK:
        INSTALL_STATUS.update(updates)


def _get_install_status() -> dict:
    with INSTALL_LOCK:
        return dict(INSTALL_STATUS)


def _set_run_status(**updates) -> None:
    with RUN_LOCK:
        RUN_STATUS.update(updates)


def _get_run_status() -> dict:
    with RUN_LOCK:
        return dict(RUN_STATUS)


def _tail_lines(text: str, max_lines: int = STDERR_TAIL_LINES) -> str:
    lines = (text or "").splitlines()
    if len(lines) <= max_lines:
        return "\n".join(lines)
    return "\n".join(lines[-max_lines:])


def _cleanup_storage(max_age_days: int) -> dict:
    return cleanup_storage(UPLOAD_DIR, OUTPUT_DIR, max_age_days)


def _find_free_port(start: int = 5000, end: int = 5010) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return start


def _feature_params(feature: dict, form=None) -> dict:
    source = form if form is not None else request.form
    values = {}
    for param in feature.get("params", []):
        value = source.get(param["name"], "").strip()
        values[param["name"]] = value or param.get("default", "")
    return values


def _render_token(token: str, values: dict) -> str:
    rendered = token
    for key, value in values.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered


def _render_args(tokens: list[str], values: dict) -> list[str]:
    return [_render_token(token, values) for token in tokens if _render_token(token, values) != ""]


def _split_custom_args(raw_args: str) -> list[str]:
    if not raw_args.strip():
        return []
    return shlex.split(raw_args, posix=os.name != "nt")


def _safe_output_name(input_path: Path, feature: dict, values: dict) -> Path:
    ext_template = feature.get("output_ext", "mp4")
    ext = _render_token(ext_template, values).strip().lstrip(".") or "out"
    safe_stem = secure_filename(input_path.stem) or "output"
    return OUTPUT_DIR / f"{safe_stem}_{feature['id']}_{uuid.uuid4().hex[:8]}.{ext}"


def _save_upload(file_storage) -> Path:
    if not file_storage or not file_storage.filename:
        raise RuntimeError("请先选择输入文件。")

    original = Path(file_storage.filename)
    ext = original.suffix.lower()
    safe_stem = secure_filename(original.stem)
    if not safe_stem:
        safe_stem = "media"
    target = UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe_stem}{ext}"
    file_storage.save(target)
    return target


def _probe_duration(ffprobe_path: str | None, input_path: Path) -> float | None:
    if not ffprobe_path:
        return None
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(input_path),
    ]
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=FFPROBE_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return None
    if process.returncode != 0:
        return None
    try:
        return float(process.stdout.strip())
    except ValueError:
        return None


def _parse_ffmpeg_time_seconds(line: str) -> float | None:
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _run_timeout_seconds(feature: dict) -> int:
    if feature.get("tool") == "ffprobe":
        return FFPROBE_TIMEOUT
    return DEFAULT_RUN_TIMEOUT


def _build_command(
    feature: dict,
    values: dict,
    input_path: Path,
    output_path: Path,
    binaries: dict,
    custom_args: str = "",
) -> list[str]:
    tool = feature.get("tool", "ffmpeg")
    tool_path = binaries.get(tool)
    if not tool_path:
        raise RuntimeError(f"未找到 {tool}，请先安装或配置 FFmpeg。")

    if feature.get("builder") == "container_codec":
        error = validate_container_codec(values)
        if error:
            raise RuntimeError(error)

    if tool == "ffprobe":
        return [tool_path, *_render_args(feature.get("args", []), values), str(input_path)]

    command = [tool_path, "-y"]
    command.extend(_render_args(feature.get("pre_input_args", []), values))
    command.extend(["-i", str(input_path)])

    if feature.get("builder") == "container_codec":
        stream_mode = values.get("stream_mode", "audio_video")
        video_codec = values.get("video_codec", "libx264")
        audio_codec = values.get("audio_codec", "aac")
        video_bitrate = values.get("video_bitrate", "").strip()
        audio_bitrate = values.get("audio_bitrate", "").strip()
        force_format = values.get("force_format", "").strip()
        container = values.get("container_format", "mp4").lower().strip().lstrip(".")
        if not force_format:
            force_format = FORMAT_PRESETS.get(container, {}).get("force_format", "")

        if stream_mode == "audio_only":
            command.append("-vn")
        else:
            command.extend(["-c:v", video_codec])
            if video_codec != "copy" and video_codec in {"libx264", "libx265"}:
                if values.get("preset"):
                    command.extend(["-preset", values["preset"]])
                if values.get("crf"):
                    command.extend(["-crf", values["crf"]])
            elif video_codec != "copy" and video_bitrate:
                command.extend(["-b:v", video_bitrate])

        if stream_mode == "video_only":
            command.append("-an")
        else:
            command.extend(["-c:a", audio_codec])
            if audio_codec != "copy" and audio_bitrate:
                command.extend(["-b:a", audio_bitrate])

        if force_format:
            command.extend(["-f", force_format])

        command.append(str(output_path))
        return command

    command.extend(_render_args(feature.get("args", []), values))
    if feature.get("allow_custom_args") or custom_args.strip():
        command.extend(_split_custom_args(custom_args))
    command.append(str(output_path))
    return command


def _run_ffmpeg_with_progress(
    command: list[str],
    output_path: Path | None,
    feature: dict,
    binaries: dict,
    input_path: Path,
) -> dict:
    command_text = subprocess.list2cmdline(command)
    timeout_seconds = _run_timeout_seconds(feature)
    duration = None
    if feature.get("tool") == "ffmpeg":
        duration = _probe_duration(binaries.get("ffprobe"), input_path)

    stderr_lines: list[str] = []
    stdout_lines: list[str] = []
    start = time.time()
    capture_stdout = feature.get("tool") == "ffprobe"

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE if capture_stdout else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    def stderr_reader() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            stderr_lines.append(line)
            current = _parse_ffmpeg_time_seconds(line)
            elapsed = int(time.time() - start)
            if duration and current is not None and duration > 0:
                file_percent = min(99, int(current / duration * 100))
                stage = f"处理中 {file_percent}%"
            else:
                file_percent = min(95, 5 + elapsed % 90)
                stage = line.strip()[:120] or "正在处理..."
            snapshot = _get_run_status()
            total = snapshot.get("batch_total", 1) or 1
            index = snapshot.get("batch_index", 1) or 1
            if total > 1:
                percent = int(((index - 1) + file_percent / 100) / total * 100)
                percent = min(99, max(0, percent))
                message = f"[{index}/{total}] {stage} · 已用时 {elapsed}s"
            else:
                percent = file_percent
                message = f"{stage} · 已用时 {elapsed}s"
            _set_run_status(percent=percent, message=message, status="running", command=command_text)

    def stdout_reader() -> None:
        if process.stdout is None:
            return
        stdout_lines.append(process.stdout.read())

    stderr_thread = threading.Thread(target=stderr_reader, daemon=True)
    stderr_thread.start()
    stdout_thread = None
    if capture_stdout:
        stdout_thread = threading.Thread(target=stdout_reader, daemon=True)
        stdout_thread.start()

    try:
        returncode = process.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        process.kill()
        returncode = process.wait()
        stderr_thread.join(timeout=2)
        if stdout_thread:
            stdout_thread.join(timeout=2)
        stderr_text = "".join(stderr_lines)
        return {
            "success": False,
            "returncode": -1,
            "command": command_text,
            "stdout": "".join(stdout_lines),
            "stderr": stderr_text,
            "stderr_tail": _tail_lines(stderr_text),
            "output_file": None,
            "elapsed": int(time.time() - start),
            "error": f"处理超时（超过 {timeout_seconds} 秒），已终止任务。",
        }

    stderr_thread.join(timeout=2)
    if stdout_thread:
        stdout_thread.join(timeout=2)
    stderr_text = "".join(stderr_lines)
    stdout = "".join(stdout_lines)
    elapsed = int(time.time() - start)

    if feature.get("tool") == "ffprobe":
        output_path = output_path or (OUTPUT_DIR / f"media_probe_{uuid.uuid4().hex[:8]}.json")
        output_path.write_text(stdout or stderr_text, encoding="utf-8")

    success = returncode == 0 and output_path is not None and output_path.exists()
    return {
        "success": success,
        "returncode": returncode,
        "command": command_text,
        "stdout": stdout or "",
        "stderr": stderr_text,
        "stderr_tail": _tail_lines(stderr_text),
        "output_file": output_path.name if success and output_path else None,
        "elapsed": elapsed,
        "error": "" if success else "FFmpeg 执行失败，请查看错误输出。",
    }


def _install_worker(install_dir: str, download_url: str) -> None:
    def update(percent: int, message: str) -> None:
        _set_install_status(percent=percent, message=message, status="running")

    try:
        result = install_ffmpeg(install_dir, download_url, progress_callback=update)
        _set_install_status(
            running=False,
            percent=100,
            message=f"FFmpeg 安装完成：{result['bin_dir']}。{result['path_message']}",
            status="success",
            error="",
            result=result,
        )
    except Exception as exc:
        _set_install_status(
            running=False,
            percent=0,
            message=f"安装失败：{exc}",
            status="error",
            error=str(exc),
            result=None,
        )


def _resolve_output_path(feature: dict, values: dict, input_path: Path) -> Path:
    if feature.get("tool") == "ffprobe":
        return OUTPUT_DIR / f"{input_path.stem}_media_probe_{uuid.uuid4().hex[:8]}.json"
    return _safe_output_name(input_path, feature, values)


def _run_batch_worker(
    feature: dict,
    values: dict,
    input_paths: list[Path],
    binaries: dict,
    custom_args: str,
) -> None:
    total = len(input_paths)
    batch_results: list[dict] = []
    try:
        _set_run_status(
            running=True,
            percent=1,
            message="任务已启动，正在准备 FFmpeg...",
            status="running",
            command="",
            stdout="",
            stderr="",
            stderr_tail="",
            output_file=None,
            success=False,
            batch_total=total,
            batch_index=0,
            batch_results=[],
        )

        for index, input_path in enumerate(input_paths, start=1):
            _set_run_status(batch_index=index, batch_total=total)
            try:
                if not input_path.exists() or input_path.stat().st_size == 0:
                    raise RuntimeError("文件为空（0 字节），已跳过。请检查源文件是否正常。")
                if input_path.suffix.lower() == ".pcm" and not feature.get("pre_input_args"):
                    raise RuntimeError(
                        "这是无文件头的 PCM 裸流，当前功能无法直接读取。"
                        "请改用「PCM 裸流转 WAV」功能，并指定采样格式/采样率/声道数。"
                    )
                output_path = _resolve_output_path(feature, values, input_path)
                command = _build_command(feature, values, input_path, output_path, binaries, custom_args)
                result = _run_ffmpeg_with_progress(command, output_path, feature, binaries, input_path)
            except Exception as exc:  # noqa: BLE001 - 单个文件失败不应中断整个批次
                result = {
                    "success": False,
                    "command": "",
                    "stdout": "",
                    "stderr": str(exc),
                    "stderr_tail": str(exc),
                    "output_file": None,
                    "elapsed": 0,
                    "error": str(exc),
                }
            batch_results.append(
                {
                    "input_name": input_path.name,
                    "success": result["success"],
                    "command": result["command"],
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "stderr_tail": result["stderr_tail"],
                    "output_file": result["output_file"],
                    "elapsed": result.get("elapsed", 0),
                    "error": "" if result["success"] else result.get("error", "处理失败。"),
                }
            )
            _set_run_status(batch_results=list(batch_results))

        succeeded = sum(1 for r in batch_results if r["success"])
        failed = total - succeeded
        all_ok = failed == 0
        last = batch_results[-1] if batch_results else {}
        if total == 1:
            summary = "处理完成。" if all_ok else last.get("error", "处理失败。")
        else:
            summary = f"批量处理完成：成功 {succeeded} 个，失败 {failed} 个（共 {total} 个）。"
        _set_run_status(
            running=False,
            percent=100,
            message=summary,
            status="success" if all_ok else "error",
            command=last.get("command", ""),
            stdout=last.get("stdout", ""),
            stderr=last.get("stderr", ""),
            stderr_tail=last.get("stderr_tail", ""),
            output_file=last.get("output_file"),
            success=all_ok,
            elapsed=sum(r.get("elapsed", 0) for r in batch_results),
            batch_index=total,
            batch_total=total,
            batch_results=list(batch_results),
        )
    except Exception as exc:
        _set_run_status(
            running=False,
            percent=0,
            message=str(exc),
            status="error",
            success=False,
            stderr_tail=str(exc),
            batch_results=list(batch_results),
        )


# Run startup cleanup after helper is defined.
_cleanup_storage(CLEANUP_MAX_AGE_DAYS)


@app.get("/")
def index():
    selected_id = request.args.get("feature") or FEATURES[0]["id"]
    selected_feature = get_feature(selected_id) or FEATURES[0]
    storage_stats = _cleanup_storage(0)
    return render_template(
        "index.html",
        groups=grouped_features(),
        features=FEATURES,
        selected_feature=selected_feature,
        binaries=discover_binaries(),
        default_download_url=DEFAULT_WINDOWS_BUILD_URL,
        format_presets=FORMAT_PRESETS,
        storage_stats=storage_stats,
    )


@app.post("/install")
def install():
    install_dir = request.form.get("install_dir", "").strip()
    download_url = request.form.get("download_url", "").strip() or DEFAULT_WINDOWS_BUILD_URL
    if not install_dir:
        return jsonify({"ok": False, "message": "请填写 FFmpeg 安装路径。"}), 400

    if _get_install_status()["running"]:
        return jsonify({"ok": False, "message": "FFmpeg 正在安装中，请等待当前任务完成。"}), 409

    _set_install_status(
        running=True,
        percent=0,
        message="安装任务已启动。",
        status="running",
        error="",
        result=None,
    )
    threading.Thread(target=_install_worker, args=(install_dir, download_url), daemon=True).start()
    return jsonify({"ok": True, "message": "安装任务已启动。"})


@app.get("/install/status")
def install_status():
    return jsonify(_get_install_status())


@app.post("/run/preview")
def run_preview():
    feature_id = request.form.get("feature_id", "")
    feature = get_feature(feature_id)
    if not feature:
        return jsonify({"ok": False, "message": "未知功能。"}), 400

    binaries = discover_binaries()
    if not binaries.get(feature.get("tool", "ffmpeg")):
        return jsonify({"ok": False, "message": "请先安装 FFmpeg。"}), 400

    try:
        values = _feature_params(feature)
        dummy_input = UPLOAD_DIR / "preview_input.mp4"
        dummy_output = OUTPUT_DIR / f"preview_{uuid.uuid4().hex[:8]}.{_render_token(feature.get('output_ext', 'out'), values)}"
        command = _build_command(feature, values, dummy_input, dummy_output, binaries, request.form.get("custom_args", ""))
        return jsonify({"ok": True, "command": subprocess.list2cmdline(command)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@app.post("/run")
def run_feature():
    feature_id = request.form.get("feature_id", "")
    feature = get_feature(feature_id)
    if not feature:
        return jsonify({"ok": False, "message": "未知功能。"}), 400

    if _get_run_status()["running"]:
        return jsonify({"ok": False, "message": "已有任务正在处理，请等待完成。"}), 409

    binaries = discover_binaries()
    if not binaries.get(feature.get("tool", "ffmpeg")):
        return jsonify({"ok": False, "message": "请先安装 FFmpeg。"}), 400

    files = [f for f in request.files.getlist("input_file") if f and f.filename]
    if not files:
        return jsonify({"ok": False, "message": "请先选择输入文件。"}), 400

    try:
        input_paths = [_save_upload(f) for f in files]
        values = _feature_params(feature)
        custom_args = request.form.get("custom_args", "")
        threading.Thread(
            target=_run_batch_worker,
            args=(feature, values, input_paths, binaries, custom_args),
            daemon=True,
        ).start()
        count_msg = "处理任务已启动。" if len(input_paths) == 1 else f"批量处理任务已启动，共 {len(input_paths)} 个文件。"
        return jsonify({"ok": True, "message": count_msg, "total": len(input_paths)})
    except Exception as exc:
        return jsonify({"ok": False, "message": str(exc)}), 400


@app.get("/run/status")
def run_status():
    return jsonify(_get_run_status())


@app.post("/cleanup")
def cleanup():
    deleted = _cleanup_storage(CLEANUP_MAX_AGE_DAYS)
    stats = _cleanup_storage(0)
    return jsonify({"ok": True, "deleted": deleted, "stats": stats})


@app.get("/open-output-folder")
def open_output_folder():
    path = str(OUTPUT_DIR)
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if os.name == "nt":
            os.startfile(OUTPUT_DIR)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            result = subprocess.run(["open", path], check=False)
            if result.returncode != 0:
                raise OSError(f"open 命令返回 {result.returncode}")
        else:
            result = subprocess.run(["xdg-open", path], check=False)
            if result.returncode != 0:
                raise OSError(f"xdg-open 命令返回 {result.returncode}")
    except Exception as exc:  # noqa: BLE001 - 需把任何失败原因回传前端
        return jsonify({"ok": False, "path": path, "error": str(exc)}), 500
    return jsonify({"ok": True, "path": path})


@app.get("/download/<path:filename>")
def download(filename):
    safe_name = Path(filename).name
    return send_from_directory(OUTPUT_DIR, safe_name, as_attachment=True)


if __name__ == "__main__":
    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"
    print(f"FFmpeg Web 工具已启动，请在浏览器打开：{url}")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)
