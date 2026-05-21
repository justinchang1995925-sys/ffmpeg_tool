---
name: ffmpeg-media-processing
description: Process audio, video, and image files with FFmpeg and FFprobe. Use when the user asks to convert media formats, extract audio, resize or transcode videos, create GIFs, capture frames, inspect media metadata, install FFmpeg on Windows, or run custom FFmpeg commands against local media files.
---

# FFmpeg Media Processing

## Core Workflow

1. Identify the input file path, desired output, and operation.
2. Check FFmpeg availability:
   ```bash
   python scripts/ffmpeg_media.py check
   ```
3. If FFmpeg is missing on Windows and the user wants installation, run:
   ```bash
   python scripts/ffmpeg_media.py install --dir D:/tools/ffmpeg
   ```
4. Choose a command from [COMMANDS.md](COMMANDS.md), or build a custom FFmpeg command.
5. Prefer previewing commands before execution. Explain destructive behavior such as overwriting output files.
6. Execute with explicit input and output paths. Quote paths that contain spaces.
7. Report the exact command, output path, and any FFmpeg error text that matters.

## Safety Rules

- Never delete or overwrite the user's original media file.
- Use a new output filename unless the user explicitly asks to overwrite an existing output.
- Use `-y` only for generated output paths or when overwrite is explicitly approved.
- Keep input and output file names simple when possible: English letters, numbers, `_`, and `-`.
- For user-provided custom arguments, do not silently add hidden transformations. Show the final command.
- If the task is only metadata inspection, use `ffprobe` and do not transcode.

## Utility Script

Use `scripts/ffmpeg_media.py` for repeatable operations:

```bash
python scripts/ffmpeg_media.py check
python scripts/ffmpeg_media.py probe input.mp4
python scripts/ffmpeg_media.py audio-params input.wav output.wav --channels 1 --sample-rate 16000 --bitrate 512k
python scripts/ffmpeg_media.py extract-audio input.mp4 output.mp3 --codec libmp3lame --bitrate 192k
python scripts/ffmpeg_media.py custom input.mp4 output.mp4 --args "-vf scale=1280:-1 -c:v libx264 -crf 23"
```

## Common Operations

- Audio parameter conversion: channels, sample rate, bitrate.
- Extract audio from video.
- Adjust audio volume.
- Trim audio or video.
- Transcode video codec, CRF, preset, and audio codec.
- Resize video or image.
- Change video frame rate.
- Rotate video.
- Capture a frame from video.
- Convert video to GIF.
- Inspect media information with FFprobe.
- Run custom FFmpeg arguments.

For detailed command templates and parameter meanings, read [COMMANDS.md](COMMANDS.md).

## Response Format

When completing a media task, respond with:

```markdown
已完成。

命令：`...`
输出：`path/to/output.ext`

说明：...
```

If execution fails, respond with the command and the important FFmpeg error lines.
