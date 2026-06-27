from dataclasses import dataclass
from typing import Optional


@dataclass
class PipelineEstimate:
    duration_seconds: Optional[float]
    low_minutes: Optional[int]
    high_minutes: Optional[int]
    markdown: str


def estimate_youtube_pipeline(
    duration_seconds: Optional[float] = None,
    *,
    clip_seconds: Optional[float] = None,
    tts_strategy: str = "source_voice",
    lip_sync_enabled: bool = True,
    lip_sync_engine: str = "Wav2Lip",
    video_quality: str = "low",
    asr_model: str = "base",
) -> PipelineEstimate:
    effective_duration = _effective_duration(duration_seconds, clip_seconds)
    duration_minutes = (effective_duration / 60.0) if effective_duration else None
    source_voice = str(tts_strategy or "source_voice").replace("-", "_") == "source_voice"
    wav2lip = lip_sync_enabled and lip_sync_engine == "Wav2Lip"

    if duration_minutes:
        low_multiplier = 2.0
        high_multiplier = 4.0
        if source_voice:
            low_multiplier += 5.0
            high_multiplier += 10.0
        if lip_sync_enabled:
            low_multiplier += 2.0 if wav2lip else 3.0
            high_multiplier += 4.0 if wav2lip else 8.0
        if str(asr_model).lower() in ("large", "large-v2", "large-v3"):
            low_multiplier += 0.5
            high_multiplier += 2.0

        low_minutes = max(1, round(duration_minutes * low_multiplier))
        high_minutes = max(low_minutes, round(duration_minutes * high_multiplier))
    else:
        low_minutes = None
        high_minutes = None

    markdown = _format_estimate_markdown(
        duration_minutes,
        low_minutes,
        high_minutes,
        source_voice=source_voice,
        lip_sync_enabled=lip_sync_enabled,
        lip_sync_engine=lip_sync_engine,
        video_quality=video_quality,
    )
    return PipelineEstimate(effective_duration, low_minutes, high_minutes, markdown)


def _effective_duration(duration_seconds, clip_seconds):
    try:
        duration = float(duration_seconds) if duration_seconds else None
    except (TypeError, ValueError):
        duration = None
    try:
        clip = float(clip_seconds) if clip_seconds else None
    except (TypeError, ValueError):
        clip = None
    if clip and clip > 0:
        return min(duration, clip) if duration else clip
    return duration


def _format_estimate_markdown(
    duration_minutes,
    low_minutes,
    high_minutes,
    *,
    source_voice,
    lip_sync_enabled,
    lip_sync_engine,
    video_quality,
):
    if duration_minutes:
        headline = f"预计处理时长：约 {low_minutes}-{high_minutes} 分钟（视频约 {duration_minutes:.1f} 分钟）。"
    else:
        headline = "预计处理时长：等待获取视频时长；本机实测 5 分钟源音色 + Wav2Lip 约 50-60 分钟。"

    tts_line = "CosyVoice 源音色克隆，本地推理，不消耗 OpenAI token。" if source_voice else "Edge/Azure TTS，主要消耗 TTS 服务请求。"
    lip_line = (
        f"{lip_sync_engine} 唇形同步，本地 CPU/GPU 推理；无人脸帧会保留原画面。"
        if lip_sync_enabled
        else "未启用唇形同步，只生成换轨配音视频。"
    )

    return "\n".join(
        [
            f"### 运行估算\n{headline}",
            "",
            "**主要消耗**",
            f"- 网络/磁盘：下载 YouTube 视频，质量 `{video_quality}` 越高越大。",
            "- ASR：本地 Whisper/faster-whisper 推理；GPU 可明显加速。",
            "- 翻译：当前走 Deep/Azure 翻译请求，按字幕文本字符/请求消耗；不是 LLM token 管线。",
            f"- TTS：{tts_line}",
            f"- 唇形：{lip_line}",
            "- 临时文件：会在 `workspace/` 下保存源视频、音频、人声/伴奏、字幕、配音和最终视频。",
        ]
    )
