# Setup Guide

This guide walks through installing yt-dub-studio, launching the web app, running the CLI pipeline, preparing Wav2Lip, and troubleshooting common setup issues.

Language: [中文](setup.md) | English

## 1. Clone

```bash
git clone https://github.com/nateEc/yt-dub-studio.git
cd yt-dub-studio
```

Use a path without spaces or special characters. The bundled Miniconda setup is sensitive to paths like `~/My Projects/yt-dub-studio`.

Recommended:

```text
~/dev/yt-dub-studio
```

## 2. System Requirements

Recommended environment:

- macOS or Linux.
- `git` and `ffmpeg`.
- Python environment managed by the project under `installer_files/env`.
- 16GB+ RAM.
- NVIDIA GPU recommended for faster inference; CPU works but is much slower.

Expected first-run downloads:

- CosyVoice runtime/model assets.
- Demucs model files.
- Wav2Lip runtime and checkpoint if lip sync is enabled.

These local folders are intentionally ignored by git:

```text
installer_files/
model/
workspace/
```

## 3. Install System Dependencies

macOS/Linux:

```bash
./configure.sh
```

What it does:

- macOS: checks Homebrew and installs `git`/`ffmpeg` when needed.
- Linux: uses the detected package manager to install `git`, `ffmpeg`, and build tools.

If you prefer manual installation, make sure these commands work:

```bash
git --version
ffmpeg -version
```

## 4. Create The Python Environment

CPU environment:

```bash
GPU_CHOICE=C ./start.sh --install-only
```

NVIDIA GPU environment:

```bash
GPU_CHOICE=G ./start.sh --install-only
```

After installation, use this Python for all commands:

```bash
installer_files/env/bin/python
```

Check it:

```bash
installer_files/env/bin/python --version
```

## 5. Install Matcha-TTS For CosyVoice

CosyVoice depends on the local Matcha-TTS package:

```bash
installer_files/env/bin/python -m pip install -e third_party/Matcha-TTS --no-deps
```

## 6. Prepare Wav2Lip

Run this once if you want lip sync:

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```

The script will:

- clone Wav2Lip into `workspace/runtimes/Wav2Lip`
- download the checkpoint to `model/wav2lip/checkpoints/wav2lip_gan.pth`
- patch Wav2Lip for the current Python/Torch/librosa stack
- preserve frames without detected faces instead of failing the whole video
- support sampled face detection for faster CPU/macOS smoke tests

If you only want to test dubbing first, skip this step and disable lip sync in the UI.

## 7. Launch The Web App

Dedicated YouTube Pipeline UI:

```bash
installer_files/env/bin/python start-youtube-pipeline.py
```

Open:

```text
http://127.0.0.1:7861
```

Recommended defaults for English YouTube to Chinese dubbing:

- Source language: `English`
- Target language: `Chinese (simplified)`
- ASR: `faster-whisper`
- TTS strategy: `CosyVoice` source voice
- Lip sync engine: `Wav2Lip`
- Video quality: `low`

You can also start the full Voice-Pro app, which includes a `YouTube Pipeline` tab:

```bash
installer_files/env/bin/python start-abus.py
```

## 8. Run From CLI

Full pipeline:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --source-language English \
  --target-language "Chinese (simplified)" \
  --media-language english \
  --tts-strategy source_voice \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

Short smoke test:

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

Preflight only:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --preflight \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

Strict lip-sync mode:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

In strict mode, the pipeline fails if real lip sync cannot be produced. Without strict mode, it may return an audio-replaced fallback video.

## 9. Source-Voice Dubbing

The default TTS strategy is:

```bash
--tts-strategy source_voice
```

This means the pipeline will:

1. separate vocals from the source video
2. extract a reference clip from the original speaker
3. synthesize Chinese speech with CosyVoice Cross-Lingual mode
4. fit each translated segment back into its source subtitle time slot

By default, source-voice failure is loud. The pipeline does not silently switch to a generic TTS voice.

If you explicitly want generic Edge/Azure fallback:

```bash
--allow-edge-tts-fallback
```

If you want to use generic Edge/Azure TTS directly:

```bash
--tts-strategy edge
```

## 10. Outputs

Generated files are stored under:

```text
workspace/
```

Typical outputs:

- downloaded source video
- extracted audio
- separated vocal/instrumental tracks
- source subtitles
- Chinese subtitles
- source-voice Chinese dub audio
- audio-replaced video
- Wav2Lip lip-synced video
- final video surfaced in the Gradio UI

## 11. Optional Azure Configuration

The default pipeline does not require OpenAI tokens.

If you want Azure Translator or Azure TTS:

```bash
cp .env.example .env
```

Then fill in:

```text
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
AZURE_TRANSLATOR_KEY=
AZURE_TRANSLATOR_ENDPOINT=
AZURE_TRANSLATOR_REGION=
```

`.env` is ignored by git. Do not commit it.

## 12. Run Tests

Pipeline tests:

```bash
installer_files/env/bin/python -m unittest \
  tests.test_pipeline_estimate \
  tests.test_lipsync_runner \
  tests.test_pipeline_cli
```

Compile check:

```bash
installer_files/env/bin/python -m compileall -q \
  app src tests run-youtube-pipeline.py start-youtube-pipeline.py \
  scripts/setup-wav2lip-runtime.py cosyvoice/cli/cosyvoice.py
```

## FAQ

### First run is slow

Expected. The first run may download models and warm up local caches. Source-voice dubbing plus lip sync is computationally heavy.

### Five minutes of video takes close to an hour

That is realistic on CPU/macOS. GPU acceleration, shorter clips, smaller ASR models, and disabling lip sync can reduce runtime.

### Wav2Lip does not change the mouth

Check:

- `scripts/setup-wav2lip-runtime.py` completed successfully.
- The source video has a visible face.
- Lip sync is enabled in the UI or CLI.
- Strict mode is enabled if you want failure instead of fallback:

```bash
--no-audio-only-fallback
```

### YouTube download fails

Update yt-dlp:

```bash
installer_files/env/bin/python -m pip install -U yt-dlp
```

Some videos require login, region access, or cookies. This project does not currently include cookies management.

### macOS shows torchvision/libjpeg warnings

Usually safe to ignore for this workflow. The warning comes from torchvision's optional image extension and does not block the Gradio UI or the video/audio pipeline.

### The installer fails because of the project path

Move the repository to a simpler path:

```text
~/dev/yt-dub-studio
```

Then re-run the setup commands.

## More Docs

- [README](README.en.md)
- [中文 README](../README.md)
- [YouTube Pipeline App](youtube-pipeline-app.md)
- [Lip Sync Pipeline](lipsync-pipeline.md)
