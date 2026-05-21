# FFmpeg 音视频图片处理 Web 工具

这是一个基于 Python Flask 的本地 Web 工具，用于下载/安装 FFmpeg，并通过网页执行常见音频、视频、图片处理命令。

## 功能

- 一键下载 Windows FFmpeg release essentials ZIP。
- 可指定安装路径，自动解压并保存 `ffmpeg.exe` / `ffprobe.exe` 位置。
- 写入当前用户 `PATH`，新打开的终端可直接使用 `ffmpeg`。
- 按单个功能展示参数、说明和示例命令。
- 支持上传文件、执行处理、查看命令输出并下载结果。
- 支持高级自定义 FFmpeg 参数。

## 运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

然后打开：

```text
http://127.0.0.1:5000
```

## 已内置的单个功能

- 音视频参数转换：`-ac`、`-ar`、`-b:a`
- 从视频提取音频：`-vn`、`-c:a`、`-b:a`
- 调整音量：`-filter:a volume=...`
- 截取片段：`-ss`、`-t`、`-c`
- 视频转码：`-c:v`、`-preset`、`-crf`、`-c:a`
- 视频缩放：`-vf scale=...`
- 调整帧率：`-r`
- 视频旋转：`-vf transpose=...`
- 截取视频画面：`-frames:v 1`
- 图片缩放：`-vf scale=...`
- 视频转 GIF：`fps`、`scale`
- 查看媒体信息：`ffprobe`
- 自定义 FFmpeg 参数

## 说明

FFmpeg 官方下载页说明 Windows 可执行包由第三方构建提供。本工具默认使用 ffmpeg.org 下载页推荐的 gyan.dev release essentials ZIP：

```text
https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip
```

FFmpeg 的完整能力非常大，包含上千个编解码器、封装格式、滤镜和协议。本项目把常用能力先做成独立功能卡片，并提供自定义参数入口；后续可以继续在 `ffmpeg_features.py` 中追加功能定义。
