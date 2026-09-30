"""Fixed-context AASIST windows and robust segment-score aggregation."""
from __future__ import annotations

from typing import List, Tuple

import numpy as np


def make_model_windows(
    waveform: np.ndarray,
    target_samples: int = 64600,
    stride_samples: int = 32300,
    max_windows: int = 64,
) -> List[Tuple[int, np.ndarray]]:
    """Return overlapping fixed-length windows spanning the available audio.

    Short clips are repeated to the model context length, matching the official
    AASIST ASVspoof evaluation loader. Long clips use half-window stride and
    include a final tail-aligned window. Very long uploads are sampled evenly
    across their full duration instead of silently scoring only the beginning.
    Each tuple contains the start sample in the prepared waveform and a copy.
    """
    samples = np.asarray(waveform, dtype=np.float32).reshape(-1)
    samples = np.nan_to_num(samples, nan=0.0, posinf=0.0, neginf=0.0)
    if target_samples <= 0 or stride_samples <= 0 or max_windows <= 0:
        raise ValueError("target_samples, stride_samples, and max_windows must be positive")
    if samples.size == 0:
        return []

    if samples.size < target_samples:
        repeats = (target_samples + samples.size - 1) // samples.size
        return [(0, np.tile(samples, repeats)[:target_samples].copy())]

    final_start = samples.size - target_samples
    starts = list(range(0, final_start + 1, stride_samples))
    if starts[-1] != final_start:
        starts.append(final_start)
    if len(starts) > max_windows:
        selected = np.linspace(0, len(starts) - 1, num=max_windows)
        indices = np.unique(np.rint(selected).astype(int))
        starts = [starts[index] for index in indices]
    return [(start, samples[start:start + target_samples].copy()) for start in starts]


def aggregate_window_scores(scores: List[float]) -> float:
    """Median over this recording's segments; robust to one anomalous window."""
    values = np.asarray(scores, dtype=np.float64).reshape(-1)
    values = values[np.isfinite(values)]
    if values.size == 0:
        raise ValueError("at least one finite model score is required")
    return float(np.median(np.clip(values, 0.0, 1.0)))