import unittest

from app.abus_pipeline_estimate import estimate_youtube_pipeline


class PipelineEstimateTest(unittest.TestCase):
    def test_estimate_uses_clip_duration_when_present(self):
        estimate = estimate_youtube_pipeline(
            duration_seconds=600,
            clip_seconds=300,
            tts_strategy="source_voice",
            lip_sync_enabled=True,
            lip_sync_engine="Wav2Lip",
        )

        self.assertEqual(estimate.duration_seconds, 300)
        self.assertGreaterEqual(estimate.high_minutes, estimate.low_minutes)
        self.assertIn("CosyVoice 源音色克隆", estimate.markdown)
        self.assertIn("不是 LLM token 管线", estimate.markdown)

    def test_estimate_handles_unknown_duration(self):
        estimate = estimate_youtube_pipeline(lip_sync_enabled=False)

        self.assertIsNone(estimate.duration_seconds)
        self.assertIsNone(estimate.low_minutes)
        self.assertIn("等待获取视频时长", estimate.markdown)


if __name__ == "__main__":
    unittest.main()
