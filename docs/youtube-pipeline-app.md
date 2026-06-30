# YouTube Pipeline App

这个应用把 YouTube 英文视频到中文配音视频的链路收成一个入口：

1. 下载 YouTube 视频。
2. 抽取音频并转写字幕。
3. 翻译成中文。
4. 使用 CosyVoice 基于原视频人声生成中文源音色配音。
5. 混回伴奏。
6. 可选使用 Wav2Lip 做唇形同步。
7. 输出最终视频、音频、字幕和中间文件。

## 启动

```bash
installer_files/env/bin/python start-youtube-pipeline.py
```

应用默认监听 `7861`，启动后在页面里输入 YouTube URL，点击 `开始生成` 即可。高级设置可以保持默认：

- 输出语言：`Chinese (simplified)`
- TTS：`CosyVoice` source voice
- 唇形同步：`Wav2Lip`
- 视频质量：`low`
- ASR：`faster-whisper`

## 耗时和资源

页面会显示粗略估算和实际耗时。当前链路默认不消耗 OpenAI token：

- ASR 是本地 Whisper/faster-whisper 推理。
- 翻译走 Deep/Azure 翻译请求，主要按字幕字符/请求消耗。
- CosyVoice 源音色配音是本地推理，主要消耗 CPU/GPU 和内存。
- Wav2Lip 是本地推理，主要消耗 CPU/GPU；无人脸帧会保留原画面。
- `workspace/` 会保存下载视频、抽取音频、人声/伴奏、字幕、配音和最终视频。

按当前机器实测，5 分钟视频使用源音色 + Wav2Lip 大约需要 50-60 分钟。不同 ASR 模型、视频时长、是否启用 GPU、是否启用唇形同步都会显著影响耗时。

## 运行进度

长任务会按阶段记录和展示进度：

1. 下载源视频
2. ASR 转写
3. 翻译字幕
4. 源音色 TTS
5. 混音
6. Wav2Lip
7. 导出

Web UI 会在运行时更新 Gradio 进度条，完成后在运行状态里展示每个阶段的开始时间、结束时间、耗时、产物路径和错误原因。

CLI 会把阶段事件以 JSON Lines 写到 `stderr`，最终结果 JSON 写到 `stdout`。最终 JSON 中的 `stages` 字段包含完整阶段记录，适合脚本或自动化系统读取。

## 质量报告

每次运行都会生成一份质量报告 summary，并在 Web UI 的 `质量报告` tab 展示，同时保存到：

```text
workspace/reports/
```

报告会同时写出 Markdown 和 JSON，内容包括视频时长、处理耗时、字幕段数、目标音频总时长、音视频时长差、是否使用 source voice、是否发生 Edge fallback、是否真实执行 Wav2Lip、是否 fallback 成换轨视频，以及输出文件列表。CLI 最终 JSON 也会包含同样的 `quality_report` 字段。

## Wav2Lip 注意事项

项目的 Wav2Lip setup patch 会启用两项适合屏幕录制/讲解视频的行为：

- `WAV2LIP_FACE_DET_STRIDE` 采样检测人脸，默认由应用配置传入 `15`，避免逐帧检测过慢。
- 检测不到人脸的帧会保留原帧，不会让整条视频失败。

如果需要重新安装 Wav2Lip runtime：

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```
