from dataclasses import dataclass, field
from typing import List, Optional


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
