# yt-dub-studio

把 YouTube 英文视频转换成中文配音视频的本地工作台。当前默认链路会尽量保留源视频说话人的音色，并可选使用 Wav2Lip 做唇形同步。

本项目基于 [Voice-Pro](https://github.com/abus-aikorea/voice-pro) 改造，保留原项目的 ASR、翻译、TTS、Demucs、CosyVoice 等能力，并新增一条面向 YouTube 到中文成片的完整 pipeline。

## 能做什么

- 下载 YouTube 视频。
- 使用 Whisper/faster-whisper 转写英文字幕。
- 翻译成中文简体。
- 用 CosyVoice 基于原视频人声生成中文源音色配音。
- 使用 Demucs 分离人声和伴奏，并把中文配音混回伴奏。
- 可选用 Wav2Lip 做口型同步。
- 输出成片、中文配音音频、原文字幕、中文字幕和中间文件。

## 环境要求

推荐环境：

- macOS 或 Linux。
- Python 环境由项目脚本自动安装到 `installer_files/env`。
- `git`、`ffmpeg`。
- 至少 16GB 内存。源音色 + 唇形同步会更吃内存和时间。
- NVIDIA GPU 会明显加速；CPU 也可以跑，但 5 分钟视频可能需要接近 1 小时甚至更久。

注意：

- 首次运行会下载较大的模型和资源，例如 CosyVoice、Demucs、Wav2Lip checkpoint。
- `installer_files/`、`model/`、`workspace/` 都不会提交到 git，需要每台机器本地准备。
- 当前 pipeline 默认不消耗 OpenAI token。翻译默认走 Deep Translator；如果配置 Azure Translator，会消耗 Azure 翻译请求。

## 快速开始

### 1. Clone

```bash
git clone https://github.com/nateEc/yt-dub-studio.git
cd yt-dub-studio
```

建议把项目放在没有空格和特殊字符的路径下，Miniconda 静默安装对路径比较挑剔。

### 2. 安装系统依赖

macOS/Linux:

```bash
./configure.sh
```

这个脚本会检查并安装 `git`、`ffmpeg` 等系统依赖。macOS 会使用 Homebrew，Linux 会按当前发行版使用 apt/yum/dnf/pacman。

### 3. 创建 Python/Conda 环境

CPU 环境：

```bash
GPU_CHOICE=C ./start.sh --install-only
```

NVIDIA GPU 环境：

```bash
GPU_CHOICE=G ./start.sh --install-only
```

安装完成后，项目会生成：

```text
installer_files/env/bin/python
```

后续所有命令都建议使用这个 Python。

### 4. 安装 Matcha-TTS 本地包

CosyVoice 依赖本项目里的 Matcha-TTS：

```bash
installer_files/env/bin/python -m pip install -e third_party/Matcha-TTS --no-deps
```

### 5. 准备 Wav2Lip

如果你需要口型同步，运行：

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```

它会：

- clone Wav2Lip 到 `workspace/runtimes/Wav2Lip`。
- 下载 checkpoint 到 `model/wav2lip/checkpoints/wav2lip_gan.pth`。
- 应用兼容补丁，适配当前 Python/Torch/librosa 环境。
- 允许无人脸帧保留原画面，避免整条视频直接失败。

如果暂时只想验证配音链路，可以先跳过这一步，在页面里关闭唇形同步。

## 启动 Web 应用

启动专用 YouTube Pipeline 页面：

```bash
installer_files/env/bin/python start-youtube-pipeline.py
```

默认地址：

```text
http://127.0.0.1:7861
```

页面默认设置适合英文 YouTube 到中文配音：

- 源语言：English
- 目标语言：Chinese (simplified)
- ASR：faster-whisper
- TTS：CosyVoice 源音色
- 唇形引擎：Wav2Lip
- 视频质量：low

也可以启动完整 Voice-Pro 应用，里面会有 `YouTube Pipeline` tab：

```bash
installer_files/env/bin/python start-abus.py
```

## 命令行运行

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

先跑一个短片段 smoke test：

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

只做运行时检查，不处理视频：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --preflight \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

如果你必须保证真实口型同步成功，而不是失败后输出仅换音轨视频：

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

## 源音色策略

默认 `--tts-strategy source_voice`，也就是：

1. 从源视频中分离出原始人声。
2. 截取一段参考音频。
3. 使用 CosyVoice Cross-Lingual 模式生成中文配音。
4. 将每句中文音频按字幕时间槽做时长适配，减少漂移。

默认不会静默降级到普通 Edge TTS。如果 CosyVoice 源音色失败，pipeline 会失败并报错。确实想允许降级时再加：

```bash
--allow-edge-tts-fallback
```

## 输出目录

所有运行产物默认保存在：

```text
workspace/
```

常见输出包括：

- 下载后的源视频。
- 抽取音频。
- 人声/伴奏分离结果。
- 原文字幕。
- 中文字幕。
- 中文配音音频。
- 换音轨视频。
- Wav2Lip 口型同步视频。

`workspace/` 被 git 忽略，可以放心本地生成，不会误提交。

## 可选 Azure 配置

如果你要使用 Azure Translator 或 Azure TTS：

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

`.env` 已经在 `.gitignore` 中，不要提交。

## 测试

运行当前 pipeline 相关测试：

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

## 常见问题

### 1. 首次运行很慢

正常。第一次需要下载模型和初始化缓存。CosyVoice、Demucs、Wav2Lip 都是本地推理链路，模型比较大。

### 2. Wav2Lip 没有改变嘴形

确认：

- 已运行 `scripts/setup-wav2lip-runtime.py`。
- 视频里有人脸且画面清晰。
- 页面或 CLI 中启用了唇形同步。
- 如果想强制失败而不是输出换音轨 fallback，使用 `--no-audio-only-fallback`。

### 3. YouTube 下载失败

更新 yt-dlp：

```bash
installer_files/env/bin/python -m pip install -U yt-dlp
```

有些视频需要登录、地区权限或 cookies，本项目目前不内置 cookies 管理。

### 4. macOS 上 torchvision/libjpeg warning

如果只是启动页面或跑当前 pipeline，通常可以忽略。它来自 torchvision image extension，没有影响 Gradio 页面和常规音视频 pipeline。

### 5. 路径里有空格导致安装失败

把项目移到没有空格和特殊字符的路径，例如：

```text
~/dev/yt-dub-studio
```

然后重新运行安装步骤。

## 项目结构

```text
app/tab_youtube_pipeline.py       Web UI
app/abus_pipeline.py              YouTube pipeline 编排
app/abus_lipsync.py               MuseTalk/Wav2Lip 适配层
app/abus_pipeline_estimate.py     耗时/消耗估算
run-youtube-pipeline.py           CLI 入口
start-youtube-pipeline.py         专用 Gradio 应用入口
scripts/setup-wav2lip-runtime.py  Wav2Lip runtime 准备脚本
docs/youtube-pipeline-app.md      Pipeline 应用说明
docs/lipsync-pipeline.md          唇形同步说明
tests/                            Pipeline 相关测试
```

## 许可证和来源

本项目基于 Voice-Pro 改造，仓库保留原始 GPLv3 `LICENSE`。使用、分发和二次开发请遵守该许可证以及依赖模型/第三方项目各自的许可证。
