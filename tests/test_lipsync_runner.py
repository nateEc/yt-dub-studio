import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.abus_lipsync import LipSyncError, LipSyncRunner


class LipSyncRunnerSmokeTest(unittest.TestCase):
    def setUp(self):
        if shutil.which("ffmpeg") is None:
            self.skipTest("ffmpeg is required for lip-sync smoke tests")
        self.tmpdir = tempfile.TemporaryDirectory()
        self.source_video = os.path.join(self.tmpdir.name, "source.mp4")
        self.dubbed_audio = os.path.join(self.tmpdir.name, "dubbed.wav")

        self._run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=size=128x96:rate=25:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
            "-c:v", "mpeg4", "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-shortest",
            self.source_video,
        ])
        self._run([
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
            "-ac", "2",
            "-ar", "48000",
            self.dubbed_audio,
        ])

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_audio_only_fallback_generates_video(self):
        output_video = os.path.join(self.tmpdir.name, "audio_only.mp4")
        runner = LipSyncRunner()

        result = runner.run(
            self.source_video,
            self.dubbed_audio,
            output_video,
            engine=LipSyncRunner.ENGINE_AUDIO_ONLY,
        )

        self.assertTrue(os.path.exists(output_video))
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.output_path, output_video)

    def test_unconfigured_musetalk_falls_back_when_allowed(self):
        output_video = os.path.join(self.tmpdir.name, "musetalk_fallback.mp4")
        runner = LipSyncRunner()

        with patch.dict(os.environ, {"MUSETALK_DIR": ""}, clear=False):
            result = runner.run(
                self.source_video,
                self.dubbed_audio,
                output_video,
                engine=LipSyncRunner.ENGINE_MUSETALK,
                allow_audio_only_fallback=True,
            )

        self.assertTrue(os.path.exists(output_video))
        self.assertTrue(result.used_fallback)
        self.assertIn("Audio-only fallback", result.message)

    def test_unconfigured_musetalk_fails_when_fallback_disabled(self):
        output_video = os.path.join(self.tmpdir.name, "musetalk_strict.mp4")
        runner = LipSyncRunner()

        with patch.dict(os.environ, {"MUSETALK_DIR": ""}, clear=False):
            with self.assertRaises(LipSyncError):
                runner.run(
                    self.source_video,
                    self.dubbed_audio,
                    output_video,
                    engine=LipSyncRunner.ENGINE_MUSETALK,
                    allow_audio_only_fallback=False,
                )

        self.assertFalse(os.path.exists(output_video))

    def test_preflight_fails_for_unconfigured_strict_musetalk(self):
        runner = LipSyncRunner()

        with patch.dict(os.environ, {"MUSETALK_DIR": ""}, clear=False):
            with self.assertRaises(LipSyncError):
                runner.preflight(
                    LipSyncRunner.ENGINE_MUSETALK,
                    enabled=True,
                    allow_audio_only_fallback=False,
                )

    def test_preflight_skips_when_fallback_is_allowed(self):
        runner = LipSyncRunner()

        with patch.dict(os.environ, {"MUSETALK_DIR": ""}, clear=False):
            runner.preflight(
                LipSyncRunner.ENGINE_MUSETALK,
                enabled=True,
                allow_audio_only_fallback=True,
            )

    def test_wav2lip_preflight_accepts_configured_runtime(self):
        runtime_dir, checkpoint_path = self._create_fake_wav2lip_runtime()
        runner = LipSyncRunner(
            {
                "lipsync_wav2lip_dir": runtime_dir,
                "lipsync_wav2lip_checkpoint": checkpoint_path,
                "lipsync_wav2lip_python": sys.executable,
            }
        )

        runner.preflight(
            LipSyncRunner.ENGINE_WAV2LIP,
            enabled=True,
            allow_audio_only_fallback=False,
        )

    def test_wav2lip_runtime_uses_space_safe_temporary_inputs(self):
        runtime_dir, checkpoint_path = self._create_fake_wav2lip_runtime()
        source_with_spaces = os.path.join(self.tmpdir.name, "source video.mp4")
        audio_with_spaces = os.path.join(self.tmpdir.name, "dubbed audio.wav")
        shutil.copy2(self.source_video, source_with_spaces)
        shutil.copy2(self.dubbed_audio, audio_with_spaces)
        output_video = os.path.join(self.tmpdir.name, "wav2lip.mp4")
        commands = []
        runner = LipSyncRunner(
            {
                "lipsync_wav2lip_dir": runtime_dir,
                "lipsync_wav2lip_checkpoint": checkpoint_path,
                "lipsync_wav2lip_python": sys.executable,
                "lipsync_wav2lip_face_det_stride": 15,
            }
        )

        def fake_run_command(command, cwd, env=None):
            commands.append((command, cwd, env))
            outfile = command[command.index("--outfile") + 1]
            generated_path = Path(cwd) / outfile
            generated_path.parent.mkdir(parents=True, exist_ok=True)
            generated_path.write_bytes(b"fake video")

        with patch.object(runner, "_run_command", side_effect=fake_run_command):
            result = runner.run(
                source_with_spaces,
                audio_with_spaces,
                output_video,
                engine=LipSyncRunner.ENGINE_WAV2LIP,
                allow_audio_only_fallback=False,
            )

        self.assertTrue(os.path.exists(output_video))
        self.assertFalse(result.used_fallback)
        command, cwd, env = commands[0]
        self.assertEqual(cwd, runtime_dir)
        self.assertEqual(env["WAV2LIP_FACE_DET_STRIDE"], "15")
        for flag in ("--face", "--audio", "--outfile"):
            value = command[command.index(flag) + 1]
            self.assertNotIn(" ", value)
            self.assertFalse(os.path.isabs(value))

    def _run(self, command):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            self.fail(f"Command failed: {' '.join(command)}\n{result.stderr}")

    def _create_fake_wav2lip_runtime(self):
        runtime_dir = os.path.join(self.tmpdir.name, "Wav2Lip")
        detector_dir = os.path.join(runtime_dir, "face_detection", "detection", "sfd")
        os.makedirs(detector_dir, exist_ok=True)
        Path(runtime_dir, "inference.py").write_text("# fake wav2lip")
        Path(detector_dir, "s3fd.pth").write_bytes(b"detector")
        checkpoint_path = os.path.join(self.tmpdir.name, "wav2lip_gan.pth")
        Path(checkpoint_path).write_bytes(b"checkpoint")
        return runtime_dir, checkpoint_path


if __name__ == "__main__":
    unittest.main()
