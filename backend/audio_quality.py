"""Speech activity and input-quality checks for the upload anti-spoof path.

WebRTC VAD is used only to locate speech and assess whether the model has
usable material. It is not a spoof classifier. No denoising or spectral
filtering is applied to the waveform sent to AASIST.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Tuple

import numpy as np
import webrtcvad

SAMPLE_RATE = 16000
FRAME_MS = 30
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
TRIM_CONTEXT_SAMPLES = SAMPLE_RATE * 150 // 1000
MIN_SPEECH_SECONDS = 0.5
MAX_CLIP_RATIO_POOR = 0.10
# A fresh webrtcvad instance reports its first few frames as speech no matter
# what they contain (measured: 4 phantom frames at the start of a clip even
# when the audio there is exact digital silence; shifting the content +10
# frames leaves the phantom at frames 0-3). A voiced frame therefore only
# counts when it belongs to a sustained run, so the phantom can never create
# a fake speech onset, inflate speech duration, or defeat the trim.
MIN_VOICED_RUN_FRAMES = 5


def _debounce_flags(speech_flags: np.ndarray) -> np.ndarray:
    """Keep voiced frames that belong to a run of >= MIN_VOICED_RUN_FRAMES."""
    flags = np.asarray(speech_flags, dtype=bool).reshape(-1)
    if flags.size == 0:
        return flags
    stable = np.zeros_like(flags)
    edges = np.diff(np.concatenate(([False], flags, [False])).astype(np.int8))
    starts = np.flatnonzero(edges == 1)
    ends = np.flatnonzero(edges == -1)
    for start, end in zip(starts, ends):
        if end - start >= MIN_VOICED_RUN_FRAMES:
            stable[start:end] = True
    return stable


def prepare_voice_audio(audio: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Remove outer silence and report measured quality signals.

    ``audio_quality_score`` is a conservative heuristic minimum of duration,
    clipping, and (when measurable) SNR components; it is not model confidence.
    """
    if sample_rate != SAMPLE_RATE:
        raise ValueError(f"quality analysis expects {SAMPLE_RATE} Hz mono audio")
    decoded = np.asarray(audio, dtype=np.float32).reshape(-1)
    decoded = np.nan_to_num(decoded, nan=0.0, posinf=0.0, neginf=0.0)
    if decoded.size == 0:
        raise ValueError("audio is empty")

    duration_seconds = decoded.size / SAMPLE_RATE
    clipped_ratio = float(np.mean(np.abs(decoded) >= 0.999))
    signal_rms = float(np.sqrt(np.mean(decoded.astype(np.float64) ** 2)))
    waveform = decoded - np.mean(decoded, dtype=np.float64).astype(np.float32)
    peak = float(np.max(np.abs(waveform)))
    vad_waveform = waveform
    if peak > 1e-8:
        vad_waveform = waveform / peak

    rms_values = []
    speech_flags = []
    vad = webrtcvad.Vad(1)
    for start in range(0, vad_waveform.size, FRAME_SAMPLES):
        frame = vad_waveform[start:start + FRAME_SAMPLES]
        actual_samples = frame.size
        if actual_samples < FRAME_SAMPLES:
            frame = np.pad(frame, (0, FRAME_SAMPLES - actual_samples))
        rms_values.append(float(np.sqrt(np.mean(frame.astype(np.float64) ** 2))))
        pcm16 = np.clip(np.round(frame * 32767.0), -32768, 32767).astype("<i2")
        speech_flags.append(vad.is_speech(pcm16.tobytes(), SAMPLE_RATE))

    flags = np.asarray(speech_flags, dtype=bool)
    # Drop the VAD startup phantom and sub-150ms flicker before any decision
    # or measurement uses the flags (onset, duration, activity, SNR, trim).
    flags = _debounce_flags(flags)
    frame_rms = np.asarray(rms_values, dtype=np.float64)
    voiced_indices = np.flatnonzero(flags)
    speech_seconds = min(duration_seconds, float(flags.sum() * FRAME_MS / 1000.0))
    speech_activity_ratio = float(flags.mean()) if flags.size else 0.0

    snr_db = None
    if voiced_indices.size and np.any(~flags):
        speech_rms = float(np.median(frame_rms[flags]))
        noise_rms = float(np.median(frame_rms[~flags]))
        if speech_rms > 1e-8 and noise_rms > 1e-8:
            snr_db = round(20.0 * math.log10(speech_rms / noise_rms), 2)

    duration_component = min(100.0, speech_seconds / 2.0 * 100.0)
    clipping_component = max(0.0, 100.0 * (1.0 - clipped_ratio / 0.05))
    components = [duration_component, clipping_component]
    if snr_db is not None:
        components.append(max(0.0, min(100.0, (snr_db + 5.0) / 30.0 * 100.0)))
    quality_score = round(min(components), 1)

    insufficient = (
        speech_seconds < MIN_SPEECH_SECONDS
        or clipped_ratio >= MAX_CLIP_RATIO_POOR
        or signal_rms < 1e-4
    )
    if insufficient:
        quality_label = "POOR"
    elif speech_seconds < 1.5 or clipped_ratio > 0.01 or (snr_db is not None and snr_db < 10.0):
        quality_label = "FAIR"
    else:
        quality_label = "GOOD"

    if voiced_indices.size:
        start_sample = max(0, int(voiced_indices[0]) * FRAME_SAMPLES - TRIM_CONTEXT_SAMPLES)
        end_sample = min(waveform.size, (int(voiced_indices[-1]) + 1) * FRAME_SAMPLES + TRIM_CONTEXT_SAMPLES)
        trimmed = waveform[start_sample:end_sample].astype(np.float32, copy=True)
    else:
        start_sample, end_sample = 0, waveform.size
        trimmed = waveform.astype(np.float32, copy=True)
    trimmed_peak = float(np.max(np.abs(trimmed))) if trimmed.size else 0.0
    if trimmed_peak > 1e-8:
        trimmed = trimmed / trimmed_peak

    report = {
        "sample_rate": SAMPLE_RATE,
        "duration_s": round(duration_seconds, 3),
        "speech_duration_s": round(speech_seconds, 3),
        "speech_activity_ratio": round(speech_activity_ratio, 4),
        "clipped_sample_ratio": round(clipped_ratio, 6),
        "signal_rms": round(signal_rms, 6),
        "estimated_snr_db": snr_db,
        "audio_quality_score": quality_score,
        "audio_quality_score_type": "heuristic minimum of measured quality components; not calibrated",
        "audio_quality": quality_label,
        "insufficient_audio_quality": insufficient,
        "trim_start_s": round(start_sample / SAMPLE_RATE, 3),
        "trim_end_s": round(end_sample / SAMPLE_RATE, 3),
    }
    return trimmed, report