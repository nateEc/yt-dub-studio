import glob
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

from app.abus_ffmpeg import ffmpeg_replace_audio
from app.abus_path import path_lipsync_folder, path_new_filename

try:
    import structlog
    logger = structlog.get_logger()
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class LipSyncError(RuntimeError):
    pass


@dataclass
class LipSyncResult:
    output_path: str
    engine: str
    used_fallback: bool
    message: str


class LipSyncRunner:
    ENGINE_DISABLED = "Disabled"
    ENGINE_MUSETALK = "MuseTalk"
    ENGINE_WAV2LIP = "Wav2Lip"
    ENGINE_AUDIO_ONLY = "Audio-only fallback"
    WAV2LIP_DEFAULT_DIR = Path(__file__).resolve().parents[1] / "workspace" / "runtimes" / "Wav2Lip"
    WAV2LIP_DEFAULT_CHECKPOINTS = (
        Path(__file__).resolve().parents[1] / "model" / "wav2lip" / "checkpoints" / "wav2lip_gan.pth",
        Path(__file__).resolve().parents[1] / "model" / "wav2lip" / "checkpoints" / "wav2lip_folder" / "Wav2Lip-SD-GAN.pt",
        Path(__file__).resolve().parents[1] / "model" / "wav2lip" / "checkpoints" / "Wav2Lip-SD-GAN.pt",
    )

    def __init__(self, user_config=None):
        self.user_config = user_config

    @classmethod
    def available_engines(cls):
        return [
            cls.ENGINE_MUSETALK,
            cls.ENGINE_WAV2LIP,
            cls.ENGINE_AUDIO_ONLY,
            cls.ENGINE_DISABLED,
        ]

    def preflight(self, engine: str, enabled: bool = True, allow_audio_only_fallback: bool = True):
        if not enabled or engine in (self.ENGINE_DISABLED, self.ENGINE_AUDIO_ONLY):
            return
        if allow_audio_only_fallback:
            return
        if engine == self.ENGINE_MUSETALK:
            self._check_musetalk_config()
            return
        if engine == self.ENGINE_WAV2LIP:
            self._check_wav2lip_config()
            return
        raise LipSyncError(f"Unsupported lip-sync engine: {engine}")

    def run(
        self,
        source_video: str,
        audio_path: str,
        output_path: Optional[str] = None,
        engine: str = ENGINE_MUSETALK,
        bbox_shift: int = 0,
        enabled: bool = True,
        allow_audio_only_fallback: bool = True,
    ) -> LipSyncResult:
        if not source_video or not os.path.exists(source_video):
            raise LipSyncError(f"Source video not found: {source_video}")
        if not audio_path or not os.path.exists(audio_path):
            raise LipSyncError(f"Audio file not found: {audio_path}")

        if output_path is None:
            output_path = os.path.join(path_lipsync_folder(), path_new_filename(".mp4"))
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        if not enabled or engine == self.ENGINE_DISABLED:
            return self._audio_only(source_video, audio_path, output_path, self.ENGINE_DISABLED, False)

        try:
            if engine == self.ENGINE_MUSETALK:
                return self._run_musetalk(source_video, audio_path, output_path, bbox_shift)
            if engine == self.ENGINE_WAV2LIP:
                return self._run_wav2lip(source_video, audio_path, output_path)
            if engine == self.ENGINE_AUDIO_ONLY:
                return self._audio_only(source_video, audio_path, output_path, engine, True)
            raise LipSyncError(f"Unsupported lip-sync engine: {engine}")
        except Exception as e:
            if not allow_audio_only_fallback:
                raise
            logger.error(f"[abus_lipsync.py] Lip-sync failed, using audio-only fallback: {e}")
            result = self._audio_only(source_video, audio_path, output_path, engine, True)
            result.message = f"{engine} failed or is not configured. Audio-only fallback was generated. Reason: {e}"
            return result

    def _run_musetalk(self, source_video: str, audio_path: str, output_path: str, bbox_shift: int) -> LipSyncResult:
        musetalk_dir = self._check_musetalk_config()
        python_bin = self._setting("lipsync_musetalk_python", "MUSETALK_PYTHON", "python")
        ffmpeg_path = self._setting("lipsync_musetalk_ffmpeg_path", "MUSETALK_FFMPEG_PATH")
        unet_model_path = self._setting("lipsync_musetalk_unet_model_path", "MUSETALK_UNET_MODEL_PATH")
        unet_config = self._setting("lipsync_musetalk_unet_config", "MUSETALK_UNET_CONFIG")
        version = self._setting("lipsync_musetalk_version", "MUSETALK_VERSION", "v15")

        run_dir = os.path.join(path_lipsync_folder(), path_new_filename("", "%Y%m%d-%H%M%S-musetalk"))
        os.makedirs(run_dir, exist_ok=True)

        config_path = os.path.join(run_dir, "inference.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "task_0": {
                        "video_path": os.path.abspath(source_video),
                        "audio_path": os.path.abspath(audio_path),
                    }
                },
                f,
                sort_keys=False,
                allow_unicode=True,
            )

        command = [
            python_bin,
            "-m",
            "scripts.inference",
            "--inference_config",
            config_path,
            "--result_dir",
            run_dir,
            "--bbox_shift",
            str(int(bbox_shift)),
            "--version",
            version,
        ]
        if ffmpeg_path:
            command.extend(["--ffmpeg_path", ffmpeg_path])
        if unet_model_path:
            command.extend(["--unet_model_path", unet_model_path])
        if unet_config:
            command.extend(["--unet_config", unet_config])

        self._run_command(command, cwd=musetalk_dir)
        generated = self._find_newest_video(run_dir)
        if not generated:
            raise LipSyncError(f"MuseTalk finished but no output video was found in {run_dir}")
        shutil.copy2(generated, output_path)
        return LipSyncResult(output_path, self.ENGINE_MUSETALK, False, f"MuseTalk output: {generated}")

    def _run_wav2lip(self, source_video: str, audio_path: str, output_path: str) -> LipSyncResult:
        wav2lip_dir, checkpoint_path = self._check_wav2lip_config()
        python_bin = self._python_setting("lipsync_wav2lip_python", "WAV2LIP_PYTHON")
        face_det_batch_size = self._int_setting("lipsync_wav2lip_face_det_batch_size", "WAV2LIP_FACE_DET_BATCH_SIZE", 1)
        wav2lip_batch_size = self._int_setting("lipsync_wav2lip_batch_size", "WAV2LIP_BATCH_SIZE", 4)
        resize_factor = self._int_setting("lipsync_wav2lip_resize_factor", "WAV2LIP_RESIZE_FACTOR", 1)
        face_det_stride = self._int_setting("lipsync_wav2lip_face_det_stride", "WAV2LIP_FACE_DET_STRIDE", 15)
        pads = self._int_list_setting("lipsync_wav2lip_pads", "WAV2LIP_PADS")
        box = self._int_list_setting("lipsync_wav2lip_box", "WAV2LIP_BOX")
        nosmooth = self._bool_setting("lipsync_wav2lip_nosmooth", "WAV2LIP_NOSMOOTH", False)

        run_id = f"{path_new_filename('', '%Y%m%d-%H%M%S-wav2lip')}-{os.getpid()}"
        run_dir = os.path.join(wav2lip_dir, "temp", "voice_pro_runs", run_id)
        os.makedirs(run_dir, exist_ok=True)
        face_path = self._copy_runtime_input(source_video, run_dir, "face")
        copied_audio_path = self._copy_runtime_input(audio_path, run_dir, "audio")
        generated_path = os.path.join(run_dir, "result.mp4")

        face_arg = os.path.relpath(face_path, wav2lip_dir)
        audio_arg = os.path.relpath(copied_audio_path, wav2lip_dir)
        outfile_arg = os.path.relpath(generated_path, wav2lip_dir)

        command = [
            python_bin,
            "inference.py",
            "--checkpoint_path",
            checkpoint_path,
            "--face",
            face_arg,
            "--audio",
            audio_arg,
            "--outfile",
            outfile_arg,
            "--face_det_batch_size",
            str(face_det_batch_size),
            "--wav2lip_batch_size",
            str(wav2lip_batch_size),
            "--resize_factor",
            str(resize_factor),
        ]
        if len(pads) == 4:
            command.extend(["--pads", *[str(value) for value in pads]])
        if len(box) == 4:
            command.extend(["--box", *[str(value) for value in box]])
        if nosmooth:
            command.append("--nosmooth")
        env = os.environ.copy()
        env["WAV2LIP_FACE_DET_STRIDE"] = str(max(1, face_det_stride))
        self._run_command(command, cwd=wav2lip_dir, env=env)
        if not os.path.exists(generated_path):
            raise LipSyncError(f"Wav2Lip finished but output was not found: {generated_path}")
        shutil.copy2(generated_path, output_path)
        if not os.path.exists(output_path):
            raise LipSyncError(f"Wav2Lip finished but output was not found: {output_path}")
        return LipSyncResult(output_path, self.ENGINE_WAV2LIP, False, "Wav2Lip output generated.")

    def _copy_runtime_input(self, source_path: str, run_dir: str, stem: str) -> str:
        ext = os.path.splitext(source_path)[1].lower()
        if not ext:
            ext = ".dat"
        target_path = os.path.join(run_dir, f"{stem}{ext}")
        shutil.copy2(source_path, target_path)
        return target_path

    def _audio_only(self, source_video: str, audio_path: str, output_path: str, engine: str, used_fallback: bool) -> LipSyncResult:
        ffmpeg_replace_audio(source_video, audio_path, output_path)
        return LipSyncResult(
            output_path,
            engine,
            used_fallback,
            "Audio-only video generated; visual lip motion was not changed.",
        )

    def _run_command(self, command, cwd, env=None):
        logger.debug(f"[abus_lipsync.py] command = {command}, cwd = {cwd}")
        started_at = time.time()
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        elapsed = time.time() - started_at
        if result.returncode != 0:
            raise LipSyncError(
                f"Command failed after {elapsed:.1f}s with code {result.returncode}: {' '.join(command)}\n"
                f"stdout:\n{result.stdout[-4000:]}\n"
                f"stderr:\n{result.stderr[-4000:]}"
            )
        logger.debug(f"[abus_lipsync.py] command completed in {elapsed:.1f}s")

    def _find_newest_video(self, folder):
        candidates = []
        for ext in ("*.mp4", "*.mov", "*.webm", "*.mkv"):
            candidates.extend(glob.glob(os.path.join(folder, "**", ext), recursive=True))
        candidates = [path for path in candidates if os.path.isfile(path)]
        if not candidates:
            return None
        return max(candidates, key=os.path.getmtime)

    def _check_musetalk_config(self):
        musetalk_dir = self._setting("lipsync_musetalk_dir", "MUSETALK_DIR")
        if not musetalk_dir or not os.path.isdir(musetalk_dir):
            raise LipSyncError("MuseTalk is not configured. Set MUSETALK_DIR or lipsync_musetalk_dir.")
        inference_path = os.path.join(musetalk_dir, "scripts", "inference.py")
        if not os.path.exists(inference_path):
            raise LipSyncError(f"MuseTalk scripts/inference.py was not found under {musetalk_dir}.")
        return musetalk_dir

    def _check_wav2lip_config(self):
        default_dir = str(self.WAV2LIP_DEFAULT_DIR) if self.WAV2LIP_DEFAULT_DIR.is_dir() else ""
        default_checkpoint = self._default_existing_wav2lip_checkpoint()
        wav2lip_dir = self._setting("lipsync_wav2lip_dir", "WAV2LIP_DIR", default_dir)
        checkpoint_path = self._setting("lipsync_wav2lip_checkpoint", "WAV2LIP_CHECKPOINT", default_checkpoint)
        if not wav2lip_dir or not os.path.isdir(wav2lip_dir):
            raise LipSyncError(
                "Wav2Lip is not configured. Run scripts/setup-wav2lip-runtime.py, "
                "or set WAV2LIP_DIR / lipsync_wav2lip_dir."
            )
        inference_path = os.path.join(wav2lip_dir, "inference.py")
        if not os.path.exists(inference_path):
            raise LipSyncError(f"Wav2Lip inference.py was not found under {wav2lip_dir}.")
        detector_path = os.path.join(wav2lip_dir, "face_detection", "detection", "sfd", "s3fd.pth")
        if not os.path.exists(detector_path):
            raise LipSyncError(
                f"Wav2Lip face detector was not found: {detector_path}. "
                "Run scripts/setup-wav2lip-runtime.py."
            )
        if not checkpoint_path or not os.path.exists(checkpoint_path):
            raise LipSyncError(
                "Wav2Lip checkpoint is not configured. Run scripts/setup-wav2lip-runtime.py, "
                "or set WAV2LIP_CHECKPOINT / lipsync_wav2lip_checkpoint."
            )
        return os.path.abspath(wav2lip_dir), os.path.abspath(checkpoint_path)

    def _default_existing_wav2lip_checkpoint(self) -> str:
        for checkpoint_path in self.WAV2LIP_DEFAULT_CHECKPOINTS:
            if checkpoint_path.exists():
                return str(checkpoint_path)
        return ""

    def _setting(self, config_key: str, env_key: str, default: str = "") -> str:
        value = ""
        if self.user_config is not None:
            value = self.user_config.get(config_key, "")
        return os.environ.get(env_key, value or default)

    def _python_setting(self, config_key: str, env_key: str) -> str:
        value = self._setting(config_key, env_key, sys.executable)
        if value == "python":
            return sys.executable
        return value

    def _int_setting(self, config_key: str, env_key: str, default: int) -> int:
        value = self._setting(config_key, env_key, str(default))
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _int_list_setting(self, config_key: str, env_key: str):
        value = self._setting(config_key, env_key, "")
        if not value:
            return []
        if isinstance(value, (list, tuple)):
            items = value
        else:
            items = str(value).replace(",", " ").split()
        try:
            return [int(item) for item in items]
        except (TypeError, ValueError):
            return []

    def _bool_setting(self, config_key: str, env_key: str, default: bool) -> bool:
        value = self._setting(config_key, env_key, str(default))
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "on")
