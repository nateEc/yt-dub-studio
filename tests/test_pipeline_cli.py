import os
import subprocess
import sys
import tempfile
import unittest


class PipelineCliSmokeTest(unittest.TestCase):
    def test_help_does_not_require_multimedia_dependencies(self):
        result = subprocess.run(
            [sys.executable, "run-youtube-pipeline.py", "--help"],
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Run the full YouTube dubbing pipeline", result.stdout)
        self.assertIn("--target-language", result.stdout)
        self.assertIn("--lip-sync-engine", result.stdout)
        self.assertIn("--preflight", result.stdout)

    def test_preflight_does_not_require_gradio(self):
        env = os.environ.copy()
        env["MUSETALK_DIR"] = ""

        with tempfile.NamedTemporaryFile("w", suffix=".json5", delete=False) as config:
            config.write("{lipsync_enabled: true, lipsync_engine: 'MuseTalk'}")
            config_path = config.name

        try:
            result = subprocess.run(
                [
                    sys.executable,
                    "run-youtube-pipeline.py",
                    "https://youtu.be/invalid",
                    "--config",
                    config_path,
                    "--preflight",
                    "--enable-lip-sync",
                    "--no-audio-only-fallback",
                ],
                capture_output=True,
                text=True,
                env=env,
            )
        finally:
            os.unlink(config_path)

        self.assertEqual(result.returncode, 1)
        self.assertIn("MuseTalk is not configured", result.stderr)
        self.assertNotIn("gradio", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
