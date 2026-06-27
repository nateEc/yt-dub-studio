# YouTube Dubbing + Lip Sync Pipeline

Voice-Pro now exposes a standard one-click entry in the **Dubbing Studio** tab:

```text
YouTube URL
-> download media
-> transcribe speech
-> translate subtitles
-> synthesize target-language speech with Edge/Azure TTS
-> mix dubbed speech with instrumental audio
-> optionally run lip sync
-> output final video, audio, subtitles, and intermediate files
```

The same pipeline can be run from the command line:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID"
```

On a fresh checkout, initialize the Voice-Pro environment first:

```bash
GPU_CHOICE=C ./start.sh --install-only
```

On Apple Silicon macOS, `start.sh` selects the arm64 Miniconda installer automatically.
After the environment is created, run CLI commands with:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID"
```

For a quick end-to-end smoke test on a long YouTube video, trim the downloaded media before ASR/TTS/lip sync:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" \
  --clip-start-seconds 120 \
  --clip-seconds 12 \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

Useful overrides:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" \
  --source-language English \
  --target-language "Chinese (simplified)" \
  --media-language english \
  --tts-strategy source_voice \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip
```

By default, the YouTube pipeline uses `--tts-strategy source_voice`. This extracts the original video's vocals as a reference and uses CosyVoice cross-lingual synthesis so the Chinese dub keeps the source speaker's timbre as much as possible. The old Edge/Azure TTS path is still available explicitly:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" --tts-strategy edge
```

If source-voice cloning fails, the pipeline fails loudly by default instead of silently producing a generic TTS voice. To allow a fallback to Edge/Azure TTS:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" --allow-edge-tts-fallback
```

The first source-voice run needs the CosyVoice runtime model, which is large. With asset bootstrapping enabled, the pipeline downloads the `cosyvoice` model files automatically. CosyVoice also needs the local Matcha-TTS package:

```bash
installer_files/env/bin/python -m pip install -e third_party/Matcha-TTS --no-deps
```

Subtitle-based CosyVoice output is time-fitted back into each original subtitle slot, so translated speech does not overrun the video or drift before lip sync.

Use `--enable-lip-sync` when `app/config-user.json5` has lip sync disabled but you want this CLI run to use it.

Use `--no-audio-only-fallback` when a real lip-sync result is required:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" --enable-lip-sync --no-audio-only-fallback
```

In this mode, a MuseTalk/Wav2Lip runtime failure fails the pipeline instead of silently returning a plain audio-replaced video.

Check runtime and lip-sync configuration before spending time on ASR/TTS:

```bash
python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" --preflight --enable-lip-sync --no-audio-only-fallback
```

## Lip Sync Engines

The lip-sync layer is intentionally an external adapter so MuseTalk/Wav2Lip can live in their own Python environments without conflicting with Voice-Pro's Torch/CUDA stack.

### MuseTalk

Set these environment variables before launching Voice-Pro:

```bash
export MUSETALK_DIR=/absolute/path/to/MuseTalk
export MUSETALK_PYTHON=/absolute/path/to/musetalk-env/bin/python
```

Optional overrides:

```bash
export MUSETALK_FFMPEG_PATH=/absolute/path/to/ffmpeg/bin
export MUSETALK_UNET_MODEL_PATH=/absolute/path/to/unet.pth
export MUSETALK_UNET_CONFIG=/absolute/path/to/musetalk.json
export MUSETALK_VERSION=v15
```

The adapter creates a temporary inference YAML with:

```yaml
task_0:
  video_path: /absolute/path/to/source.mp4
  audio_path: /absolute/path/to/dubbed.wav
```

Then it runs:

```bash
python -m scripts.inference --inference_config <generated.yaml> --result_dir <workspace/lipsync/run> --bbox_shift <value> --version v15
```

### Wav2Lip

Wav2Lip is the recommended local smoke-test engine for macOS/CPU setups. Install the project-local runtime once:

```bash
installer_files/env/bin/python scripts/setup-wav2lip-runtime.py
```

This clones Wav2Lip into:

```text
workspace/runtimes/Wav2Lip
```

and downloads runtime weights into:

```text
model/wav2lip/checkpoints/wav2lip_gan.pth
```

The setup script also applies two compatibility patches needed by the current Voice-Pro environment:

- `librosa.filters.mel(...)` uses keyword-only arguments in newer librosa.
- The downloaded Wav2Lip checkpoint can be a TorchScript module instead of the older `state_dict` format.

After setup, strict preflight should succeed without extra environment variables:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" \
  --preflight \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

Then run the full pipeline:

```bash
installer_files/env/bin/python run-youtube-pipeline.py "https://youtu.be/VIDEO_ID" \
  --source-language English \
  --target-language "Chinese (simplified)" \
  --media-language english \
  --enable-lip-sync \
  --lip-sync-engine Wav2Lip \
  --no-audio-only-fallback
```

Wav2Lip needs a visible, detectable face in the source video. If the video has no face, heavy occlusion, extreme side profiles, or frequent scene cuts, strict mode will fail and fallback mode will return an audio-replaced video.

You can still point Voice-Pro to a custom Wav2Lip checkout:

Set these environment variables before launching Voice-Pro:

```bash
export WAV2LIP_DIR=/absolute/path/to/Wav2Lip
export WAV2LIP_PYTHON=/absolute/path/to/wav2lip-env/bin/python
export WAV2LIP_CHECKPOINT=/absolute/path/to/wav2lip_gan.pth
```

Optional CPU-friendly overrides:

```bash
export WAV2LIP_FACE_DET_BATCH_SIZE=1
export WAV2LIP_BATCH_SIZE=4
export WAV2LIP_RESIZE_FACTOR=1
export WAV2LIP_PADS="0 10 0 0"
export WAV2LIP_BOX="-1 -1 -1 -1"
export WAV2LIP_NOSMOOTH=false
```

The adapter runs:

```bash
python inference.py \
  --checkpoint_path <checkpoint> \
  --face <copied_source_video> \
  --audio <copied_dubbed_audio> \
  --outfile <temporary_output_video>
```

The adapter copies source media into a temporary Wav2Lip work folder before inference. This avoids failures in the upstream script when YouTube titles create file paths with spaces.

## Smoke Fallback

When lip sync is enabled but the selected external engine is not configured, Voice-Pro can generate an audio-only fallback video. This keeps the full pipeline testable, but it does **not** change mouth motion.

Disable **Allow audio-only fallback** when you want the pipeline to fail loudly unless a real lip-sync engine succeeds.
