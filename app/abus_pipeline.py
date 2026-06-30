import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Iterable, List, Optional


PIPELINE_STAGE_DEFINITIONS = [
    ("download", "下载源视频", "Download source media"),
    ("asr", "ASR 转写", "Transcribe source speech"),
    ("translate", "翻译字幕", "Translate subtitles"),
    ("tts", "源音色 TTS", "Synthesize source-voice speech"),
    ("mix", "混音", "Mix dubbed voice with instrumental audio"),
    ("lipsync", "Wav2Lip", "Run lip sync"),
    ("export", "导出", "Export final artifacts"),
]


PIPELINE_STAGE_KEYS = [key for key, _, _ in PIPELINE_STAGE_DEFINITIONS]


def _now_iso():
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def _flatten_artifacts(values):
    flattened = []
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            flattened.extend(_flatten_artifacts(value))
        else:
            text = str(value)
            if text and text not in flattened:
                flattened.append(text)
    return flattened


def _round_seconds(value):
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def count_subtitle_segments(text):
    if not text:
        return 0
    if "-->" in text:
        return len(re.findall(r"-->", text))
    return len([line for line in str(text).splitlines() if line.strip()])


def build_youtube_quality_report(
    *,
    youtube_url,
    ok,
    error,
    stages,
    source_video_duration_seconds=None,
    output_video_duration_seconds=None,
    processing_elapsed_seconds=None,
    subtitle_text="",
    target_audio_duration_seconds=None,
    used_source_voice=False,
    edge_fallback_occurred=False,
    real_wav2lip_executed=False,
    audio_only_fallback_used=False,
    output_files=None,
):
    source_video_duration_seconds = _round_seconds(source_video_duration_seconds)
    output_video_duration_seconds = _round_seconds(output_video_duration_seconds)
    target_audio_duration_seconds = _round_seconds(target_audio_duration_seconds)
    video_duration_seconds = output_video_duration_seconds or source_video_duration_seconds
    delta = None
    if target_audio_duration_seconds is not None and video_duration_seconds is not None:
        delta = _round_seconds(target_audio_duration_seconds - video_duration_seconds)

    return {
        "created_at": _now_iso(),
        "ok": bool(ok),
        "error": error or "",
        "youtube_url": youtube_url,
        "video_duration_seconds": video_duration_seconds,
        "source_video_duration_seconds": source_video_duration_seconds,
        "output_video_duration_seconds": output_video_duration_seconds,
        "processing_elapsed_seconds": _round_seconds(processing_elapsed_seconds),
        "subtitle_segment_count": count_subtitle_segments(subtitle_text),
        "target_audio_duration_seconds": target_audio_duration_seconds,
        "audio_video_duration_delta_seconds": delta,
        "used_source_voice": bool(used_source_voice),
        "edge_fallback_occurred": bool(edge_fallback_occurred),
        "real_wav2lip_executed": bool(real_wav2lip_executed),
        "audio_only_fallback_used": bool(audio_only_fallback_used),
        "output_files": _flatten_artifacts(output_files or []),
        "stages": stages or [],
        "report_json_path": "",
        "report_markdown_path": "",
    }


def format_quality_report_markdown(report):
    lines = [
        "# YouTube Pipeline Quality Summary",
        "",
        f"- 状态：{'成功' if report.get('ok') else '失败'}",
    ]
    if report.get("error"):
        lines.append(f"- 错误：{report['error']}")
    lines.extend(
        [
            f"- 视频时长：{_format_seconds(report.get('video_duration_seconds'))}",
            f"- 源视频时长：{_format_seconds(report.get('source_video_duration_seconds'))}",
            f"- 输出视频时长：{_format_seconds(report.get('output_video_duration_seconds'))}",
            f"- 处理耗时：{_format_seconds(report.get('processing_elapsed_seconds'))}",
            f"- 字幕段数：{report.get('subtitle_segment_count', 0)}",
            f"- 目标音频总时长：{_format_seconds(report.get('target_audio_duration_seconds'))}",
            f"- 音视频时长差：{_format_seconds(report.get('audio_video_duration_delta_seconds'), signed=True)}",
            f"- 使用 source voice：{_format_bool(report.get('used_source_voice'))}",
            f"- 发生 Edge fallback：{_format_bool(report.get('edge_fallback_occurred'))}",
            f"- 真实执行 Wav2Lip：{_format_bool(report.get('real_wav2lip_executed'))}",
            f"- fallback 成换轨视频：{_format_bool(report.get('audio_only_fallback_used'))}",
            "",
            "## 输出文件",
        ]
    )
    output_files = report.get("output_files") or []
    if output_files:
        lines.extend([f"- `{path}`" for path in output_files])
    else:
        lines.append("- 无")

    lines.extend(["", "## 阶段"])
    for stage in report.get("stages") or []:
        line = f"- {stage.get('label', stage.get('key'))}: {stage.get('status')}"
        if stage.get("duration_seconds") is not None:
            line += f" / {_format_seconds(stage.get('duration_seconds'))}"
        if stage.get("error"):
            line += f" / error: {stage['error']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def save_quality_report(report, json_path, markdown_path):
    report = dict(report)
    report["report_json_path"] = json_path
    report["report_markdown_path"] = markdown_path
    report["output_files"] = _flatten_artifacts(report.get("output_files", []) + [markdown_path, json_path])
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    markdown = format_quality_report_markdown(report)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    with open(markdown_path, "w", encoding="utf-8") as f:
        f.write(markdown)
    return report, markdown


def _format_seconds(value, signed=False):
    value = _round_seconds(value)
    if value is None:
        return "未知"
    sign = ""
    if signed and value > 0:
        sign = "+"
    return f"{sign}{value:.2f}s"


def _format_bool(value):
    return "是" if value else "否"


@dataclass
class PipelineStage:
    key: str
    label: str
    description: str = ""
    status: str = "pending"
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: Optional[float] = None
    artifacts: List[str] = field(default_factory=list)
    message: str = ""
    error: str = ""

    def to_dict(self):
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "status": self.status,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": self.duration_seconds,
            "artifacts": list(self.artifacts),
            "message": self.message,
            "error": self.error,
        }


class PipelineProgressTracker:
    def __init__(self, callback: Optional[Callable[[Dict], None]] = None):
        self.callback = callback
        self._stages = {
            key: PipelineStage(key=key, label=label, description=description)
            for key, label, description in PIPELINE_STAGE_DEFINITIONS
        }
        self._active_key = None

    def start(self, key: str, message: str = "", artifacts: Optional[Iterable] = None):
        stage = self._stage(key)
        stage.status = "running"
        stage.started_at = _now_iso()
        stage.ended_at = None
        stage.duration_seconds = None
        stage.error = ""
        stage.message = message
        self._active_key = key
        if artifacts is not None:
            self.add_artifacts(key, artifacts, notify=False)
        self._notify("stage_started", stage)
        return stage

    def complete(self, key: str, message: str = "", artifacts: Optional[Iterable] = None):
        stage = self._finish(key, "completed", message, artifacts)
        self._notify("stage_completed", stage)
        return stage

    def fail(self, key: str, error, artifacts: Optional[Iterable] = None):
        stage = self._finish(key, "failed", "", artifacts)
        stage.error = str(error)
        self._notify("stage_failed", stage)
        return stage

    def skip(self, key: str, message: str = "", artifacts: Optional[Iterable] = None):
        stage = self._finish(key, "skipped", message, artifacts)
        self._notify("stage_skipped", stage)
        return stage

    def fail_active(self, error):
        if self._active_key:
            stage = self._stage(self._active_key)
            if stage.status == "running":
                self.fail(self._active_key, error)

    def add_artifacts(self, key: str, *artifacts, notify: bool = True):
        stage = self._stage(key)
        for artifact in _flatten_artifacts(artifacts):
            if artifact not in stage.artifacts:
                stage.artifacts.append(artifact)
        if notify:
            self._notify("stage_updated", stage)

    def snapshot(self):
        return [self._stages[key].to_dict() for key in PIPELINE_STAGE_KEYS]

    def status_of(self, key: str):
        return self._stage(key).status

    def format_status(self):
        lines = ["Pipeline stages:"]
        for stage in self.snapshot():
            lines.append(self._format_stage_line(stage))
            if stage.get("message"):
                lines.append(f"  Message: {stage['message']}")
            if stage.get("error"):
                lines.append(f"  Error: {stage['error']}")
            for artifact in stage.get("artifacts") or []:
                lines.append(f"  Artifact: {artifact}")
        return "\n".join(lines)

    def _finish(self, key: str, status: str, message: str = "", artifacts: Optional[Iterable] = None):
        stage = self._stage(key)
        if not stage.started_at:
            stage.started_at = _now_iso()
        stage.ended_at = _now_iso()
        stage.status = status
        stage.message = message or stage.message
        if artifacts is not None:
            self.add_artifacts(key, artifacts, notify=False)
        stage.duration_seconds = self._duration_seconds(stage.started_at, stage.ended_at)
        if self._active_key == key:
            self._active_key = None
        return stage

    def _stage(self, key: str):
        if key not in self._stages:
            raise KeyError(f"Unknown pipeline stage: {key}")
        return self._stages[key]

    def _notify(self, event: str, stage: PipelineStage):
        if self.callback:
            self.callback({"event": event, "stage": stage.to_dict(), "stages": self.snapshot()})

    @staticmethod
    def _duration_seconds(started_at, ended_at):
        if not started_at or not ended_at:
            return None
        try:
            started = datetime.fromisoformat(started_at)
            ended = datetime.fromisoformat(ended_at)
            return round((ended - started).total_seconds(), 3)
        except ValueError:
            return None

    @staticmethod
    def _format_stage_line(stage):
        icon = {
            "pending": "-",
            "running": ">",
            "completed": "OK",
            "failed": "ERR",
            "skipped": "SKIP",
        }.get(stage["status"], "-")
        timing = ""
        if stage.get("started_at") or stage.get("ended_at"):
            started = stage.get("started_at") or "?"
            ended = stage.get("ended_at") or "..."
            timing = f" [{started} -> {ended}]"
        duration = ""
        if stage.get("duration_seconds") is not None:
            duration = f" ({stage['duration_seconds']:.1f}s)"
        return f"{icon} {stage['label']} [{stage['status']}]{duration}{timing}"


@dataclass
class YoutubePipelineParams:
    youtube_url: str
    video_quality: str = "good"
    audio_format: str = "mp3"
    asr_engine: str = "faster-whisper"
    asr_model: str = "base"
    media_language: str = "english"
    compute_type: str = "default"
    denoise_level: int = 0
    source_language: str = "English"
    target_language: str = "Chinese (simplified)"
    voice_name: str = "CHINA-Xiaoxiao-Female"
    pitch: int = 0
    speech_rate: int = 0
    volume: int = 0
    tts_strategy: str = "source_voice"
    source_voice_engine: str = "CosyVoice"
    source_voice_mode: str = "Cross-Lingual"
    source_voice_speed: float = 1.0
    allow_edge_tts_fallback: bool = False
    lip_sync_enabled: bool = True
    lip_sync_engine: str = "MuseTalk"
    lip_sync_bbox_shift: int = 0
    lip_sync_allow_fallback: bool = True
    bootstrap_assets: bool = True
    clip_seconds: Optional[float] = None
    clip_start_seconds: float = 0


@dataclass
class YoutubePipelineResult:
    input_video: Optional[str] = None
    input_audio: Optional[str] = None
    transcription_text: str = ""
    output_video: Optional[str] = None
    output_audio: Optional[str] = None
    translation_text: str = ""
    files: List[str] = field(default_factory=list)
    status: str = ""
    stages: List[dict] = field(default_factory=list)
    quality_report: dict = field(default_factory=dict)
    quality_report_markdown: str = ""
    quality_report_json_path: str = ""
    quality_report_markdown_path: str = ""
    ok: bool = True
    error: str = ""

    def as_gradio_outputs(self):
        return (
            self.input_video,
            self.input_audio,
            self.transcription_text,
            self.output_video,
            self.output_audio,
            self.translation_text,
            self.files,
            self.status,
        )

    def to_dict(self):
        return {
            "input_video": self.input_video,
            "input_audio": self.input_audio,
            "transcription_text": self.transcription_text,
            "output_video": self.output_video,
            "output_audio": self.output_audio,
            "translation_text": self.translation_text,
            "files": self.files,
            "status": self.status,
            "stages": self.stages,
            "quality_report": self.quality_report,
            "quality_report_markdown": self.quality_report_markdown,
            "quality_report_json_path": self.quality_report_json_path,
            "quality_report_markdown_path": self.quality_report_markdown_path,
            "ok": self.ok,
            "error": self.error,
        }
