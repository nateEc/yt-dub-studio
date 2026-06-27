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

## Wav2Lip 注意事项

项目的 Wav2Lip setup patch 会启用两项适合屏幕录制/讲解视频的行为：

- `WAV2LIP_FACE_DET_STRIDE` 采样检测人脸，默认由应用配置传入 `15`，避免逐帧检测过慢。
- 检测不到人脸的帧会保留原帧，不会让整条视频失败。

如果需要重新安装 Wav2Lip runtime：

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```
