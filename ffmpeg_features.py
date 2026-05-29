"""Data-driven FFmpeg feature catalog used by the web UI and command builder."""

FEATURES = [
    {
        "id": "audio_params_convert",
        "category": "音频处理",
        "title": "音视频参数转换",
        "description": "调整音频声道数、采样率和音频码率，适合语音识别、转码和压缩场景。",
        "tool": "ffmpeg",
        "output_ext": "wav",
        "example": "ffmpeg -y -i sound1.wav -ac 1 -ar 16000 -b:a 512k sound2.wav",
        "docs": [
            "-ac：audio channel，声道数，1 表示 mono，2 表示 stereo。",
            "-ar：audio sample rate，采样率，例如 16000 表示 16 kHz。",
            "-b:a：audio bitrate，音频码率，例如 512k。",
            "-y：覆盖输出文件。",
            "-i：输入文件，后接输入文件名。",
        ],
        "args": ["-ac", "{audio_channels}", "-ar", "{sample_rate}", "-b:a", "{audio_bitrate}"],
        "params": [
            {
                "name": "audio_channels",
                "label": "声道数 -ac",
                "default": "1",
                "placeholder": "1 或 2",
                "help": "1=mono，2=stereo。",
            },
            {
                "name": "sample_rate",
                "label": "采样率 -ar",
                "default": "16000",
                "placeholder": "16000",
                "help": "单位 Hz，常见值：16000、44100、48000。",
            },
            {
                "name": "audio_bitrate",
                "label": "音频码率 -b:a",
                "default": "512k",
                "placeholder": "512k",
                "help": "单位 bit/s，可写 128k、256k、512k。",
            },
        ],
    },
    {
        "id": "extract_audio",
        "category": "音频处理",
        "title": "从视频提取音频",
        "description": "去掉视频流，只保留音频并编码为 MP3、AAC 或 WAV。",
        "tool": "ffmpeg",
        "output_ext": "{format}",
        "example": "ffmpeg -y -i input.mp4 -vn -c:a libmp3lame -b:a 192k output.mp3",
        "docs": ["-vn：不输出视频流。", "-c:a：音频编码器。", "-b:a：音频码率。"],
        "args": ["-vn", "-c:a", "{audio_codec}", "-b:a", "{audio_bitrate}"],
        "params": [
            {
                "name": "format",
                "label": "输出格式",
                "default": "mp3",
                "choices": ["mp3", "aac", "wav", "m4a"],
                "help": "决定输出文件扩展名。",
            },
            {
                "name": "audio_codec",
                "label": "音频编码器 -c:a",
                "default": "libmp3lame",
                "choices": ["libmp3lame", "aac", "pcm_s16le", "copy"],
                "help": "WAV 通常使用 pcm_s16le，直接复制可选 copy。",
            },
            {
                "name": "audio_bitrate",
                "label": "音频码率 -b:a",
                "default": "192k",
                "placeholder": "192k",
                "help": "当 audio_codec 为 copy 时该参数可能被 FFmpeg 忽略。",
            },
        ],
    },
    {
        "id": "audio_volume",
        "category": "音频处理",
        "title": "调整音量",
        "description": "通过 audio filter 放大或降低音量。",
        "tool": "ffmpeg",
        "output_ext": "mp3",
        "example": "ffmpeg -y -i input.mp3 -filter:a volume=1.5 output.mp3",
        "docs": ["-filter:a：音频滤镜。", "volume=1.5 表示音量变为 1.5 倍。"],
        "args": ["-filter:a", "volume={volume}"],
        "params": [
            {
                "name": "volume",
                "label": "音量倍数",
                "default": "1.5",
                "placeholder": "1.5",
                "help": "1.0 为原音量，0.5 为一半，2.0 为两倍。",
            }
        ],
    },
    {
        "id": "trim_media",
        "category": "音视频剪辑",
        "title": "截取片段",
        "description": "按开始时间和持续时长截取音频或视频片段。",
        "tool": "ffmpeg",
        "output_ext": "mp4",
        "example": "ffmpeg -y -ss 00:00:05 -i input.mp4 -t 10 -c copy output.mp4",
        "docs": ["-ss：开始时间。", "-t：持续时长。", "-c copy：不重新编码，速度快。"],
        "pre_input_args": ["-ss", "{start_time}"],
        "args": ["-t", "{duration}", "-c", "{codec_mode}"],
        "params": [
            {
                "name": "start_time",
                "label": "开始时间 -ss",
                "default": "00:00:00",
                "placeholder": "00:00:05",
                "help": "格式可为 HH:MM:SS 或秒数。",
            },
            {
                "name": "duration",
                "label": "持续时长 -t",
                "default": "10",
                "placeholder": "10",
                "help": "可填写秒数或 HH:MM:SS。",
            },
            {
                "name": "codec_mode",
                "label": "编码模式 -c",
                "default": "copy",
                "choices": ["copy", "libx264", "aac"],
                "help": "copy 最快，但部分格式可能需要重新编码。",
            },
        ],
    },
    {
        "id": "video_transcode",
        "category": "视频处理",
        "title": "视频转码",
        "description": "转换视频编码、质量、编码速度和音频编码。",
        "tool": "ffmpeg",
        "output_ext": "mp4",
        "example": "ffmpeg -y -i input.mov -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output.mp4",
        "docs": ["-c:v：视频编码器。", "-preset：编码速度。", "-crf：恒定质量，数值越小质量越高。"],
        "args": [
            "-c:v",
            "{video_codec}",
            "-preset",
            "{preset}",
            "-crf",
            "{crf}",
            "-c:a",
            "{audio_codec}",
            "-b:a",
            "{audio_bitrate}",
        ],
        "params": [
            {
                "name": "video_codec",
                "label": "视频编码器 -c:v",
                "default": "libx264",
                "choices": ["libx264", "libx265", "mpeg4", "copy"],
            },
            {
                "name": "preset",
                "label": "编码速度 -preset",
                "default": "medium",
                "choices": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"],
            },
            {"name": "crf", "label": "质量 CRF", "default": "23", "placeholder": "23", "help": "18-28 常用。"},
            {
                "name": "audio_codec",
                "label": "音频编码器 -c:a",
                "default": "aac",
                "choices": ["aac", "libmp3lame", "copy"],
            },
            {"name": "audio_bitrate", "label": "音频码率 -b:a", "default": "128k", "placeholder": "128k"},
        ],
    },
    {
        "id": "container_codec_generate",
        "category": "音视频生成",
        "title": "生成指定封装与编码格式",
        "description": "按输出封装格式、视频编码器、音频编码器生成新的音视频文件。",
        "tool": "ffmpeg",
        "builder": "container_codec",
        "output_ext": "{container_format}",
        "example": "ffmpeg -y -i input.mp4 -c:v libx264 -preset medium -crf 23 -c:a aac -b:a 128k output.mp4",
        "docs": [
            "FFmpeg 支持 muxer 封装器生成不同容器格式，常见如 mp4、mkv、webm、mov、avi、mp3、wav、flac、ogg。",
            "-c:v：指定视频编码器，例如 libx264、libx265、mpeg4、libvpx-vp9、copy。",
            "-c:a：指定音频编码器，例如 aac、libmp3lame、libopus、flac、pcm_s16le、copy。",
            "输出文件扩展名会决定封装格式；高级场景可填写 -f 强制指定 muxer。",
            "并非所有封装格式都兼容所有编码器，例如 mp4 常用 H.264/H.265 + AAC，webm 常用 VP9 + Opus。",
        ],
        "params": [
            {
                "name": "container_format",
                "label": "输出封装格式/扩展名",
                "default": "mp4",
                "choices": ["mp4", "mkv", "webm", "mov", "avi", "mp3", "wav", "flac", "ogg", "m4a"],
                "help": "决定输出文件扩展名，FFmpeg 通常会据此选择 muxer。",
            },
            {
                "name": "stream_mode",
                "label": "输出流类型",
                "default": "audio_video",
                "choices": ["audio_video", "audio_only", "video_only"],
                "help": "audio_only 会添加 -vn；video_only 会添加 -an。",
            },
            {
                "name": "video_codec",
                "label": "视频编码器 -c:v",
                "default": "libx264",
                "choices": ["libx264", "libx265", "mpeg4", "libvpx-vp9", "copy"],
                "help": "输出纯音频时会自动忽略视频编码器。",
            },
            {
                "name": "audio_codec",
                "label": "音频编码器 -c:a",
                "default": "aac",
                "choices": ["aac", "libmp3lame", "libopus", "flac", "pcm_s16le", "copy"],
                "help": "输出纯视频时会自动忽略音频编码器。",
            },
            {
                "name": "preset",
                "label": "视频编码速度 -preset",
                "default": "medium",
                "choices": ["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow"],
                "help": "主要用于 libx264/libx265，其他编码器可能忽略或不支持。",
            },
            {
                "name": "crf",
                "label": "视频质量 CRF",
                "default": "23",
                "placeholder": "23",
                "help": "数值越小质量越高；常用 18-28。",
            },
            {
                "name": "video_bitrate",
                "label": "视频码率 -b:v（可选）",
                "default": "",
                "placeholder": "2500k",
                "help": "留空则不追加 -b:v。",
            },
            {
                "name": "audio_bitrate",
                "label": "音频码率 -b:a",
                "default": "128k",
                "placeholder": "128k",
                "help": "当音频编码器为 copy 时会自动忽略。",
            },
            {
                "name": "force_format",
                "label": "强制 muxer -f（可选）",
                "default": "",
                "placeholder": "mp4 / matroska / webm",
                "help": "通常留空即可；mkv 如需强制 muxer 可填 matroska。",
            },
        ],
    },
    {
        "id": "video_resize",
        "category": "视频处理",
        "title": "视频缩放",
        "description": "调整视频分辨率，可固定宽高或使用 -1 保持比例。",
        "tool": "ffmpeg",
        "output_ext": "mp4",
        "example": "ffmpeg -y -i input.mp4 -vf scale=1280:-1 output.mp4",
        "docs": ["-vf：视频滤镜。", "scale=1280:-1 表示宽 1280，高度按比例自动计算。"],
        "args": ["-vf", "scale={width}:{height}"],
        "params": [
            {"name": "width", "label": "宽度", "default": "1280", "placeholder": "1280"},
            {"name": "height", "label": "高度", "default": "-1", "placeholder": "-1"},
        ],
    },
    {
        "id": "video_fps",
        "category": "视频处理",
        "title": "调整帧率",
        "description": "设置输出视频帧率。",
        "tool": "ffmpeg",
        "output_ext": "mp4",
        "example": "ffmpeg -y -i input.mp4 -r 30 output.mp4",
        "docs": ["-r：输出帧率。"],
        "args": ["-r", "{fps}"],
        "params": [{"name": "fps", "label": "帧率 -r", "default": "30", "placeholder": "30"}],
    },
    {
        "id": "video_rotate",
        "category": "视频处理",
        "title": "视频旋转",
        "description": "使用 transpose 滤镜旋转视频画面。",
        "tool": "ffmpeg",
        "output_ext": "mp4",
        "example": "ffmpeg -y -i input.mp4 -vf transpose=1 output.mp4",
        "docs": ["transpose=1：顺时针 90 度。", "transpose=2：逆时针 90 度。"],
        "args": ["-vf", "transpose={transpose}"],
        "params": [
            {
                "name": "transpose",
                "label": "旋转模式",
                "default": "1",
                "choices": ["0", "1", "2", "3"],
                "help": "0/3 为不同方向翻转后旋转，1=顺时针 90 度，2=逆时针 90 度。",
            }
        ],
    },
    {
        "id": "extract_frame",
        "category": "图片处理",
        "title": "截取视频画面",
        "description": "从视频指定时间点导出一张图片。",
        "tool": "ffmpeg",
        "output_ext": "jpg",
        "example": "ffmpeg -y -ss 00:00:03 -i input.mp4 -frames:v 1 output.jpg",
        "docs": ["-frames:v 1：只输出一帧视频画面。"],
        "pre_input_args": ["-ss", "{time_point}"],
        "args": ["-frames:v", "1"],
        "params": [
            {
                "name": "time_point",
                "label": "截图时间 -ss",
                "default": "00:00:03",
                "placeholder": "00:00:03",
            }
        ],
    },
    {
        "id": "image_resize",
        "category": "图片处理",
        "title": "图片缩放",
        "description": "使用 FFmpeg 对图片进行缩放。",
        "tool": "ffmpeg",
        "output_ext": "png",
        "example": "ffmpeg -y -i input.jpg -vf scale=800:-1 output.png",
        "docs": ["图片同样可以使用 -vf scale 滤镜。"],
        "args": ["-vf", "scale={width}:{height}"],
        "params": [
            {"name": "width", "label": "宽度", "default": "800", "placeholder": "800"},
            {"name": "height", "label": "高度", "default": "-1", "placeholder": "-1"},
        ],
    },
    {
        "id": "gif_create",
        "category": "图片处理",
        "title": "视频转 GIF",
        "description": "从视频生成 GIF 动图。",
        "tool": "ffmpeg",
        "output_ext": "gif",
        "example": "ffmpeg -y -i input.mp4 -vf fps=12,scale=480:-1 output.gif",
        "docs": ["fps：GIF 帧率。", "scale：GIF 尺寸。"],
        "args": ["-vf", "fps={fps},scale={width}:{height}"],
        "params": [
            {"name": "fps", "label": "GIF 帧率", "default": "12", "placeholder": "12"},
            {"name": "width", "label": "宽度", "default": "480", "placeholder": "480"},
            {"name": "height", "label": "高度", "default": "-1", "placeholder": "-1"},
        ],
    },
    {
        "id": "media_probe",
        "category": "媒体信息",
        "title": "查看媒体信息",
        "description": "调用 ffprobe 输出格式、码率、时长、视频流和音频流信息。",
        "tool": "ffprobe",
        "output_ext": "json",
        "example": "ffprobe -hide_banner -show_format -show_streams -print_format json input.mp4",
        "docs": ["ffprobe 用于分析媒体文件元数据，不改变原文件。"],
        "args": ["-hide_banner", "-show_format", "-show_streams", "-print_format", "json"],
        "params": [],
    },
    {
        "id": "custom_ffmpeg",
        "category": "高级",
        "title": "自定义 FFmpeg 参数",
        "description": "上传输入文件后，自定义 -i 之后、输出文件之前的参数。",
        "tool": "ffmpeg",
        "output_ext": "{format}",
        "example": "ffmpeg -y -i input.mp4 <自定义参数> output.mp4",
        "docs": ["适合未在功能目录中列出的参数组合。不要在这里填写输入文件和输出文件。"],
        "args": [],
        "params": [
            {
                "name": "format",
                "label": "输出格式",
                "default": "mp4",
                "placeholder": "mp4",
                "help": "例如 mp4、wav、jpg、gif。",
            }
        ],
        "allow_custom_args": True,
    },
]


def get_feature(feature_id):
    """Return a single feature definition by id."""
    return next((feature for feature in FEATURES if feature["id"] == feature_id), None)


def grouped_features():
    """Return features grouped by category while preserving declaration order."""
    groups = {}
    for feature in FEATURES:
        groups.setdefault(feature["category"], []).append(feature)
    return groups


# Recommended codec combinations per container (used for validation and UI presets).
FORMAT_PRESETS = {
    "mp4": {
        "stream_mode": "audio_video",
        "video_codecs": ["libx264", "libx265", "mpeg4", "copy"],
        "audio_codecs": ["aac", "libmp3lame", "copy"],
        "default_video": "libx264",
        "default_audio": "aac",
        "force_format": "",
    },
    "mkv": {
        "stream_mode": "audio_video",
        "video_codecs": ["libx264", "libx265", "libvpx-vp9", "mpeg4", "copy"],
        "audio_codecs": ["aac", "libopus", "flac", "libmp3lame", "copy"],
        "default_video": "libx264",
        "default_audio": "aac",
        "force_format": "matroska",
    },
    "webm": {
        "stream_mode": "audio_video",
        "video_codecs": ["libvpx-vp9", "copy"],
        "audio_codecs": ["libopus", "copy"],
        "default_video": "libvpx-vp9",
        "default_audio": "libopus",
        "force_format": "webm",
    },
    "mov": {
        "stream_mode": "audio_video",
        "video_codecs": ["libx264", "libx265", "mpeg4", "copy"],
        "audio_codecs": ["aac", "libmp3lame", "copy"],
        "default_video": "libx264",
        "default_audio": "aac",
        "force_format": "",
    },
    "avi": {
        "stream_mode": "audio_video",
        "video_codecs": ["mpeg4", "libx264", "copy"],
        "audio_codecs": ["libmp3lame", "aac", "copy"],
        "default_video": "mpeg4",
        "default_audio": "libmp3lame",
        "force_format": "",
    },
    "mp3": {
        "stream_mode": "audio_only",
        "video_codecs": [],
        "audio_codecs": ["libmp3lame", "copy"],
        "default_video": "",
        "default_audio": "libmp3lame",
        "force_format": "",
    },
    "wav": {
        "stream_mode": "audio_only",
        "video_codecs": [],
        "audio_codecs": ["pcm_s16le", "copy"],
        "default_video": "",
        "default_audio": "pcm_s16le",
        "force_format": "",
    },
    "flac": {
        "stream_mode": "audio_only",
        "video_codecs": [],
        "audio_codecs": ["flac", "copy"],
        "default_video": "",
        "default_audio": "flac",
        "force_format": "",
    },
    "ogg": {
        "stream_mode": "audio_only",
        "video_codecs": [],
        "audio_codecs": ["libopus", "copy"],
        "default_video": "",
        "default_audio": "libopus",
        "force_format": "",
    },
    "m4a": {
        "stream_mode": "audio_only",
        "video_codecs": [],
        "audio_codecs": ["aac", "copy"],
        "default_video": "",
        "default_audio": "aac",
        "force_format": "",
    },
}


def validate_container_codec(values: dict) -> str | None:
    """Return an error message when the format/codec combination is invalid."""
    container = values.get("container_format", "mp4").lower().strip().lstrip(".")
    preset = FORMAT_PRESETS.get(container)
    if not preset:
        return f"不支持的封装格式：{container}"

    stream_mode = values.get("stream_mode", preset["stream_mode"])
    if preset["stream_mode"] == "audio_only" and stream_mode != "audio_only":
        return f"{container} 为纯音频封装，请将输出流类型设为“仅音频”。"

    video_codec = values.get("video_codec", "")
    audio_codec = values.get("audio_codec", "")

    if stream_mode != "audio_only" and video_codec and video_codec not in preset["video_codecs"]:
        allowed = "、".join(preset["video_codecs"]) or "无"
        return f"{container} 不支持视频编码器 {video_codec}，可选：{allowed}。"

    if stream_mode != "video_only" and audio_codec and audio_codec not in preset["audio_codecs"]:
        allowed = "、".join(preset["audio_codecs"]) or "无"
        return f"{container} 不支持音频编码器 {audio_codec}，可选：{allowed}。"

    return None
