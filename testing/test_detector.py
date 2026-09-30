import unittest

import numpy as np

from backend.audio_quality import prepare_voice_audio
from deepfake_detection.windowing import aggregate_window_scores, make_model_windows


class ModelWindowTests(unittest.TestCase):
    def test_short_audio_repeats_to_exact_model_length(self):
        windows = make_model_windows(np.array([0.25, -0.25], dtype=np.float32), target_samples=8)
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0][0], 0)
        np.testing.assert_array_equal(windows[0][1], [0.25, -0.25] * 4)

    def test_long_audio_overlaps_and_covers_tail(self):
        waveform = np.arange(28, dtype=np.float32)
        windows = make_model_windows(waveform, target_samples=10, stride_samples=5)
        self.assertEqual([start for start, _ in windows], [0, 5, 10, 15, 18])
        self.assertTrue(all(len(window) == 10 for _, window in windows))
        self.assertEqual(windows[-1][1][-1], waveform[-1])

    def test_window_cap_samples_across_full_recording(self):
        waveform = np.arange(100, dtype=np.float32)
        windows = make_model_windows(waveform, target_samples=10, stride_samples=5, max_windows=4)
        self.assertEqual(len(windows), 4)
        self.assertEqual(windows[0][0], 0)
        self.assertEqual(windows[-1][0] + len(windows[-1][1]), len(waveform))

    def test_median_resists_single_extreme_window(self):
        self.assertEqual(aggregate_window_scores([0.22, 0.25, 0.27, 0.99]), 0.26)


class AudioQualityTests(unittest.TestCase):
    def test_silence_is_insufficient_not_a_bonafide_score(self):
        _, quality = prepare_voice_audio(np.zeros(16000, dtype=np.float32))
        self.assertTrue(quality["insufficient_audio_quality"])
        self.assertEqual(quality["audio_quality"], "POOR")
        self.assertEqual(quality["speech_duration_s"], 0.0)

    def test_clean_voiced_audio_is_not_mistaken_for_clipping(self):
        time = np.arange(32000, dtype=np.float32) / 16000
        waveform = 0.55 * np.sin(2 * np.pi * 130 * time) + 0.22 * np.sin(2 * np.pi * 260 * time)
        _, quality = prepare_voice_audio(waveform)
        self.assertFalse(quality["insufficient_audio_quality"])
        self.assertEqual(quality["clipped_sample_ratio"], 0.0)

    def test_clipped_audio_is_flagged_as_insufficient(self):
        time = np.arange(32000, dtype=np.float32) / 16000
        waveform = np.clip(4 * np.sin(2 * np.pi * 130 * time), -1, 1)
        _, quality = prepare_voice_audio(waveform)
        self.assertTrue(quality["insufficient_audio_quality"])
        self.assertGreater(quality["clipped_sample_ratio"], 0.1)


if __name__ == "__main__":
    unittest.main()