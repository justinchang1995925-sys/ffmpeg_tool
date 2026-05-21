# ffmpeg-media-processing Skill

把整个 `ffmpeg-media-processing` 文件夹发给其他人即可。

## 安装位置

个人全局使用：

```text
~/.cursor/skills/ffmpeg-media-processing/
```

项目内共享：

```text
.cursor/skills/ffmpeg-media-processing/
```

## 触发方式

在 Cursor 中向 agent 描述媒体处理需求，例如：

```text
使用 ffmpeg 把 input.wav 转成单声道、16000Hz、512k，输出 output.wav
```

```text
帮我从 video.mp4 的 00:00:03 截一张 jpg
```

```text
分析这个 mp4 的媒体信息
```

agent 会读取 `SKILL.md`，参考 `COMMANDS.md`，并可调用 `scripts/ffmpeg_media.py` 执行对应命令。
