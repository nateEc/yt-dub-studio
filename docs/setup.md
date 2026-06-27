# 安装指南

这份文档介绍如何安装 yt-dub-studio、启动 Web App、运行 CLI pipeline、准备 Wav2Lip，以及排查常见问题。

语言：中文 | [English](setup.en.md)

## 1. Clone

```bash
git clone https://github.com/nateEc/yt-dub-studio.git
cd yt-dub-studio
```

建议把项目放在没有空格和特殊字符的路径下。项目内置的 Miniconda 安装流程对路径比较敏感，例如 `~/My Projects/yt-dub-studio` 这类路径可能导致安装失败。

推荐路径：

```text
~/dev/yt-dub-studio
```

## 2. 系统要求

推荐环境：

- macOS 或 Linux。
- 已安装或可自动安装 `git` 和 `ffmpeg`。
- Python 环境由项目脚本安装到 `installer_files/env`。
- 16GB 以上内存。
- NVIDIA GPU 会明显加速；CPU 也能跑，但速度会慢很多。

首次运行可能会下载：

- CosyVoice runtime/model 资源。
- Demucs 模型文件。
- 如果启用唇形同步，还会下载 Wav2Lip runtime 和 checkpoint。

这些本地目录已被 git 忽略：

```text
installer_files/
model/
workspace/
```

## 3. 安装系统依赖

macOS/Linux：

```bash
./configure.sh
```

这个脚本会做什么：

- macOS：检查 Homebrew，并在需要时安装 `git`/`ffmpeg`。
- Linux：使用当前发行版的包管理器安装 `git`、`ffmpeg` 和构建工具。

如果你想手动安装，确保这些命令可用：

```bash
git --version
ffmpeg -version
```

## 4. 创建 Python 环境

CPU 环境：

```bash
GPU_CHOICE=C ./start.sh --install-only
```

NVIDIA GPU 环境：

```bash
GPU_CHOICE=G ./start.sh --install-only
```

安装完成后，后续命令都建议使用这个 Python：

```bash
installer_files/env/bin/python
```

检查环境：

```bash
installer_files/env/bin/python --version
```

## 5. 安装 Matcha-TTS

CosyVoice 依赖项目里的本地 Matcha-TTS 包：

```bash
installer_files/env/bin/python -m pip install -e third_party/Matcha-TTS --no-deps
```

## 6. 准备 Wav2Lip

如果你需要唇形同步，先运行一次：

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```

这个脚本会：

- clone Wav2Lip 到 `workspace/runtimes/Wav2Lip`
- 下载 checkpoint 到 `model/wav2lip/checkpoints/wav2lip_gan.pth`
- 为当前 Python/Torch/librosa 环境打兼容补丁
- 对检测不到人脸的帧保留原画面，而不是让整条视频失败
- 支持采样做人脸检测，方便 CPU/macOS 上快速 smoke test

如果你只想先验证配音链路，可以跳过这一步，并在 UI 里关闭唇形同步。

## 7. 启动 Web App

启动专用 YouTube Pipeline 页面：

```bash
installer_files/env/bin/python start-youtube-pipeline.py
```

打开：

```text
http://127.0.0.1:7861
```

英文 YouTube 到中文配音的推荐默认值：

- 源语言：`English`
- 目标语言：`Chinese (simplified)`
- ASR：`faster-whisper`
- TTS 策略：`CosyVoice` 源音色
- 唇形引擎：`Wav2Lip`
- 视频质量：`low`

也可以启动完整 Voice-Pro 应用，其中包含 `YouTube Pipeline` tab：

```bash
installer_files/env/bin/python start-abus.py
```

## 8. 使用 CLI

完整 pipeline：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --source-language English \
  --target-language "Chinese (simplified)" \
  --media-language english \
  --tts-strategy source_voice \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

短片段 smoke test：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --clip-start-seconds 0 \
  --clip-seconds 30 \
  --source-language English \
  --target-language "Chinese (simplified)" \
  --media-language english \
  --tts-strategy source_voice \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

只做 preflight 检查，不处理视频：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --preflight \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

严格唇形同步模式：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

严格模式下，如果真实唇形同步失败，pipeline 会直接失败；非严格模式下，可能返回仅换音轨的视频 fallback。

## 9. 源音色配音

默认 TTS 策略是：

```bash
--tts-strategy source_voice
```

这意味着 pipeline 会：

1. 从源视频分离人声
2. 提取原说话人参考音频
3. 使用 CosyVoice Cross-Lingual 模式生成中文语音
4. 将每段中文配音贴回原字幕时间槽，减少音画漂移

默认情况下，源音色生成失败会明确报错，不会静默切到普通 TTS。

如果你明确想允许 Edge/Azure 普通 TTS fallback：

```bash
--allow-edge-tts-fallback
```

如果想直接使用普通 Edge/Azure TTS：

```bash
--tts-strategy edge
```

## 10. 输出目录

生成文件保存在：

```text
workspace/
```

常见输出包括：

- 下载后的源视频
- 抽取音频
- 分离后的人声/伴奏
- 英文字幕
- 中文字幕
- 源音色中文配音音频
- 换音轨视频
- Wav2Lip 口型同步视频
- Gradio 页面展示的最终成片

## 11. 可选 Azure 配置

默认 pipeline 不需要 OpenAI token。

如果你想使用 Azure Translator 或 Azure TTS：

```bash
cp .env.example .env
```

然后填写：

```text
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_ENDPOINT=
AZURE_TRANSLATOR_REGION=
```

`.env` 已被 git 忽略，不要提交。

## 12. 运行测试

Pipeline tests：

```bash
installer_files/env/bin/python -m unittest \
  tests.test_pipeline_estimate \
  tests.test_lipsync_runner \
  tests.test_pipeline_cli
```

编译检查：

```bash
installer_files/env/bin/python -m compileall -q \
  app src tests run-youtube-pipeline.py start-youtube-pipeline.py \
  scripts/setup-wav2lip-runtime.py cosyvoice/cli/cosyvoice.py
```

## FAQ

### 首次运行很慢

正常。第一次运行可能要下载模型并初始化缓存。源音色配音加唇形同步本身也比较吃计算资源。

### 5 分钟视频接近 1 小时

在 CPU/macOS 上这是现实情况。使用 GPU、缩短 clip、降低 ASR 模型、关闭唇形同步都能减少耗时。

### Wav2Lip 没有改变嘴形

检查：

- `scripts/setup-wav2lip-runtime.py` 是否成功执行。
- 源视频里是否有人脸且画面清楚。
- UI 或 CLI 是否启用了唇形同步。
- 如果你想失败时直接报错而不是 fallback，使用：

```bash
--no-audio-only-fallback
```

### YouTube 下载失败

更新 yt-dlp：

```bash
installer_files/env/bin/python -m pip install -U yt-dlp
```

有些视频需要登录、地区权限或 cookies。当前项目还没有内置 cookies 管理。

### macOS 出现 torchvision/libjpeg warning

通常可以忽略。这个 warning 来自 torchvision 的可选 image extension，不会阻塞 Gradio UI 或当前音视频 pipeline。

### 安装因为路径失败

把仓库移到更简单的路径：

```text
~/dev/yt-dub-studio
```

然后重新执行安装命令。

## 更多文档

- [README](../README.md)
- [English README](README.en.md)
- [YouTube Pipeline 应用说明](youtube-pipeline-app.md)
- [唇形同步说明](lipsync-pipeline.md)
