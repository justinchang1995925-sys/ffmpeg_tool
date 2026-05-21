from __future__ import annotations

import os
import shlex
import subprocess
import uuid
import webbrowser
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from ffmpeg_features import FEATURES, get_feature, grouped_features
from ffmpeg_manager import DEFAULT_WINDOWS_BUILD_URL, discover_binaries, install_ffmpeg

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("FFMPEG_TOOL_SECRET", "local-ffmpeg-tool")
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024


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
        flash("请填写 FFmpeg 安装路径。", "error")
        return redirect(url_for("index"))

    try:
        result = install_ffmpeg(install_dir, download_url)
        flash(f"FFmpeg 安装完成：{result['bin_dir']}。{result['path_message']}", "success")
    except Exception as exc:
        flash(f"安装失败：{exc}", "error")
    return redirect(url_for("index"))


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
