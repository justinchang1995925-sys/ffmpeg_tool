# FFmpeg Command Reference

## Install And Check

Check local binaries:

```bash
python scripts/ffmpeg_media.py check
```

Install Windows release essentials build:

```bash
python scripts/ffmpeg_media.py install --dir D:/tools/ffmpeg
```

Default download source:

```text
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
```

## Audio Parameter Conversion

Command:

```bash
ffmpeg -y -i sound1.wav -ac 1 -ar 16000 -b:a 512k sound2.wav
```

Parameters:

- `-ac`: audio channel count. `1` means mono, `2` means stereo.
- `-ar`: audio sample rate in Hz. Example: `16000`.
- `-b:a`: audio bitrate. Example: `512k`.
- `-y`: overwrite output file.
- `-i`: input file.

Script:

```bash
python scripts/ffmpeg_media.py audio-params sound1.wav sound2.wav --channels 1 --sample-rate 16000 --bitrate 512k
```

## Extract Audio

```bash
ffmpeg -y -i input.mp4 -vn -c:a libmp3lame -b:a 192k output.mp3
```

- `-vn`: disable video output.
- `-c:a`: audio codec, such as `libmp3lame`, `aac`, `pcm_s16le`, or `copy`.
- `-b:a`: audio bitrate.

```bash
python scripts/ffmpeg_media.py extract-audio input.mp4 output.mp3 --codec libmp3lame --bitrate 192k
```

## Adjust Audio Volume

```bash
ffmpeg -y -i input.mp3 -filter:a volume=1.5 output.mp3
```

- `volume=1.0`: original volume.
- `volume=0.5`: half volume.
- `volume=2.0`: double volume.

```bash
python scripts/ffmpeg_media.py volume input.mp3 output.mp3 --volume 1.5
```

## Trim Media

```bash
ffmpeg -y -ss 00:00:05 -i input.mp4 -t 10 -c copy output.mp4
```

- `-ss`: start time.
- `-t`: duration.
- `-c copy`: stream copy, fast but less precise for some formats.

```bash
python scripts/ffmpeg_media.py trim input.mp4 output.mp4 --start 00:00:05 --duration 10 --codec copy
```

## Video Transcode

```bash
ffmpeg -y -i input.mov -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output.mp4
```

- `-c:v`: video codec, such as `libx264`, `libx265`, `mpeg4`, or `copy`.
- `-preset`: encode speed/efficiency tradeoff.
- `-crf`: constant quality. Lower is higher quality. Common range: `18` to `28`.
- `-c:a`: audio codec.

```bash
python scripts/ffmpeg_media.py transcode input.mov output.mp4 --video-codec libx264 --preset medium --crf 23 --audio-codec aac --audio-bitrate 128k
```

## Resize Video Or Image

```bash
ffmpeg -y -i input.mp4 -vf scale=1280:-1 output.mp4
```

- `scale=1280:-1`: set width to `1280` and calculate height automatically.

```bash
python scripts/ffmpeg_media.py resize input.mp4 output.mp4 --width 1280 --height -1
```

## Change Frame Rate

```bash
ffmpeg -y -i input.mp4 -r 30 output.mp4
```

```bash
python scripts/ffmpeg_media.py fps input.mp4 output.mp4 --fps 30
```

## Rotate Video

```bash
ffmpeg -y -i input.mp4 -vf transpose=1 output.mp4
```

- `transpose=1`: clockwise 90 degrees.
- `transpose=2`: counterclockwise 90 degrees.

```bash
python scripts/ffmpeg_media.py rotate input.mp4 output.mp4 --transpose 1
```

## Capture Frame

```bash
ffmpeg -y -ss 00:00:03 -i input.mp4 -frames:v 1 output.jpg
```

```bash
python scripts/ffmpeg_media.py frame input.mp4 output.jpg --time 00:00:03
```

## Video To GIF

```bash
ffmpeg -y -i input.mp4 -vf fps=12,scale=480:-1 output.gif
```

```bash
python scripts/ffmpeg_media.py gif input.mp4 output.gif --fps 12 --width 480 --height -1
```

## Probe Media

```bash
ffprobe -hide_banner -show_format -show_streams -print_format json input.mp4
```

```bash
python scripts/ffmpeg_media.py probe input.mp4
```

## Custom Arguments

Use this when the requested operation is not listed above. Do not include the input or output path inside `--args`.

```bash
python scripts/ffmpeg_media.py custom input.mp4 output.mp4 --args "-vf scale=640:-1 -c:v libx264 -crf 23"
```
