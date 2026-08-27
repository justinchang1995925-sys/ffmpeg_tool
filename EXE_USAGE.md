# FFmpegTool.exe 使用说明

把 `dist/FFmpegTool.exe` 发给对方即可运行。

## 使用方式

1. 双击 `FFmpegTool.exe`。
2. 程序会启动本地 Web 服务并自动打开浏览器。
3. 如果浏览器没有自动打开，手动访问：

```text
http://127.0.0.1:5000
```

4. 第一次使用可在页面中点击“下载并安装”安装 FFmpeg。

## 运行时文件

exe 所在目录会自动创建：

- `uploads/`：上传的原始文件
- `outputs/`：处理后的结果文件
- `.ffmpeg_tool_config.json`：FFmpeg 路径配置

## 注意

- 这是本地工具，不需要公网服务器。
- 运行期间不要关闭弹出的控制台窗口。
- 若 5000 端口被占用，请先关闭占用该端口的程序。
