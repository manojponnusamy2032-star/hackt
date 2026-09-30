"""Upload-path audio handling: decoding, DC handling and input-quality gating.

These are structural checks on the signal path. They assert *behaviour* (no
clipping, no crash, correct scale, DC actually removed) and never assert that
the detector is accurate, because no labeled dataset is configured in this
repository - see ``testing/detector_audit.md``.

    PYTHONPATH=. .venv/bin/python -m unittest testing.test_audio -v
"""
import io
import unittest

import numpy as np
import soundfile as sf

from backend.main import SAMPLE_RATE, load_audio_bytes
from backend.audio_quality import (MAX_CLIP_RATIO_POOR, MIN_SPEECH_SECONDS,
                                   prepare_voice_audio)


def tone(freq: float, seconds: float, amplitude: float = 0.5) -> np.ndarray:
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def speech_like(seconds: float = 2.0, seed: int = 11) -> np.ndarray:
    """Harmonic stack with a jittering f0 - a structural speech stand-in only."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    f0 = 125.0 + 3.0 * np.sin(2 * np.pi * 2.7 * t)
    phase = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
    sig = 0.5 * np.sin(phase) + 0.25 * np.sin(2 * phase) + 0.12 * np.sin(3 * phase)
    sig += 0.005 * rng.standard_normal(t.size)
    return np.clip(sig / np.max(np.abs(sig)), -1.0, 1.0).astype(np.float32)


def wav_bytes(signal: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, signal, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


class DecodeTests(unittest.TestCase):
    def test_round_trip_through_wav_preserves_duration(self):
        decoded = load_audio_bytes(wav_bytes(speech_like(2.0)), "sample.wav")
        self.assertAlmostEqual(decoded.size / SAMPLE_RATE, 2.0, delta=0.01)
        self.assertEqual(decoded.dtype, np.float32)

    def test_dc_offset_is_removed_before_scoring(self):
        """A DC-shifted recording must not be scored as a loud signal.

        The previous peak-normalisation path amplified a pure DC offset into a
        full-scale constant, which the feature extractor would then treat as
        energy. Mean removal keeps the AC content and drops the offset.
        """
        shifted = speech_like(2.0) + 0.6
        decoded = load_audio_bytes(wav_bytes(np.clip(shifted, -1.0, 1.0)), "dc.wav")
        self.assertLess(abs(float(np.mean(decoded))), 0.05)

    def test_peak_is_not_silently_rescaled(self):
        """Amplitude is preserved; only the DC offset is corrected.

        AASIST saw peak-normalised input before, so a quiet-but-clean recording
        and a loud one produced different scores for reasons unrelated to
        authenticity. Normalising here hid that difference.
        """
        quiet = load_audio_bytes(wav_bytes(tone(220.0, 1.0, amplitude=0.05)), "q.wav")
        self.assertLessEqual(float(np.max(np.abs(quiet))), 0.2)

    def test_output_is_bounded_and_finite(self):
        decoded = load_audio_bytes(wav_bytes(np.full(16000, 4.0, dtype=np.float32)), "loud.wav")
        self.assertTrue(np.all(np.isfinite(decoded)))
        self.assertLessEqual(float(np.max(np.abs(decoded))), 1.0)


class QualityGateTests(unittest.TestCase):
    def test_digital_silence_is_rejected_not_scored(self):
        _, quality = prepare_voice_audio(np.zeros(SAMPLE_RATE * 2, dtype=np.float32))
        self.assertTrue(quality["insufficient_audio_quality"])
        self.assertEqual(quality["audio_quality"], "POOR")
        self.assertLess(quality["speech_duration_s"], MIN_SPEECH_SECONDS)

    def test_speech_longer_than_the_minimum_is_accepted(self):
        _, quality = prepare_voice_audio(speech_like(2.0))
        self.assertFalse(quality["insufficient_audio_quality"])
        self.assertGreaterEqual(quality["speech_duration_s"], MIN_SPEECH_SECONDS)

    def test_heavy_clipping_is_rejected(self):
        _, quality = prepare_voice_audio(np.clip(3.0 * tone(140.0, 2.0), -1.0, 1.0))
        self.assertTrue(quality["insufficient_audio_quality"])
        self.assertGreaterEqual(quality["clipped_sample_ratio"], MAX_CLIP_RATIO_POOR)

    def test_quality_score_is_bounded_and_labelled_heuristic(self):
        _, quality = prepare_voice_audio(speech_like(2.0))
        self.assertGreaterEqual(quality["audio_quality_score"], 0.0)
        self.assertLessEqual(quality["audio_quality_score"], 100.0)
        self.assertIn("heuristic", quality["audio_quality_score_type"])
        self.assertIn(quality["audio_quality"], {"POOR", "FAIR", "GOOD"})

    def test_silent_padding_is_trimmed_off_the_model_input(self):
        voiced = speech_like(2.0)
        padded = np.concatenate([np.zeros(SAMPLE_RATE, dtype=np.float32), voiced])
        trimmed, quality = prepare_voice_audio(padded)
        self.assertGreater(quality["trim_start_s"], 0.0)
        self.assertLess(trimmed.size, padded.size)
        # The delivered signal must still contain the speech, not just silence.
        self.assertGreater(float(np.max(np.abs(trimmed))), 0.1)

    def test_empty_audio_is_rejected_with_a_clear_error(self):
        with self.assertRaises(ValueError):
            prepare_voice_audio(np.zeros(0, dtype=np.float32))

    def test_non_16k_input_is_rejected_rather_than_silently_resampled(self):
        with self.assertRaises(ValueError):
            prepare_voice_audio(np.zeros(4800, dtype=np.float32), sample_rate=8000)


if __name__ == "__main__":
    unittest.main()
