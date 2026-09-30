"""Sliding-window PCM buffer + pure NumPy/SciPy acoustic features (SIH26104).

Real-time contract
------------------
* **Everything stays in RAM** - zero disk I/O on the streaming path.
* 200 ms analysis window @16 kHz with **50 % overlap** (100 ms hop) so coverage
  is continuous and gapless no matter how the browser batches its frames.
* **One FFT per scored frame**: the Hann magnitude spectrum is computed once and
  reused for both the high-frequency power ratio and the spectral flux.
* No module-level mutable state: every helper is pure, so concurrent REST
  callers and WebSocket sessions can never contaminate each other.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.fft import irfft, rfft, rfftfreq

SAMPLE_RATE = 16000
WINDOW_MS = 200
WINDOW_SAMPLES = SAMPLE_RATE * WINDOW_MS // 1000          # 3200 samples
OVERLAP = 0.5                                             # 50 % overlap
HOP_SAMPLES = int(WINDOW_SAMPLES * (1.0 - OVERLAP))       # 1600 samples (100 ms)
HF_CUTOFF_HZ = 4000.0                                     # vocoder leakage band
PITCH_MIN_HZ = 50.0
PITCH_MAX_HZ = 400.0
VOICING_CORR_MIN = 0.3                                    # autocorr peak -> voiced
VOICING_LOWPASS_HZ = 1000.0                               # band-limit before pitch
_MIN_SAMPLES = 512                                        # below this: unreliable
_EPS = 1e-12

#: Feature keys every extractor returns - single source of truth for the API.
FEATURE_KEYS: Tuple[str, ...] = (
    "hf_power_ratio",
    "pitch_f0_variance",
    "voiced_ratio",
    "spectral_flux",
    "rms_energy",
)

_EMPTY_FEATURES: Dict[str, float] = {key: 0.0 for key in FEATURE_KEYS}


def _sanitize(pcm: np.ndarray, dtype: type = np.float64) -> np.ndarray:
    """Coerce any PCM-ish input into a finite, mono, peak-limited 1-D array."""
    if pcm is None:
        return np.zeros(0, dtype=dtype)
    arr = np.asarray(pcm)
    if arr.size == 0:
        return np.zeros(0, dtype=dtype)
    arr = arr.astype(np.float64, copy=False).ravel()
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(arr, -1.0, 1.0).astype(dtype, copy=False)


def hf_cutoff_hz(sample_rate: int = SAMPLE_RATE) -> float:
    """High-frequency band start, kept below Nyquist for non-16 kHz streams."""
    nyquist = sample_rate / 2.0
    if nyquist >= HF_CUTOFF_HZ * 1.2:
        return HF_CUTOFF_HZ
    return max(300.0, 0.45 * nyquist)


class AudioBufferManager:
    """Fixed-size circular RAM window with hop-aligned, 50 %-overlapped emission.

    The ring keeps ``capacity + hop`` samples (19 KB of float32 at 16 kHz), which
    is exactly the history needed to emit a window ending on any hop boundary.
    ``push()`` slices an incoming chunk into hop-sized slabs, so a client that
    uploads 20 ms frames, 100 ms frames or one 500 ms burst all end up with the
    *same* deterministic window grid - gapless, never double-counted.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE, window_ms: int = WINDOW_MS,
                 overlap: float = OVERLAP) -> None:
        self.sample_rate = int(sample_rate) if sample_rate else SAMPLE_RATE
        self.window_ms = int(window_ms)
        self.capacity = max(1, self.sample_rate * self.window_ms // 1000)
        self.overlap = float(min(max(overlap, 0.0), 0.9))
        self.hop = max(1, int(round(self.capacity * (1.0 - self.overlap))))
        self._ring_len = self.capacity + self.hop
        self._ring = np.zeros(self._ring_len, dtype=np.float32)
        self._written = 0            # valid samples currently held in the ring
        self.total_ingested = 0      # samples ever accepted
        self.windows_emitted = 0
        self._next_emit = self.capacity   # first window ends exactly at 200 ms

    # ------------------------------------------------------------- ingestion
    def _append(self, piece: np.ndarray) -> None:
        """Shift-register append: the newest sample always lives at ``_ring[-1]``."""
        n = int(piece.size)
        if n <= 0:
            return
        if n >= self._ring_len:
            self._ring[:] = piece[-self._ring_len:]
            self._written = self._ring_len
        else:
            self._ring[:-n] = self._ring[n:]
            self._ring[-n:] = piece
            self._written = min(self._ring_len, self._written + n)
        self.total_ingested += n

    def _window_ending_at(self, end_index: int) -> Optional[np.ndarray]:
        """Samples ``[end_index - capacity, end_index)``; None if already evicted."""
        back = self.total_ingested - int(end_index)
        if back < 0 or back + self.capacity > self._written:
            return None
        stop = self._ring_len - back
        return self._ring[stop - self.capacity:stop].astype(np.float64, copy=True)

    def push(self, pcm_chunk: np.ndarray) -> List[np.ndarray]:
        """Ingest PCM and return every *new* 200 ms window that is now complete.

        Emission is quantised to the hop grid, so consecutive windows overlap by
        exactly 50 % and no sample is ever skipped. Returns ``[]`` until the
        first full window has arrived, so a cold stream never scores silence.
        """
        arr = _sanitize(pcm_chunk, dtype=np.float32)
        if arr.size == 0:
            return []
        windows: List[np.ndarray] = []
        for start in range(0, arr.size, self.hop):
            self._append(arr[start:start + self.hop])
            while self._next_emit <= self.total_ingested:
                back = self.total_ingested - self._next_emit
                if back + self.capacity > self._written:
                    # The grid point is older than the retained history (the ring
                    # only keeps one window behind it): advance without emitting.
                    # hop-sized slabs append at most one window per iteration, so
                    # this resyncs instantly instead of skipping a whole chunk.
                    self._next_emit += self.hop
                    continue
                window = self._window_ending_at(self._next_emit)
                if window is None:      # producer somehow outran the ring: resync
                    self._next_emit = self.total_ingested + self.hop
                    break
                windows.append(window)
                self._next_emit += self.hop
                self.windows_emitted += 1
        return windows

    def add_chunk(self, pcm_chunk: np.ndarray) -> np.ndarray:
        """Compatibility helper: append and return the latest padded window."""
        self._append(_sanitize(pcm_chunk, dtype=np.float32))
        return self.get_window()

    # -------------------------------------------------------------- read side
    def get_window(self) -> np.ndarray:
        """Latest ``capacity`` samples; zero-padded on the left while cold."""
        if self._written == 0:
            return np.zeros(self.capacity, dtype=np.float64)
        return self._ring[self._ring_len - self.capacity:].astype(np.float64)

    def fill_ratio(self) -> float:
        return min(1.0, self._written / float(self.capacity))

    def is_ready(self) -> bool:
        return self._written >= _MIN_SAMPLES

    def reset(self) -> None:
        self._ring[:] = 0.0
        self._written = 0
        self.total_ingested = 0
        self.windows_emitted = 0
        self._next_emit = self.capacity

    def stats(self) -> Dict[str, float]:
        return {
            "sample_rate": self.sample_rate,
            "window_ms": self.window_ms,
            "window_samples": self.capacity,
            "hop_samples": self.hop,
            "overlap": round(self.overlap, 3),
            "window_fill": round(self.fill_ratio(), 4),
            "buffered_samples": self._written,
            "total_ingested": self.total_ingested,
            "windows_emitted": self.windows_emitted,
            "ring_bytes": int(self._ring.nbytes),
        }

    def __len__(self) -> int:
        return min(self._written, self.capacity)



# --------------------------------------------------------------------- helpers
def _lowpass(signal: np.ndarray, cutoff: float = VOICING_LOWPASS_HZ,
             sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Brickwall-ish low-pass (raised-cosine rolloff) via rFFT.

    Pitch detection must run on a band-limited signal: without it a high
    frequency tone or codec hiss creates spurious autocorrelation peaks and
    masks the real glottal structure.
    """
    n = int(signal.size)
    if n < 32:
        return signal
    hi = float(cutoff) * 1.5
    if hi >= sample_rate / 2.0:
        return signal                       # cutoff above Nyquist: nothing to do
    spec = rfft(signal)
    freqs = rfftfreq(n, 1.0 / sample_rate)
    gain = np.ones_like(freqs)
    ramp = (freqs >= cutoff) & (freqs <= hi)
    gain[ramp] = 0.5 * (1.0 + np.cos(np.pi * (freqs[ramp] - cutoff) / max(hi - cutoff, _EPS)))
    gain[freqs > hi] = 0.0
    return irfft(spec * gain, n=n)


def _autocorrelation(frame: np.ndarray) -> np.ndarray:
    """Linear autocorrelation via FFT (O(n log n) instead of O(n^2) correlate)."""
    n = int(frame.size)
    nfft = 1 << max(5, int(math.ceil(math.log2(2 * n))))
    spec = rfft(frame, nfft)
    return irfft(np.abs(spec) ** 2, nfft)[:n]


def _pitch_stats(window: np.ndarray, sample_rate: int = SAMPLE_RATE) -> Tuple[float, float]:
    """Autocorrelation pitch pass on a low-passed copy -> (F0 variance Hz^2, voiced ratio).

    Each frame is peak-normalised before correlation, so a quiet-but-clean voice
    still counts as voiced. Frames below the autocorrelation peak threshold are
    unvoiced; if fewer than two voiced frames survive, variance is reported 0.0.
    """
    n = int(window.size)
    if n < _MIN_SAMPLES or float(np.max(np.abs(window))) < 1e-4:
        return 0.0, 0.0
    voiced_signal = _lowpass(window, cutoff=min(VOICING_LOWPASS_HZ, sample_rate / 4.0),
                             sample_rate=sample_rate)
    frame_len = min(1024, n)
    step = max(1, frame_len // 2)
    lo = max(1, int(sample_rate / PITCH_MAX_HZ))
    hi = min(frame_len - 1, int(sample_rate / PITCH_MIN_HZ))
    f0s: List[float] = []
    analysed = 0
    if hi > lo:
        for start in range(0, n - frame_len + 1, step):
            frame = voiced_signal[start:start + frame_len]
            peak_amp = float(np.max(np.abs(frame)))
            if peak_amp < 1e-4:
                continue
            analysed += 1
            frame = frame / peak_amp * np.hanning(frame_len)
            corr = _autocorrelation(frame)
            if corr[0] <= _EPS:
                continue
            corr = corr / corr[0]
            peak = lo + int(np.argmax(corr[lo:hi + 1]))
            if corr[peak] < VOICING_CORR_MIN:
                continue                      # unvoiced frame
            f0s.append(float(sample_rate) / float(peak))
    voiced_ratio = (len(f0s) / analysed) if analysed else 0.0
    variance = float(np.var(np.asarray(f0s, dtype=np.float64))) if len(f0s) >= 2 else 0.0
    return variance, float(np.clip(voiced_ratio, 0.0, 1.0))



class FeatureExtractor:
    """Streaming acoustic features: one FFT per frame, no hidden globals.

    ``last_spectrum`` exposes the Hann magnitude spectrum that was already paid
    for, so the dashboard visualiser never triggers a second FFT.
    """

    def __init__(self, sample_rate: int = SAMPLE_RATE) -> None:
        self.sample_rate = int(sample_rate) if sample_rate else SAMPLE_RATE
        self.hf_cutoff = hf_cutoff_hz(self.sample_rate)
        self._prev_mag: Optional[np.ndarray] = None
        self._freqs: Optional[np.ndarray] = None
        self.last_spectrum: Optional[np.ndarray] = None

    def _frequency_grid(self, n: int) -> np.ndarray:
        if self._freqs is None or self._freqs.size != n // 2 + 1:
            self._freqs = rfftfreq(n, 1.0 / self.sample_rate)
        return self._freqs

    def extract(self, window: np.ndarray) -> Dict[str, float]:
        """Features for one PCM window (>=512 samples), else all zeros."""
        win = _sanitize(window, dtype=np.float64)
        if win.size < _MIN_SAMPLES:
            self._prev_mag = None
            self.last_spectrum = None
            return dict(_EMPTY_FEATURES)

        magnitude = np.abs(rfft(win * np.hanning(win.size)))
        self.last_spectrum = magnitude.astype(np.float32, copy=False)

        power = magnitude * magnitude
        total_power = float(power.sum()) + _EPS
        freqs = self._frequency_grid(win.size)
        hf_ratio = float(power[freqs >= self.hf_cutoff].sum()) / total_power

        flux = 0.0
        previous = self._prev_mag
        if previous is not None and previous.shape == magnitude.shape:
            diff = magnitude - previous
            np.maximum(diff, 0.0, out=diff)          # half-wave rectified flux
            flux = float(diff.sum()) / (float(previous.sum()) + _EPS)
        self._prev_mag = magnitude

        variance, voiced_ratio = _pitch_stats(win, self.sample_rate)
        rms = float(np.sqrt(np.mean(win * win)))
        return {
            "hf_power_ratio": round(float(np.clip(hf_ratio, 0.0, 1.0)), 6),
            "pitch_f0_variance": round(variance, 4),
            "voiced_ratio": round(voiced_ratio, 4),
            "spectral_flux": round(max(0.0, flux), 6),
            "rms_energy": round(rms, 6),
        }

    def reset(self) -> None:
        self._prev_mag = None
        self.last_spectrum = None


def extract_acoustic_features(pcm_chunk: np.ndarray,
                              sample_rate: int = SAMPLE_RATE) -> Dict[str, float]:
    """Features for a single PCM chunk - **pure and thread-safe**.

    Unlike the streaming :class:`FeatureExtractor`, this helper owns no module
    state: spectral flux is measured between the two halves of the chunk (when
    it is long enough), so repeated or concurrent calls are deterministic.
    """
    win = _sanitize(pcm_chunk, dtype=np.float64)
    if win.size < _MIN_SAMPLES:
        return dict(_EMPTY_FEATURES)
    features = FeatureExtractor(sample_rate).extract(win)
    if features["spectral_flux"] <= 0.0 and win.size >= 2 * _MIN_SAMPLES:
        half = win.size // 2
        probe = FeatureExtractor(sample_rate)
        probe.extract(win[:half])
        features["spectral_flux"] = probe.extract(win[half:])["spectral_flux"]
    return features


def mean_features(frames: List[Dict[str, float]]) -> Dict[str, float]:
    """Average a list of per-frame feature dicts (batch/file analysis path)."""
    if not frames:
        return dict(_EMPTY_FEATURES)
    return {
        key: round(float(np.mean([float(f.get(key, 0.0)) for f in frames])), 6)
        for key in FEATURE_KEYS
    }

