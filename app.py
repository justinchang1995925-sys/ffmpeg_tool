from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, flash, jsonify, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ffmpeg_features import FEATURES, get_feature, grouped_features
from ffmpeg_manager import DEFAULT_WINDOWS_BUILD_URL, discover_binaries, install_ffmpeg

def _resource_dir() -> Path:
    """Return bundled resource directory when running as a PyInstaller exe."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS"))
    return Path(__file__).resolve().parent


def _data_dir() -> Path:
    """Return writable directory beside the exe or source file."""
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


def _set_install_status(**updates) -> None:
    with INSTALL_LOCK:
        INSTALL_STATUS.update(updates)


def _get_install_status() -> dict:
    with INSTALL_LOCK:
        return dict(INSTALL_STATUS)


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
            message=f"安装失败：{exc}",
            status="error",
            error=str(exc),
            result=None,
        )


def _feature_params(feature: dict) -> dict:
    values = {}
    for param in feature.get("params", []):
        value = request.form.get(param["name"], "").strip()
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


def _build_command(feature: dict, values: dict, input_path: Path, output_path: Path, binaries: dict) -> list[str]:
    tool = feature.get("tool", "ffmpeg")
    tool_path = binaries.get(tool)
    if not tool_path:
        raise RuntimeError(f"未找到 {tool}，请先安装或配置 FFmpeg。")

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

        if stream_mode == "audio_only":
            command.append("-vn")
        else:
            command.extend(["-c:v", video_codec])
            if video_codec != "copy":
                if values.get("preset"):
                    command.extend(["-preset", values["preset"]])
                if values.get("crf"):
                    command.extend(["-crf", values["crf"]])
                if video_bitrate:
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

    raw_custom_args = request.form.get("custom_args", "")
    if feature.get("allow_custom_args") or raw_custom_args.strip():
        command.extend(_split_custom_args(raw_custom_args))

    command.append(str(output_path))
    return command


def _save_upload() -> Path:
    file = request.files.get("input_file")
    if not file or not file.filename:
        raise RuntimeError("请先选择输入文件。")

    safe_name = secure_filename(file.filename)
    if not safe_name:
        safe_name = f"upload_{uuid.uuid4().hex}"
    target = UPLOAD_DIR / f"{uuid.uuid4().hex}_{safe_name}"
    file.save(target)
    return target


def _run_process(command: list[str], output_path: Path | None, feature: dict) -> dict:
    process = subprocess.run(command, capture_output=True, text=True, check=False)
    command_text = subprocess.list2cmdline(command)

    if feature.get("tool") == "ffprobe":
        output_path = output_path or (OUTPUT_DIR / f"media_probe_{uuid.uuid4().hex[:8]}.json")
        output_path.write_text(process.stdout or process.stderr, encoding="utf-8")

    success = process.returncode == 0 and output_path and output_path.exists()
    return {
        "success": success,
        "returncode": process.returncode,
        "command": command_text,
        "stdout": process.stdout,
        "stderr": process.stderr,
        "output_file": output_path.name if success else None,
    }


@app.get("/")
def index():
    selected_id = request.args.get("feature") or FEATURES[0]["id"]
    selected_feature = get_feature(selected_id) or FEATURES[0]
    return render_template(
        "index.html",
        groups=grouped_features(),
        features=FEATURES,
        selected_feature=selected_feature,
        binaries=discover_binaries(),
        default_download_url=DEFAULT_WINDOWS_BUILD_URL,
    )


@app.post("/install")
def install():
    install_dir = request.form.get("install_dir", "").strip()
    download_url = request.form.get("download_url", "").strip() or DEFAULT_WINDOWS_BUILD_URL
    if not install_dir:
        return jsonify({"ok": False, "message": "请填写 FFmpeg 安装路径。"}), 400

    current_status = _get_install_status()
    if current_status["running"]:
        return jsonify({"ok": False, "message": "FFmpeg 正在安装中，请等待当前任务完成。"}), 409

    _set_install_status(
        running=True,
        percent=0,
        message="安装任务已启动。",
        status="running",
        error="",
        result=None,
    )
    worker = threading.Thread(target=_install_worker, args=(install_dir, download_url), daemon=True)
    worker.start()
    return jsonify({"ok": True, "message": "安装任务已启动。"})


@app.get("/install/status")
def install_status():
    return jsonify(_get_install_status())


@app.post("/run")
def run_feature():
    feature_id = request.form.get("feature_id", "")
    feature = get_feature(feature_id)
    if not feature:
        flash("未知功能。", "error")
        return redirect(url_for("index"))

    try:
        input_path = _save_upload()
        values = _feature_params(feature)
        output_path = _safe_output_name(input_path, feature, values)
        if feature.get("tool") == "ffprobe":
            output_path = OUTPUT_DIR / f"{input_path.stem}_media_probe_{uuid.uuid4().hex[:8]}.json"

        binaries = discover_binaries()
        command = _build_command(feature, values, input_path, output_path, binaries)
        result = _run_process(command, output_path, feature)
        return render_template(
            "index.html",
            groups=grouped_features(),
            features=FEATURES,
            selected_feature=feature,
            binaries=binaries,
            default_download_url=DEFAULT_WINDOWS_BUILD_URL,
            result=result,
        )
    except Exception as exc:
        flash(f"执行失败：{exc}", "error")
        return redirect(url_for("index", feature=feature_id))


@app.get("/download/<path:filename>")
def download(filename):
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


if __name__ == "__main__":
    url = "http://127.0.0.1:5000"
    print(f"FFmpeg Web 工具已启动，请在浏览器打开：{url}")
    webbrowser.open(url)
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)
