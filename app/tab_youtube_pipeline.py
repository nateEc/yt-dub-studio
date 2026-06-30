import os
import sys
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

import gradio as gr

from app.abus_ffmpeg import ffmpeg_get_duration
from app.abus_pipeline import PIPELINE_STAGE_KEYS, YoutubePipelineParams
from app.abus_pipeline_estimate import estimate_youtube_pipeline
from app.gradio_gulliver import GradioGulliver
from src.config import UserConfig


def youtube_pipeline_css():
    return """
.youtube-pipeline-shell {
    max-width: 1440px;
    margin: 0 auto;
    padding: 18px 20px 30px;
}
.yp-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    padding: 20px 22px;
    margin-bottom: 16px;
    border: 1px solid rgba(148, 163, 184, 0.24);
    border-left: 4px solid #2dd4bf;
    border-radius: 8px;
    background: #10151b;
}
.yp-title {
    margin: 0;
    color: #f8fafc;
    font-size: 27px;
    line-height: 1.18;
    font-weight: 720;
    letter-spacing: 0;
}
.yp-subtitle {
    margin-top: 8px;
    color: #a9b7c6;
    font-size: 14px;
    line-height: 1.5;
}
.yp-status-strip {
    display: grid;
    grid-template-columns: repeat(4, minmax(94px, 1fr));
    gap: 8px;
    min-width: 440px;
}
.yp-chip {
    padding: 10px 12px;
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 8px;
    background: #151c23;
}
.yp-chip strong {
    display: block;
    color: #e2e8f0;
    font-size: 13px;
    line-height: 1.2;
    font-weight: 680;
}
.yp-chip span {
    display: block;
    margin-top: 5px;
    color: #8ea2b6;
    font-size: 12px;
    line-height: 1.25;
}
.yp-main-grid {
    gap: 16px;
    align-items: stretch;
}
.yp-panel {
    border: 1px solid rgba(148, 163, 184, 0.22) !important;
    border-radius: 8px !important;
    background: #121820 !important;
    box-shadow: none !important;
    overflow: hidden !important;
}
.youtube-pipeline-shell .yp-panel > .styler {
    --block-radius: 8px !important;
    --button-large-radius: 8px !important;
    --button-small-radius: 8px !important;
    --layout-gap: 0px !important;
    --form-gap-width: 0px !important;
    background: transparent !important;
    border-radius: 8px !important;
}
.youtube-pipeline-shell .yp-panel .block {
    background: transparent !important;
    border-color: rgba(148, 163, 184, 0.16) !important;
}
.youtube-pipeline-shell .yp-panel .hide-container {
    border-width: 0 !important;
}
.youtube-pipeline-shell .yp-panel label,
.youtube-pipeline-shell .yp-panel span[data-testid="block-info"] {
    color: #dbe7f3 !important;
}
.youtube-pipeline-shell .yp-panel textarea,
.youtube-pipeline-shell .yp-panel input {
    color: #f8fafc !important;
}
.youtube-pipeline-shell .yp-url {
    margin: 0 14px 10px !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-radius: 8px !important;
    background: #0d1319 !important;
}
.youtube-pipeline-shell .yp-url textarea {
    background: #0d1319 !important;
}
.yp-panel > div,
.yp-panel .block {
    border-radius: 8px !important;
}
.yp-section-label {
    color: #f8fafc;
    font-size: 15px;
    line-height: 1.35;
    font-weight: 700;
    padding: 14px 14px 10px;
}
.yp-flow {
    display: grid;
    grid-template-columns: repeat(5, minmax(0, 1fr));
    gap: 8px;
    padding: 12px 14px 14px;
}
.yp-step {
    min-height: 58px;
    padding: 9px 10px;
    border: 1px solid rgba(45, 212, 191, 0.2);
    border-radius: 8px;
    background: #111f24;
    color: #c9d7e6;
    font-size: 12px;
    line-height: 1.25;
}
.yp-step b {
    display: block;
    color: #5eead4;
    font-size: 12px;
    margin-bottom: 4px;
}
.yp-button-row {
    gap: 10px;
    padding: 0 14px 12px;
}
.yp-button-row button {
    min-height: 42px !important;
    border-radius: 8px !important;
    border: 1px solid rgba(148, 163, 184, 0.22) !important;
    box-shadow: none !important;
    font-weight: 700 !important;
}
.yp-button-row button.secondary {
    background: #1a2430 !important;
    color: #d9e8f6 !important;
}
.yp-button-row button.primary {
    background: #2dd4bf !important;
    color: #042f2e !important;
}
.yp-button-row button:hover {
    filter: brightness(1.06);
}
.yp-estimate {
    color: #c9d7e6;
    padding: 14px !important;
    max-height: 360px;
}
.yp-estimate h3 {
    color: #f8fafc;
    font-size: 16px;
    margin: 0 0 8px;
}
.yp-estimate strong {
    color: #f8fafc;
}
.yp-output-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    padding: 14px 14px 10px;
}
.yp-output-title h3 {
    margin: 0;
    color: #f8fafc;
    font-size: 17px;
    line-height: 1.35;
}
.yp-output-title span {
    color: #93c5fd;
    font-size: 12px;
    line-height: 1.3;
}
.yp-video {
    min-height: 360px;
    margin: 0 14px !important;
    border: 1px solid rgba(148, 163, 184, 0.2) !important;
    border-style: solid !important;
    border-radius: 8px !important;
    background: #0c1117 !important;
}
.youtube-pipeline-shell .yp-panel audio,
.youtube-pipeline-shell .yp-panel video {
    background: #0c1117 !important;
}
.youtube-pipeline-shell .yp-panel .yp-video + .block {
    margin: 10px 14px 14px !important;
    border-radius: 8px !important;
    background: #0d1319 !important;
}
.yp-status textarea {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
    font-size: 13px !important;
    line-height: 1.45 !important;
}
.yp-advanced {
    border-radius: 8px !important;
    border: 1px solid rgba(148, 163, 184, 0.18) !important;
    background: #121820 !important;
}
@media (max-width: 1100px) {
    .yp-header {
        display: block;
    }
    .yp-status-strip {
        grid-template-columns: repeat(2, minmax(0, 1fr));
        min-width: 0;
        margin-top: 14px;
    }
    .yp-flow {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
"""


def youtube_pipeline_tab(user_config: UserConfig):
    gulliver = GradioGulliver(user_config)

    with gr.Column(elem_classes=["youtube-pipeline-shell"]):
        gr.HTML(
            """
<section class="yp-header">
  <div>
    <h1 class="yp-title">YouTube 中文配音工作台</h1>
    <div class="yp-subtitle">输入视频链接，生成保留源音色的中文配音成片。</div>
  </div>
  <div class="yp-status-strip">
    <div class="yp-chip"><strong>源音色</strong><span>CosyVoice</span></div>
    <div class="yp-chip"><strong>字幕</strong><span>ASR + 翻译</span></div>
    <div class="yp-chip"><strong>唇形</strong><span>Wav2Lip</span></div>
    <div class="yp-chip"><strong>成本</strong><span>本地推理为主</span></div>
  </div>
</section>
"""
        )

        with gr.Row(elem_classes=["yp-main-grid"]):
            with gr.Column(scale=4, min_width=360):
                with gr.Group(elem_classes=["yp-panel"]):
                    gr.HTML('<div class="yp-section-label">输入</div>')
                    youtube_url = gr.Textbox(
                        label="YouTube URL",
                        placeholder="https://www.youtube.com/watch?v=...",
                        lines=1,
                        elem_classes=["yp-url"],
                    )
                    with gr.Row(elem_classes=["yp-button-row"]):
                        estimate_button = gr.Button(value="估算耗时/消耗", variant="secondary")
                        run_button = gr.Button(value="开始生成", variant="primary", elem_classes=["yp-run-button"])
                    gr.HTML(
                        """
<div class="yp-flow">
  <div class="yp-step"><b>1</b>下载</div>
  <div class="yp-step"><b>2</b>转写</div>
  <div class="yp-step"><b>3</b>翻译</div>
  <div class="yp-step"><b>4</b>源音色</div>
  <div class="yp-step"><b>5</b>唇形</div>
</div>
"""
                    )

                with gr.Group(elem_classes=["yp-panel"]):
                    estimate_markdown = gr.Markdown(
                        estimate_youtube_pipeline(
                            tts_strategy="source_voice",
                            lip_sync_enabled=True,
                            lip_sync_engine="Wav2Lip",
                            video_quality=user_config.get("video_quality", "low"),
                            asr_model=user_config.get("faster_whisper_model", "base"),
                        ).markdown,
                        elem_classes=["yp-estimate"],
                    )

                with gr.Accordion("高级设置", open=False, elem_classes=["yp-advanced"]):
                    with gr.Row():
                        video_quality = gr.Radio(
                            label="视频质量",
                            choices=["low", "good", "best"],
                            value=user_config.get("youtube_pipeline_video_quality", "low"),
                        )
                        audio_format = gr.Radio(
                            label="音频格式",
                            choices=["mp3", "wav", "flac"],
                            value=user_config.get("youtube_pipeline_audio_format", "mp3"),
                        )
                    with gr.Row():
                        clip_seconds = gr.Number(
                            label="只处理前 N 秒",
                            value=None,
                            precision=0,
                        )
                        clip_start_seconds = gr.Number(
                            label="起始秒数",
                            value=0,
                            precision=0,
                        )
                    with gr.Row():
                        source_language = gr.Dropdown(
                            label="源语言",
                            choices=gulliver.gradio_translate_languages(),
                            value=user_config.get("translate_source_language", "English"),
                        )
                        target_language = gr.Dropdown(
                            label="目标语言",
                            choices=gulliver.gradio_translate_languages(),
                            value=user_config.get("translate_target_language", "Chinese (simplified)"),
                        )
                    with gr.Row():
                        asr_engine = gr.Radio(
                            label="ASR Engine",
                            choices=gulliver.get_asr_engines(),
                            value=user_config.get("asr_engine", "faster-whisper"),
                        )
                        asr_model = gr.Dropdown(
                            label="ASR Model",
                            choices=gulliver.get_whisper_models(),
                            value=user_config.get("faster_whisper_model", "base"),
                        )
                    with gr.Row():
                        media_language = gr.Dropdown(
                            label="媒体语言",
                            choices=gulliver.get_whisper_languages(),
                            value=user_config.get("whisper_language", "english"),
                        )
                        compute_type = gr.Dropdown(
                            label="计算精度",
                            choices=gulliver.get_whisper_compute_types(),
                            value=user_config.get("whisper_compute_type", "default"),
                        )
                    denoise_level = gr.Slider(
                        minimum=0,
                        maximum=2,
                        step=1,
                        value=user_config.get("denoise_level", 0),
                        label="降噪级别",
                    )
                    with gr.Row():
                        source_voice_mode = gr.Radio(
                            label="源音色模式",
                            choices=["Cross-Lingual", "Zero-Shot", "Instruct"],
                            value=user_config.get("youtube_pipeline_source_voice_mode", "Cross-Lingual"),
                        )
                        source_voice_speed = gr.Slider(
                            0.3,
                            2.0,
                            value=user_config.get("youtube_pipeline_source_voice_speed", 1.0),
                            step=0.1,
                            label="语速",
                        )
                    with gr.Row():
                        lip_sync_enabled = gr.Checkbox(
                            label="启用唇形同步",
                            value=user_config.get("youtube_pipeline_lipsync_enabled", True),
                        )
                        lip_sync_engine = gr.Dropdown(
                            label="唇形引擎",
                            choices=gulliver.get_lipsync_engines(),
                            value=user_config.get("youtube_pipeline_lipsync_engine", "Wav2Lip"),
                        )
                    with gr.Row():
                        lip_sync_allow_fallback = gr.Checkbox(
                            label="唇形失败时输出换轨视频",
                            value=user_config.get("youtube_pipeline_lipsync_allow_fallback", False),
                        )
                        bootstrap_assets = gr.Checkbox(
                            label="自动准备资源",
                            value=user_config.get("youtube_pipeline_bootstrap_assets", True),
                        )

            with gr.Column(scale=8, min_width=520):
                with gr.Group(elem_classes=["yp-panel"]):
                    gr.HTML(
                        """
<div class="yp-output-title">
  <h3>最终视频</h3>
  <span>完成后会显示在这里</span>
</div>
"""
                    )
                    output_video = gr.Video(label="成片预览", interactive=False, elem_classes=["yp-video"])
                    output_audio = gr.Audio(label="中文配音音频", type="filepath", interactive=False)

                with gr.Tabs():
                    with gr.Tab("运行状态"):
                        status = gr.Textbox(label="运行日志", lines=9, max_lines=18, interactive=False, elem_classes=["yp-status"])
                    with gr.Tab("质量报告"):
                        quality_report = gr.Markdown("运行完成后会显示质量报告。")
                    with gr.Tab("源视频"):
                        input_video = gr.Video(label="源视频", interactive=False)
                        input_audio = gr.Audio(label="源音频", type="filepath", interactive=False)
                    with gr.Tab("字幕与文件"):
                        transcription = gr.Textbox(label="原文字幕", lines=8, max_lines=18, show_copy_button=True)
                        translation = gr.Textbox(label="中文字幕", lines=8, max_lines=18, show_copy_button=True)
                        files = gr.File(label="生成文件", type="filepath", file_count="multiple", interactive=False)

    asr_engine.change(gulliver.update_whisper_models, inputs=[asr_engine], outputs=[asr_model])

    estimate_button.click(
        _gradio_estimate,
        inputs=[clip_seconds, video_quality, asr_model, lip_sync_enabled, lip_sync_engine],
        outputs=[estimate_markdown],
    )
    run_button.click(
        _gradio_run_pipeline,
        inputs=[
            youtube_url,
            video_quality,
            audio_format,
            clip_seconds,
            clip_start_seconds,
            source_language,
            target_language,
            asr_engine,
            asr_model,
            media_language,
            compute_type,
            denoise_level,
            source_voice_mode,
            source_voice_speed,
            lip_sync_enabled,
            lip_sync_engine,
            lip_sync_allow_fallback,
            bootstrap_assets,
        ],
        outputs=[
            input_video,
            input_audio,
            transcription,
            output_video,
            output_audio,
            translation,
            files,
            status,
            quality_report,
            estimate_markdown,
        ],
    )


def _gradio_estimate(clip_seconds, video_quality, asr_model, lip_sync_enabled, lip_sync_engine):
    estimate = estimate_youtube_pipeline(
        clip_seconds=clip_seconds,
        tts_strategy="source_voice",
        lip_sync_enabled=lip_sync_enabled,
        lip_sync_engine=lip_sync_engine,
        video_quality=video_quality,
        asr_model=asr_model,
    )
    return estimate.markdown


def _gradio_run_pipeline(
    youtube_url,
    video_quality,
    audio_format,
    clip_seconds,
    clip_start_seconds,
    source_language,
    target_language,
    asr_engine,
    asr_model,
    media_language,
    compute_type,
    denoise_level,
    source_voice_mode,
    source_voice_speed,
    lip_sync_enabled,
    lip_sync_engine,
    lip_sync_allow_fallback,
    bootstrap_assets,
    progress=gr.Progress(track_tqdm=False),
):
    started_at = time.monotonic()
    gulliver = GradioGulliver(UserConfig(os.path.join(parent_dir, "app", "config-user.json5")))
    params = YoutubePipelineParams(
        youtube_url=youtube_url,
        video_quality=video_quality,
        audio_format=audio_format,
        asr_engine=asr_engine,
        asr_model=asr_model,
        media_language=media_language,
        compute_type=compute_type,
        denoise_level=int(denoise_level or 0),
        source_language=source_language,
        target_language=target_language,
        tts_strategy="source_voice",
        source_voice_engine="CosyVoice",
        source_voice_mode=source_voice_mode,
        source_voice_speed=float(source_voice_speed or 1.0),
        allow_edge_tts_fallback=False,
        lip_sync_enabled=bool(lip_sync_enabled),
        lip_sync_engine=lip_sync_engine,
        lip_sync_bbox_shift=0,
        lip_sync_allow_fallback=bool(lip_sync_allow_fallback),
        bootstrap_assets=bool(bootstrap_assets),
        clip_seconds=float(clip_seconds) if clip_seconds else None,
        clip_start_seconds=float(clip_start_seconds or 0),
    )
    result = gulliver.run_youtube_pipeline(params, progress_callback=_gradio_progress_callback(progress))
    elapsed = time.monotonic() - started_at
    output_video_path = result.output_video[0] if isinstance(result.output_video, tuple) else result.output_video
    duration_seconds = ffmpeg_get_duration(output_video_path) if output_video_path else params.clip_seconds
    estimate = estimate_youtube_pipeline(
        duration_seconds=duration_seconds,
        tts_strategy=params.tts_strategy,
        lip_sync_enabled=params.lip_sync_enabled,
        lip_sync_engine=params.lip_sync_engine,
        video_quality=params.video_quality,
        asr_model=params.asr_model,
    )
    status = result.status
    status += f"\n\n实际耗时：{_format_elapsed(elapsed)}"
    status += "\n消耗说明：当前链路不使用 OpenAI token；翻译按字幕字符/请求消耗，TTS/唇形主要消耗本机 CPU/GPU。"
    input_video, input_audio, transcription, output_video, output_audio, translation, files, _ = result.as_gradio_outputs()
    return (
        input_video,
        input_audio,
        transcription,
        output_video,
        output_audio,
        translation,
        files,
        status,
        result.quality_report_markdown,
        estimate.markdown,
    )


def _gradio_progress_callback(progress):
    def _callback(event):
        stage = event.get("stage", {})
        key = stage.get("key")
        status = stage.get("status", "")
        label = stage.get("label", key or "Pipeline")
        try:
            index = PIPELINE_STAGE_KEYS.index(key)
            if status == "running":
                value = index / len(PIPELINE_STAGE_KEYS)
            else:
                value = (index + 1) / len(PIPELINE_STAGE_KEYS)
        except ValueError:
            value = None
        if value is None:
            progress(0, desc=f"{label}: {status}")
        else:
            progress(value, desc=f"{label}: {status}")

    return _callback


def _format_elapsed(seconds):
    seconds = int(seconds)
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}小时{minutes}分{sec}秒"
    return f"{minutes}分{sec}秒"
