import argparse
import json
import os
import sys


def build_parser():
    parser = argparse.ArgumentParser(
        description="Run the full YouTube dubbing pipeline: download, transcribe, translate, TTS, and optional lip sync."
    )
    parser.add_argument("youtube_url", help="YouTube URL to process.")
    parser.add_argument("--config", default="app/config-user.json5", help="Path to Voice-Pro user config.")
    parser.add_argument("--video-quality", default=None, choices=["low", "good", "best"])
    parser.add_argument("--audio-format", default=None, choices=["wav", "flac", "mp3"])
    parser.add_argument("--asr-engine", default=None, choices=["faster-whisper", "whisper", "whisper-timestamped", "whisperX"])
    parser.add_argument("--asr-model", default=None)
    parser.add_argument("--media-language", default=None)
    parser.add_argument("--compute-type", default=None)
    parser.add_argument("--denoise-level", type=int, default=None)
    parser.add_argument("--source-language", default=None)
    parser.add_argument("--target-language", default=None)
    parser.add_argument("--voice", default=None)
    parser.add_argument("--pitch", type=int, default=None)
    parser.add_argument("--speech-rate", type=int, default=None)
    parser.add_argument("--volume", type=int, default=None)
    parser.add_argument("--tts-strategy", default=None, choices=["source_voice", "source-voice", "edge"], help="TTS strategy. Default is source_voice, which clones the source video's speaker timbre.")
    parser.add_argument("--source-voice-engine", default=None, choices=["CosyVoice"], help="Voice cloning backend for --tts-strategy source_voice.")
    parser.add_argument("--source-voice-mode", default=None, choices=["Cross-Lingual", "Zero-Shot", "Instruct"], help="CosyVoice inference mode for source voice cloning.")
    parser.add_argument("--source-voice-speed", type=float, default=None, help="Speech speed for source voice cloning. CosyVoice expects roughly 0.3 to 2.0.")
    parser.add_argument("--allow-edge-tts-fallback", action="store_true", help="If source voice cloning fails, fall back to regular Edge/Azure TTS instead of failing.")
    parser.add_argument("--enable-lip-sync", action="store_true", help="Enable lip sync even if the user config disables it.")
    parser.add_argument("--disable-lip-sync", action="store_true")
    parser.add_argument("--lip-sync-engine", default=None, choices=["MuseTalk", "Wav2Lip", "Audio-only fallback", "Disabled"])
    parser.add_argument("--bbox-shift", type=int, default=None)
    parser.add_argument("--no-audio-only-fallback", action="store_true")
    parser.add_argument("--skip-asset-downloads", action="store_true", help="Do not auto-download Voice-Pro assets such as Edge voice metadata and Demucs weights.")
    parser.add_argument("--preflight", action="store_true", help="Only validate runtime and lip-sync configuration; do not process the video.")
    parser.add_argument("--clip-seconds", type=float, default=None, help="Trim downloaded YouTube media to the first N seconds before ASR/TTS/lip sync. Useful for smoke tests.")
    parser.add_argument("--clip-start-seconds", type=float, default=0, help="Start time for --clip-seconds, in seconds from the beginning of the downloaded YouTube media.")
    return parser


def _print_missing_dependency(e: ModuleNotFoundError):
    print(
        json.dumps(
            {
                "ok": False,
                "error": f"Missing runtime dependency: {e.name}",
                "hint": "Run this command inside the Voice-Pro environment created by configure/start, or install requirements-voice-cpu.txt / requirements-voice-gpu.txt first.",
            },
            indent=2,
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )


def _make_cli_progress_callback(stream=None):
    stream = stream or sys.stderr

    def _callback(event):
        stage = event.get("stage", {})
        print(
            json.dumps(
                {
                    "event": event.get("event"),
                    "stage": stage,
                },
                ensure_ascii=False,
            ),
            file=stream,
            flush=True,
        )

    return _callback


def _result_to_dict(result):
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return result.__dict__


def _build_params(args, user_config):
    from app.abus_pipeline import YoutubePipelineParams

    asr_engine = args.asr_engine or user_config.get("asr_engine", "faster-whisper")
    model_key = f"{asr_engine.replace('-', '_')}_model"

    if args.enable_lip_sync:
        lip_sync_enabled = True
    elif args.disable_lip_sync:
        lip_sync_enabled = False
    else:
        lip_sync_enabled = user_config.get("lipsync_enabled", True)

    return YoutubePipelineParams(
        youtube_url=args.youtube_url,
        video_quality=args.video_quality or user_config.get("video_quality", "good"),
        audio_format=args.audio_format or user_config.get("audio_format", "mp3"),
        asr_engine=asr_engine,
        asr_model=args.asr_model or user_config.get(model_key, "base"),
        media_language=args.media_language or user_config.get("whisper_language", "english"),
        compute_type=args.compute_type or user_config.get("whisper_compute_type", "default"),
        denoise_level=args.denoise_level if args.denoise_level is not None else user_config.get("denoise_level", 0),
        source_language=args.source_language or user_config.get("translate_source_language", "English"),
        target_language=args.target_language or user_config.get("translate_target_language", "Chinese (simplified)"),
        voice_name=args.voice or user_config.get("ms_voice", "CHINA-Xiaoxiao-Female"),
        pitch=args.pitch if args.pitch is not None else user_config.get("edge_tts_pitch", 0),
        speech_rate=args.speech_rate if args.speech_rate is not None else user_config.get("edge_tts_rate", 0),
        volume=args.volume if args.volume is not None else user_config.get("edge_tts_volume", 0),
        tts_strategy=(args.tts_strategy or user_config.get("youtube_pipeline_tts_strategy", "source_voice")).replace("-", "_"),
        source_voice_engine=args.source_voice_engine or user_config.get("youtube_pipeline_source_voice_engine", "CosyVoice"),
        source_voice_mode=args.source_voice_mode or user_config.get("youtube_pipeline_source_voice_mode", "Cross-Lingual"),
        source_voice_speed=args.source_voice_speed if args.source_voice_speed is not None else user_config.get("youtube_pipeline_source_voice_speed", 1.0),
        allow_edge_tts_fallback=args.allow_edge_tts_fallback
        or user_config.get("youtube_pipeline_allow_edge_tts_fallback", False),
        lip_sync_enabled=lip_sync_enabled,
        lip_sync_engine=args.lip_sync_engine or user_config.get("lipsync_engine", "MuseTalk"),
        lip_sync_bbox_shift=args.bbox_shift if args.bbox_shift is not None else user_config.get("lipsync_bbox_shift", 0),
        lip_sync_allow_fallback=not args.no_audio_only_fallback
        and user_config.get("lipsync_allow_audio_only_fallback", True),
        bootstrap_assets=not args.skip_asset_downloads,
        clip_seconds=args.clip_seconds,
        clip_start_seconds=args.clip_start_seconds,
    )


def _load_user_config(config_path):
    from src.config import UserConfig

    return UserConfig(config_path)


def _load_gradio_pipeline():
    original_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0]]
        from app.gradio_gulliver import GradioGulliver
    finally:
        sys.argv = original_argv

    return GradioGulliver


def _bootstrap_voice_metadata():
    from app.abus_hf import AbusHuggingFace

    AbusHuggingFace.initialize(app_name="voice")
    AbusHuggingFace.hf_download_models(file_type="edge-tts", level=0)
    AbusHuggingFace.hf_download_models(file_type="kokoro", level=0)


def main(argv=None):
    args = build_parser().parse_args(argv)
    config_path = os.path.abspath(args.config)

    # Heavy Voice-Pro imports are intentionally lazy so `--help` works even before
    # the full multimedia environment has been installed. `--preflight` only loads
    # the light lip-sync adapter, which lets setup failures point at MuseTalk or
    # Wav2Lip instead of Gradio.
    try:
        user_config = _load_user_config(config_path)
        params = _build_params(args, user_config)
    except ModuleNotFoundError as e:
        _print_missing_dependency(e)
        return 2

    if args.preflight:
        try:
            from app.abus_lipsync import LipSyncRunner
        except ModuleNotFoundError as e:
            _print_missing_dependency(e)
            return 2

        try:
            lipsync = LipSyncRunner(user_config)
            lipsync.preflight(
                params.lip_sync_engine,
                enabled=params.lip_sync_enabled,
                allow_audio_only_fallback=params.lip_sync_allow_fallback,
            )
        except Exception as e:
            print(json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "ok": True,
                    "lip_sync_enabled": params.lip_sync_enabled,
                    "lip_sync_engine": params.lip_sync_engine,
                    "audio_only_fallback_allowed": params.lip_sync_allow_fallback,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    try:
        GradioGulliver = _load_gradio_pipeline()
    except ModuleNotFoundError as e:
        _print_missing_dependency(e)
        return 2

    if params.bootstrap_assets:
        try:
            _bootstrap_voice_metadata()
        except Exception as e:
            print(json.dumps({"ok": False, "error": f"Asset bootstrap failed: {e}"}, indent=2, ensure_ascii=False), file=sys.stderr)
            return 1

    pipeline = GradioGulliver(user_config)

    try:
        result = pipeline.run_youtube_pipeline(params, progress_callback=_make_cli_progress_callback())
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e)}, indent=2, ensure_ascii=False), file=sys.stderr)
        return 1

    print(json.dumps(_result_to_dict(result), indent=2, ensure_ascii=False))
    return 0 if result.ok else 1


if __name__ == "__main__":
    exit_code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)
