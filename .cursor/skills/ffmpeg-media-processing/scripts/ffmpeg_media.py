#!/usr/bin/env python3
"""Small FFmpeg helper for Cursor agents."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path

DEFAULT_WINDOWS_BUILD_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def which(name: str) -> str | None:
    return shutil.which(name)


def run(command: list[str]) -> int:
    print("COMMAND:", subprocess.list2cmdline(command))
    process = subprocess.run(command, text=True, capture_output=True, check=False)
    if process.stdout:
        print(process.stdout)
    if process.stderr:
        print(process.stderr, file=sys.stderr)
    return process.returncode


def require_tool(name: str) -> str:
    path = which(name)
    if not path:
        raise SystemExit(f"{name} not found. Install FFmpeg or add its bin directory to PATH.")
    return path


def add_user_path_windows(bin_dir: Path) -> None:
    if os.name != "nt":
        print(f"Add this directory to PATH manually: {bin_dir}")
        return

    current_process_path = os.environ.get("PATH", "")
    if str(bin_dir) not in current_process_path:
        os.environ["PATH"] = current_process_path + os.pathsep + str(bin_dir)

    existing_user_path = subprocess.run(
        ["powershell", "-NoProfile", "-Command", "[Environment]::GetEnvironmentVariable('Path','User')"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    parts = [part for part in existing_user_path.split(os.pathsep) if part]
    if any(Path(part).resolve() == bin_dir.resolve() for part in parts if Path(part).exists()):
        print("User PATH already contains FFmpeg bin directory.")
        return

    new_path = existing_user_path + os.pathsep + str(bin_dir) if existing_user_path else str(bin_dir)
    result = subprocess.run(["setx", "Path", new_path], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr or result.stdout or "Failed to update user PATH.")
    print("Updated user PATH. Open a new terminal for it to take effect.")


def install_windows_build(target_dir: str, url: str) -> int:
    root = Path(target_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as temp_dir:
        zip_path = Path(temp_dir) / "ffmpeg.zip"
        print(f"Downloading {url}")
        with urllib.request.urlopen(url, timeout=60) as response, zip_path.open("wb") as output:
            shutil.copyfileobj(response, output)
        print(f"Extracting to {root}")
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(root)

    exe_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    matches = [path for path in root.rglob(exe_name) if path.parent.name.lower() == "bin"]
    if not matches:
        raise SystemExit("ffmpeg executable not found after extraction.")

    bin_dir = matches[0].parent
    add_user_path_windows(bin_dir)
    print(f"FFmpeg bin: {bin_dir}")
    return 0


def ffmpeg_base(input_path: str, output_path: str, args: list[str]) -> list[str]:
    return [require_tool("ffmpeg"), "-y", "-i", input_path, *args, output_path]


def cmd_check(_: argparse.Namespace) -> int:
    data = {
        "ffmpeg": which("ffmpeg"),
        "ffprobe": which("ffprobe"),
    }
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0 if data["ffmpeg"] else 1


def cmd_install(args: argparse.Namespace) -> int:
    return install_windows_build(args.dir, args.url)


def cmd_probe(args: argparse.Namespace) -> int:
    return run([require_tool("ffprobe"), "-hide_banner", "-show_format", "-show_streams", "-print_format", "json", args.input])


def cmd_audio_params(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-ac", args.channels, "-ar", args.sample_rate, "-b:a", args.bitrate]))


def cmd_extract_audio(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-vn", "-c:a", args.codec, "-b:a", args.bitrate]))


def cmd_volume(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-filter:a", f"volume={args.volume}"]))


def cmd_trim(args: argparse.Namespace) -> int:
    return run([require_tool("ffmpeg"), "-y", "-ss", args.start, "-i", args.input, "-t", args.duration, "-c", args.codec, args.output])


def cmd_transcode(args: argparse.Namespace) -> int:
    return run(
        ffmpeg_base(
            args.input,
            args.output,
            [
                "-c:v",
                args.video_codec,
                "-preset",
                args.preset,
                "-crf",
                args.crf,
                "-c:a",
                args.audio_codec,
                "-b:a",
                args.audio_bitrate,
            ],
        )
    )


def cmd_resize(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-vf", f"scale={args.width}:{args.height}"]))


def cmd_fps(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-r", args.fps]))


def cmd_rotate(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-vf", f"transpose={args.transpose}"]))


def cmd_frame(args: argparse.Namespace) -> int:
    return run([require_tool("ffmpeg"), "-y", "-ss", args.time, "-i", args.input, "-frames:v", "1", args.output])


def cmd_gif(args: argparse.Namespace) -> int:
    return run(ffmpeg_base(args.input, args.output, ["-vf", f"fps={args.fps},scale={args.width}:{args.height}"]))


def cmd_custom(args: argparse.Namespace) -> int:
    custom_args = shlex.split(args.args, posix=os.name != "nt")
    return run(ffmpeg_base(args.input, args.output, custom_args))


def add_io(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("input")
    parser.add_argument("output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run common FFmpeg media operations.")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check")
    check.set_defaults(func=cmd_check)

    install = sub.add_parser("install")
    install.add_argument("--dir", required=True, help="Installation directory, for example D:/tools/ffmpeg")
    install.add_argument("--url", default=DEFAULT_WINDOWS_BUILD_URL)
    install.set_defaults(func=cmd_install)

    probe = sub.add_parser("probe")
    probe.add_argument("input")
    probe.set_defaults(func=cmd_probe)

    audio = sub.add_parser("audio-params")
    add_io(audio)
    audio.add_argument("--channels", default="1")
    audio.add_argument("--sample-rate", default="16000")
    audio.add_argument("--bitrate", default="512k")
    audio.set_defaults(func=cmd_audio_params)

    extract = sub.add_parser("extract-audio")
    add_io(extract)
    extract.add_argument("--codec", default="libmp3lame")
    extract.add_argument("--bitrate", default="192k")
    extract.set_defaults(func=cmd_extract_audio)

    volume = sub.add_parser("volume")
    add_io(volume)
    volume.add_argument("--volume", default="1.5")
    volume.set_defaults(func=cmd_volume)

    trim = sub.add_parser("trim")
    add_io(trim)
    trim.add_argument("--start", default="00:00:00")
    trim.add_argument("--duration", required=True)
    trim.add_argument("--codec", default="copy")
    trim.set_defaults(func=cmd_trim)

    transcode = sub.add_parser("transcode")
    add_io(transcode)
    transcode.add_argument("--video-codec", default="libx264")
    transcode.add_argument("--preset", default="medium")
    transcode.add_argument("--crf", default="23")
    transcode.add_argument("--audio-codec", default="aac")
    transcode.add_argument("--audio-bitrate", default="128k")
    transcode.set_defaults(func=cmd_transcode)

    resize = sub.add_parser("resize")
    add_io(resize)
    resize.add_argument("--width", default="1280")
    resize.add_argument("--height", default="-1")
    resize.set_defaults(func=cmd_resize)

    fps = sub.add_parser("fps")
    add_io(fps)
    fps.add_argument("--fps", default="30")
    fps.set_defaults(func=cmd_fps)

    rotate = sub.add_parser("rotate")
    add_io(rotate)
    rotate.add_argument("--transpose", default="1")
    rotate.set_defaults(func=cmd_rotate)

    frame = sub.add_parser("frame")
    add_io(frame)
    frame.add_argument("--time", default="00:00:03")
    frame.set_defaults(func=cmd_frame)

    gif = sub.add_parser("gif")
    add_io(gif)
    gif.add_argument("--fps", default="12")
    gif.add_argument("--width", default="480")
    gif.add_argument("--height", default="-1")
    gif.set_defaults(func=cmd_gif)

    custom = sub.add_parser("custom")
    add_io(custom)
    custom.add_argument("--args", required=True, help="Arguments inserted after input and before output.")
    custom.set_defaults(func=cmd_custom)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
