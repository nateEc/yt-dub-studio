import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.abus_pipeline import (
    PipelineProgressTracker,
    YoutubePipelineResult,
    build_youtube_quality_report,
    save_quality_report,
)


class PipelineProgressTrackerTest(unittest.TestCase):
    def test_records_timing_artifacts_and_status_text(self):
        events = []
        tracker = PipelineProgressTracker(events.append)

        tracker.start("download", "Fetching source media.")
        tracker.complete("download", "Download ready.", ["source.mp4", ["source.wav", "source.mp4"]])

        stage = tracker.snapshot()[0]
        self.assertEqual(stage["key"], "download")
        self.assertEqual(stage["status"], "completed")
        self.assertEqual(stage["artifacts"], ["source.mp4", "source.wav"])
        self.assertIsNotNone(stage["started_at"])
        self.assertIsNotNone(stage["ended_at"])
        self.assertIsNotNone(stage["duration_seconds"])
        self.assertEqual([event["event"] for event in events], ["stage_started", "stage_completed"])
        self.assertIn("Pipeline stages:", tracker.format_status())
        self.assertIn("Artifact: source.mp4", tracker.format_status())

    def test_fail_active_marks_running_stage_with_error(self):
        tracker = PipelineProgressTracker()

        tracker.start("asr", "Transcribing.")
        tracker.fail_active("ASR model failed")

        asr_stage = tracker.snapshot()[1]
        self.assertEqual(asr_stage["status"], "failed")
        self.assertEqual(asr_stage["error"], "ASR model failed")
        self.assertIn("Error: ASR model failed", tracker.format_status())

    def test_pipeline_result_to_dict_is_json_serializable(self):
        tracker = PipelineProgressTracker()
        tracker.skip("lipsync", "Lip sync disabled.")
        result = YoutubePipelineResult(
            status=tracker.format_status(),
            stages=tracker.snapshot(),
            quality_report={"subtitle_segment_count": 2},
            quality_report_markdown="# Report\n",
            quality_report_json_path="/tmp/report.json",
            quality_report_markdown_path="/tmp/report.md",
        )

        payload = result.to_dict()
        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertIn("stages", payload)
        self.assertIn("quality_report", payload)
        self.assertIn("Lip sync disabled", encoded)
        self.assertIn("report.json", encoded)

    def test_quality_report_builds_and_saves_markdown_and_json(self):
        tracker = PipelineProgressTracker()
        tracker.start("download", "Downloading.")
        tracker.complete("download", "Ready.", ["source.mp4"])
        report = build_youtube_quality_report(
            youtube_url="https://youtu.be/demo",
            ok=True,
            error="",
            stages=tracker.snapshot(),
            source_video_duration_seconds=100.0,
            output_video_duration_seconds=98.0,
            processing_elapsed_seconds=123.4567,
            subtitle_text="1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n",
            target_audio_duration_seconds=101.0,
            used_source_voice=True,
            edge_fallback_occurred=False,
            real_wav2lip_executed=True,
            audio_only_fallback_used=False,
            output_files=["final.mp4"],
        )

        self.assertEqual(report["subtitle_segment_count"], 2)
        self.assertEqual(report["video_duration_seconds"], 98.0)
        self.assertEqual(report["audio_video_duration_delta_seconds"], 3.0)
        self.assertTrue(report["used_source_voice"])
        self.assertTrue(report["real_wav2lip_executed"])

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = str(Path(tmpdir) / "quality.json")
            markdown_path = str(Path(tmpdir) / "quality.md")
            saved_report, markdown = save_quality_report(report, json_path, markdown_path)

            self.assertTrue(Path(json_path).exists())
            self.assertTrue(Path(markdown_path).exists())
            self.assertIn("字幕段数：2", markdown)
            self.assertIn("真实执行 Wav2Lip：是", markdown)
            self.assertIn(markdown_path, saved_report["output_files"])
            loaded = json.loads(Path(json_path).read_text(encoding="utf-8"))
            self.assertEqual(loaded["report_json_path"], json_path)
            self.assertEqual(loaded["target_audio_duration_seconds"], 101.0)


class PipelineCliObservabilityTest(unittest.TestCase):
    def test_cli_emits_progress_events_and_final_stages(self):
        cli = _load_cli_module()

        class FakePipeline:
            def __init__(self, user_config):
                self.user_config = user_config

            def run_youtube_pipeline(self, params, progress_callback=None):
                tracker = PipelineProgressTracker(progress_callback)
                tracker.start("download", "Fake download.")
                tracker.complete("download", "Fake download ready.", ["fake-source.mp4"])
                return YoutubePipelineResult(
                    output_video="fake-output.mp4",
                    status=tracker.format_status(),
                    stages=tracker.snapshot(),
                    quality_report={"ok": True, "subtitle_segment_count": 1},
                    quality_report_markdown="# Quality\n",
                    quality_report_json_path="/tmp/fake-quality.json",
                    quality_report_markdown_path="/tmp/fake-quality.md",
                )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch.object(cli, "_load_user_config", return_value={}), patch.object(
            cli, "_load_gradio_pipeline", return_value=FakePipeline
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = cli.main(["https://youtu.be/fake", "--skip-asset-downloads", "--disable-lip-sync"])

        self.assertEqual(exit_code, 0)
        progress_events = [json.loads(line) for line in stderr.getvalue().splitlines()]
        self.assertEqual(progress_events[0]["event"], "stage_started")
        self.assertEqual(progress_events[0]["stage"]["key"], "download")
        self.assertEqual(progress_events[1]["event"], "stage_completed")

        result = json.loads(stdout.getvalue())
        self.assertTrue(result["ok"])
        self.assertEqual(result["output_video"], "fake-output.mp4")
        self.assertEqual(result["stages"][0]["status"], "completed")
        self.assertEqual(result["quality_report"]["subtitle_segment_count"], 1)
        self.assertEqual(result["quality_report_json_path"], "/tmp/fake-quality.json")


def _load_cli_module():
    path = Path(__file__).resolve().parents[1] / "run-youtube-pipeline.py"
    spec = importlib.util.spec_from_file_location("run_youtube_pipeline_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    unittest.main()
