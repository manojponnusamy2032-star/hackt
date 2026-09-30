"""VoiceGuard FastAPI backend - SIH26104.

Single entrypoint for the React + FastAPI voice-verification platform:

  * REST : /api/health, /api/analyze, /api/features, /api/verify,
           /api/telemetry, /api/freeze-log, /api/simulator/reset
  * WS   : /ws/simulator  - continuous browser-mic PCM stream (float32 LE or int16)
           /ws/dashboard  - telemetry pushed *immediately* after every scored
                            frame, with a 200 ms heartbeat when the stream idles

Real-time contract
------------------
Every binary frame is stamped the moment it arrives (``arrival_ts``), decoded,
pushed through the hop-aligned 200 ms RAM window (50 % overlap), scored, and
answered with the sub-250 ms SLA figure. Nothing touches disk, and no blocking
call (torch, ffmpeg, container decode) ever runs on the event loop.

Run:  uvicorn backend.main:app --reload --port 8000
      python backend/main.py
"""
from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from math import gcd
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Set, Tuple

import numpy as np
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from scipy.fft import dct, rfft, rfftfreq
from scipy.signal import resample_poly

try:  # package import (uvicorn backend.main:app)
    from .audio_processor import (FEATURE_KEYS, HOP_SAMPLES, OVERLAP, SAMPLE_RATE, WINDOW_MS,
                                  AudioBufferManager, FeatureExtractor, extract_acoustic_features,
                                  mean_features)
    from .detection_engine import (DetectionEngine, THRESHOLDS, VOICING_RULES,
                                   calculate_anomaly_score, score_components)
    from .mock_bank_api import (MAX_LOG_ENTRIES as MAX_LOG_CAPACITY, freeze_log_size,
                                freeze_transaction, freeze_transaction_async, get_freeze_log)
    from .risk_scorer import BANDS, RiskScorer, classify_risk, clamp_score
except ImportError:  # direct script execution (python backend/main.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from audio_processor import (FEATURE_KEYS, HOP_SAMPLES, OVERLAP, SAMPLE_RATE, WINDOW_MS,
                                 AudioBufferManager, FeatureExtractor, extract_acoustic_features,
                                 mean_features)
    from detection_engine import (DetectionEngine, THRESHOLDS, VOICING_RULES,
                                  calculate_anomaly_score, score_components)
    from mock_bank_api import (MAX_LOG_ENTRIES as MAX_LOG_CAPACITY, freeze_log_size,
                               freeze_transaction, freeze_transaction_async, get_freeze_log)
    from risk_scorer import BANDS, RiskScorer, classify_risk, clamp_score

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Optional pipeline hook: risk_engine.prevention.take_action (LOW/MEDIUM/HIGH/CRITICAL).
try:
    from risk_engine.prevention import take_action as _external_take_action
    PREVENTION_SOURCE = "risk_engine.prevention"
except Exception as _exc:  # pragma: no cover - optional integration
    _external_take_action = None
    PREVENTION_SOURCE = f"local-fallback ({type(_exc).__name__})"

LATENCY_BUDGET_MS = 250.0
BROADCAST_INTERVAL_S = 0.2          # dashboard heartbeat cadence
LATENCY_EMA_ALPHA = 0.3
APP_VERSION = "2.1.0"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
UPLOAD_READ_CHUNK = 1024 * 1024
MAX_WS_FRAME_BYTES = 4 * 1024 * 1024
MIN_WS_FRAME_SAMPLES = 8
ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm", ".opus", ".aac"}
ALLOWED_SAMPLE_RATES = {8000, 16000, 22050, 44100, 48000}
PCM_FORMATS = {"auto", "float32", "int16"}
FFT_BINS = 64
DASHBOARD_QUEUE_SIZE = 8
START_TIME = time.time()

LEVEL_TO_ENGINE_RISK = {"SAFE": "LOW", "WARNING": "MEDIUM", "CRITICAL FRAUD": "CRITICAL"}


def prevention_action(level: str) -> Dict[str, str]:
    """Map a streaming risk level onto the legacy prevention action payload."""
    engine_level = LEVEL_TO_ENGINE_RISK.get(level, "MEDIUM")
    if _external_take_action is not None:
        try:
            action = dict(_external_take_action(engine_level))
            action["risk_level"] = engine_level
            return action
        except Exception:
            pass
    fallback = {
        "LOW": ("ALLOW", "Interaction appears safe."),
        "MEDIUM": ("VERIFY", "Additional verification is required."),
        "CRITICAL": ("BLOCK", "Critical threat detected. Interaction is blocked."),
    }
    act, msg = fallback.get(engine_level, ("REVIEW", "Manual review required."))
    return {"action": act, "message": msg, "risk_level": engine_level}


def _pcm_format_choices() -> Dict[str, str]:
    return {
        "float32": "binary little-endian float32 mono in [-1, 1] (browser default)",
        "int16": "binary little-endian int16 mono",
        "auto": "sniffed per frame; a near-silent float32 read falls back to int16",
    }


# --------------------------------------------------------------- telemetry hub
@dataclass
class Telemetry:
    """Latest snapshot pushed to every /ws/dashboard client."""

    session_id: str = "unassigned"
    source: str = "idle"
    risk_score: float = 0.0
    raw_score: float = 0.0
    level: str = "SAFE"
    features: Dict[str, float] = field(default_factory=dict)
    band_scores: Dict[str, float] = field(default_factory=dict)
    fft: List[float] = field(default_factory=lambda: [0.0] * FFT_BINS)
    latency_ms: float = 0.0
    latency_ema_ms: float = 0.0
    latency_max_ms: float = 0.0
    latency_breakdown_ms: Dict[str, float] = field(default_factory=dict)
    sla_ok: bool = True
    chunks_processed: int = 0
    windows_scored: int = 0
    critical_events: int = 0
    window_fill: float = 0.0
    hop_samples: int = HOP_SAMPLES
    overlap: float = OVERLAP
    freeze_count: int = 0
    bank_status: str = "not triggered"
    last_freeze: Optional[Dict[str, Any]] = None
    updated_at: float = field(default_factory=time.time)

    def snapshot(self, uptime_s: float) -> Dict[str, Any]:
        return {
            "type": "telemetry",
            "ts": time.time(),
            "uptime_s": round(uptime_s, 2),
            "session_id": self.session_id,
            "source": self.source,
            "risk_score": round(self.risk_score, 2),
            "raw_score": round(self.raw_score, 2),
            "level": self.level,
            "features": self.features,
            "band_scores": self.band_scores,
            "fft": self.fft,
            "latency_ms": round(self.latency_ms, 2),
            "latency_ema_ms": round(self.latency_ema_ms, 2),
            "latency_max_ms": round(self.latency_max_ms, 2),
            "latency_breakdown_ms": {k: round(v, 3) for k, v in self.latency_breakdown_ms.items()},
            "sla_budget_ms": LATENCY_BUDGET_MS,
            "sla_ok": bool(self.sla_ok),
            "chunks_processed": self.chunks_processed,
            "windows_scored": self.windows_scored,
            "critical_events": self.critical_events,
            "window_fill": round(self.window_fill, 3),
            "hop_samples": self.hop_samples,
            "overlap": self.overlap,
            "bank": {
                "status": self.bank_status,
                "freeze_count": self.freeze_count,
                "last_freeze": self.last_freeze,
            },
            "updated_at": self.updated_at,
        }


def latency_ema(previous: float, current: float, alpha: float = LATENCY_EMA_ALPHA) -> float:
    return current if previous <= 0 else alpha * current + (1.0 - alpha) * previous



class TelemetryHub:
    """Shared snapshot + fan-out to dashboard sockets.

    ``publish`` mutates the snapshot and immediately offers it to every
    subscriber queue, so the React dashboard sees each scored frame *as it is
    produced* instead of waiting for the next 200 ms tick. The periodic sender
    still emits a heartbeat when the stream idles, which keeps the SLA clock and
    the "live" feel without any per-client polling.
    """

    def __init__(self) -> None:
        self.state = Telemetry()
        self._subscribers: Set[asyncio.Queue] = set()
        self.publishes = 0

    # ---------------------------------------------------------- subscription
    def subscribe(self, maxsize: int = DASHBOARD_QUEUE_SIZE) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # --------------------------------------------------------------- publish
    def _fan_out(self) -> None:
        if not self._subscribers:
            return
        payload = self.state.snapshot(time.time() - START_TIME)
        for queue in list(self._subscribers):
            if queue.full():                 # slow client: keep only the newest
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:   # pragma: no cover - race only
                    pass
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:        # pragma: no cover - dropped on purpose
                pass

    def publish(self, **fields: Any) -> Dict[str, Any]:
        """Apply fields to the shared snapshot and push it to subscribers."""
        for key, value in fields.items():
            if hasattr(self.state, key):
                setattr(self.state, key, value)
        self.state.updated_at = time.time()
        self.publishes += 1
        self._fan_out()
        return self.state.snapshot(time.time() - START_TIME)

    def snapshot(self) -> Dict[str, Any]:
        return self.state.snapshot(time.time() - START_TIME)

    def reset(self, source: str = "idle") -> None:
        """Clear the live snapshot; the bank audit log is intentionally kept."""
        self.state.session_id = "unassigned"
        self.state.source = source
        self.state.risk_score = 0.0
        self.state.raw_score = 0.0
        self.state.level = "SAFE"
        self.state.features = {}
        self.state.band_scores = {}
        self.state.fft = [0.0] * FFT_BINS
        self.state.latency_ms = 0.0
        self.state.latency_ema_ms = 0.0
        self.state.latency_max_ms = 0.0
        self.state.latency_breakdown_ms = {}
        self.state.sla_ok = True
        self.state.window_fill = 0.0
        self.state.bank_status = "not triggered"
        self.state.updated_at = time.time()


HUB = TelemetryHub()


def reset_hub(source: str = "idle") -> None:
    """Backwards-compatible module helper (HTTP reset + session reset)."""
    HUB.reset(source=source)


def fft_spectrum(magnitude: Optional[np.ndarray], bins: int = FFT_BINS) -> List[float]:
    """Downsample an already-computed magnitude spectrum into ``bins`` floats.

    Reusing the extractor's spectrum means the dashboard visualiser costs one
    log-scaling pass instead of a fourth FFT per frame.
    """
    if magnitude is None:
        return [0.0] * bins
    mag = np.asarray(magnitude, dtype=np.float64).ravel()
    if mag.size < 2:
        return [0.0] * bins
    mag = np.log1p(mag * 100.0)
    if mag.size >= bins:
        idx = np.linspace(0, mag.size - 1, bins)
        mag = np.interp(idx, np.arange(mag.size), mag)
    else:
        mag = np.pad(mag, (0, bins - mag.size))
    peak = float(np.max(mag))
    if peak <= 0.0:
        return [0.0] * bins
    return [round(float(v / peak), 4) for v in mag]

# ---------------------------------------------------------- streaming session
@dataclass
class FrameTimings:
    """Where one inbound frame spent its milliseconds (all values in ms)."""

    decode_ms: float = 0.0
    buffer_ms: float = 0.0
    features_ms: float = 0.0
    score_ms: float = 0.0
    publish_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        return {
            "decode": round(self.decode_ms, 3),
            "buffer": round(self.buffer_ms, 3),
            "features": round(self.features_ms, 3),
            "score": round(self.score_ms, 3),
            "publish": round(self.publish_ms, 3),
            "total": round(self.total_ms, 3),
        }


class SimulatorSession:
    """Per-WebSocket streaming state.

    ``arrival -> decode -> RAM window (50 % overlap) -> features -> anomaly
    score -> EMA risk -> freeze hook -> telemetry publish``, all synchronously
    in this call so ``delta_t`` is a true end-to-end figure (no queue hop that
    would hide back-pressure).
    """

    def __init__(self, session_id: str = "", sample_rate: int = SAMPLE_RATE,
                 overlap: float = OVERLAP, hub: Optional[TelemetryHub] = None) -> None:
        self.session_id = (session_id or "").strip() or f"sim-{uuid.uuid4().hex[:8]}"
        self.sample_rate = int(sample_rate) if sample_rate in ALLOWED_SAMPLE_RATES else SAMPLE_RATE
        self.overlap = float(overlap)
        self.hub = hub or HUB
        self.buffer = AudioBufferManager(sample_rate=self.sample_rate, window_ms=WINDOW_MS,
                                         overlap=self.overlap)
        self.extractor = FeatureExtractor(sample_rate=self.sample_rate)
        self.engine = DetectionEngine()
        self.scorer = RiskScorer()
        self.chunks = 0
        self.windows_scored = 0
        self.critical_events = 0
        self.freeze_count = 0
        self.latency_max_ms = 0.0
        self.last_freeze: Optional[Dict[str, Any]] = None
        self.last_features: Dict[str, float] = {}
        self.last_bands: Dict[str, float] = {}
        self.last_state = None
        self._bank_status = "not triggered"

    # -------------------------------------------------------------- lifecycle
    def configure(self, sample_rate: Optional[int] = None,
                  overlap: Optional[float] = None) -> Dict[str, Any]:
        """Re-tune the stream live (e.g. the browser changed context rate)."""
        if sample_rate in ALLOWED_SAMPLE_RATES:
            self.sample_rate = int(sample_rate)
        if overlap is not None:
            self.overlap = float(min(max(float(overlap), 0.0), 0.9))
        self.buffer = AudioBufferManager(sample_rate=self.sample_rate, window_ms=WINDOW_MS,
                                         overlap=self.overlap)
        self.extractor = FeatureExtractor(sample_rate=self.sample_rate)
        return {"sample_rate": self.sample_rate, "overlap": self.buffer.overlap,
                "buffer": self.buffer.stats()}

    def reset(self) -> Dict[str, Any]:
        """Clear the RAM window, EMA and per-session counters."""
        self.buffer.reset()
        self.extractor.reset()
        self.scorer.reset()
        self.chunks = 0
        self.windows_scored = 0
        self.critical_events = 0
        self.freeze_count = 0
        self.latency_max_ms = 0.0
        self.last_freeze = None
        self.last_features = {}
        self.last_bands = {}
        self.last_state = None
        self._bank_status = "not triggered"
        self.hub.reset(source="simulator")
        self.hub.publish(session_id=self.session_id, source="simulator")
        return self.snapshot()

    def snapshot(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sample_rate": self.sample_rate,
            "chunk_index": self.chunks,
            "windows_scored": self.windows_scored,
            "risk_score": self.scorer.current,
            "level": self.scorer.level,
            "critical_events": self.critical_events,
            "freeze_count": self.freeze_count,
            "latency_max_ms": round(self.latency_max_ms, 3),
            "buffer": self.buffer.stats(),
            "scorer": self.scorer.snapshot(),
        }

    @property
    def bank_status(self) -> str:
        """not triggered | monitoring (WARNING) | FROZEN | cleared (risk normalised)."""
        return self._bank_status

    # ---------------------------------------------------------------- ingest
    def _update_bank_status(self, state) -> None:
        if state.bank_freeze:
            self._bank_status = "FROZEN"
        elif self._bank_status == "FROZEN" and state.level == "SAFE":
            self._bank_status = "cleared (risk normalised)"
        elif self._bank_status == "not triggered" and state.level == "WARNING":
            self._bank_status = "monitoring (WARNING)"

    def _publish_window(self, features: Dict[str, float], detection, state,
                        timings: FrameTimings, arrival: float) -> None:
        """Push one scored window to every dashboard socket immediately."""
        timings.total_ms = (time.perf_counter() - arrival) * 1000.0
        self.latency_max_ms = max(self.latency_max_ms, timings.total_ms)
        started = time.perf_counter()
        self.hub.publish(
            session_id=self.session_id,
            source="simulator",
            risk_score=state.smoothed_score,
            raw_score=state.raw_score,
            level=state.level,
            features=features,
            band_scores=detection.band_scores,
            fft=fft_spectrum(self.extractor.last_spectrum),
            latency_ms=timings.total_ms,
            latency_ema_ms=latency_ema(self.hub.state.latency_ema_ms, timings.total_ms),
            latency_max_ms=self.latency_max_ms,
            latency_breakdown_ms=timings.to_dict(),
            sla_ok=bool(timings.total_ms <= LATENCY_BUDGET_MS),
            chunks_processed=self.chunks,
            windows_scored=self.windows_scored,
            critical_events=self.critical_events,
            freeze_count=self.freeze_count,
            bank_status=self._bank_status,
            last_freeze=self.last_freeze,
            window_fill=self.buffer.fill_ratio(),
            hop_samples=self.buffer.hop,
            overlap=self.buffer.overlap,
        )
        timings.publish_ms += (time.perf_counter() - started) * 1000.0

    def ingest(self, pcm: np.ndarray, arrival_ts: Optional[float] = None,
               decode_ms: float = 0.0) -> Dict[str, Any]:
        """Process one PCM chunk end-to-end and return the feedback payload.

        ``arrival_ts`` is the ``perf_counter`` reading taken the moment the frame
        came off the socket, so ``latency_ms`` covers decode + buffering +
        features + scoring + publish - the figure the SLA is judged on.
        """
        arrival = float(arrival_ts) if arrival_ts is not None else time.perf_counter()
        timings = FrameTimings(decode_ms=max(0.0, float(decode_ms)))
        samples = int(np.asarray(pcm).size)

        started = time.perf_counter()
        windows = self.buffer.push(pcm)
        timings.buffer_ms = (time.perf_counter() - started) * 1000.0
        self.chunks += 1

        detection = None
        state = self.last_state
        freeze_payload: Optional[Dict[str, Any]] = None
        features = self.last_features
        for window in windows:
            started = time.perf_counter()
            features = self.extractor.extract(window)
            timings.features_ms += (time.perf_counter() - started) * 1000.0

            started = time.perf_counter()
            detection = self.engine.score(features)
            state = self.scorer.update(detection.anomaly_score)
            timings.score_ms += (time.perf_counter() - started) * 1000.0

            self.windows_scored += 1
            self.last_features = features
            self.last_bands = detection.band_scores
            self.last_state = state

            if state.bank_freeze:        # rising edge of a critical episode only
                self.critical_events += 1
                freeze_payload = freeze_transaction(
                    self.session_id, state.smoothed_score,
                    reason=f"CRITICAL FRAUD voice risk (episode {state.episode_id})",
                    idempotency_key=f"{self.session_id}:{state.episode_id}",
                    metadata={"level": state.level, "raw_score": state.raw_score},
                )
                self.freeze_count += 1
                self.last_freeze = freeze_payload
            self._update_bank_status(state)
            self._publish_window(features, detection, state, timings, arrival)

        if not windows:                  # cold start: report buffering progress
            timings.total_ms = (time.perf_counter() - arrival) * 1000.0
            self.hub.publish(session_id=self.session_id, source="simulator",
                             chunks_processed=self.chunks,
                             window_fill=self.buffer.fill_ratio(),
                             latency_ms=timings.total_ms,
                             latency_breakdown_ms=timings.to_dict(),
                             sla_ok=bool(timings.total_ms <= LATENCY_BUDGET_MS))

        processing_ms = timings.features_ms + timings.score_ms
        return {
            "type": "feedback",
            "session_id": self.session_id,
            "chunk_index": self.chunks,
            "samples": samples,
            "window_ready": bool(windows),
            "windows_scored": len(windows),
            "total_windows_scored": self.windows_scored,
            "window_samples": self.buffer.capacity,
            "hop_samples": self.buffer.hop,
            "overlap": self.buffer.overlap,
            "window_fill": round(self.buffer.fill_ratio(), 3),
            "sample_rate": self.sample_rate,
            "features": features,
            "band_scores": detection.band_scores if detection is not None else self.last_bands,
            "raw_score": state.raw_score if state is not None else 0.0,
            "risk_score": state.smoothed_score if state is not None else self.scorer.current,
            "level": state.level if state is not None else self.scorer.level,
            "critical": bool(state.critical) if state is not None else False,
            "episode_id": state.episode_id if state is not None else None,
            "bank_freeze": bool(freeze_payload is not None),
            "freeze": freeze_payload,
            "bank_status": self._bank_status,
            "latency_ms": round(timings.total_ms, 3),
            "processing_ms": round(processing_ms, 3),
            "latency_breakdown_ms": timings.to_dict(),
            "sla_budget_ms": LATENCY_BUDGET_MS,
            "sla_ok": bool(timings.total_ms <= LATENCY_BUDGET_MS),
        }
# ------------------------------------------------------ PCM frame decoding
def _decode_int16(payload: bytes) -> np.ndarray:
    usable = payload[: len(payload) // 2 * 2]
    if not usable:
        return np.zeros(0, dtype=np.float32)
    values = np.frombuffer(usable, dtype="<i2").astype(np.float32) / 32768.0
    return np.clip(values, -1.0, 1.0, out=values)


def _decode_float32(payload: bytes) -> np.ndarray:
    usable = payload[: len(payload) // 4 * 4]
    if not usable:
        return np.zeros(0, dtype=np.float32)
    values = np.frombuffer(usable, dtype="<f4").astype(np.float32, copy=True)
    np.nan_to_num(values, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
    return np.clip(values, -1.0, 1.0, out=values)


def decode_pcm_frame(payload: bytes, fmt: str = "auto") -> np.ndarray:
    """Decode a binary WS frame into float32 PCM in [-1, 1].

    Float32 little-endian is the browser contract. ``auto`` sniffs the frame
    because a 6400-byte int16 buffer is *also* divisible by four: it would be
    read as 1600 float32 denormals and silently scored as silence. When the
    float32 reading looks silent but the int16 reading carries real energy, the
    int16 interpretation wins; otherwise float32 is kept.
    """
    if not payload:
        return np.zeros(0, dtype=np.float32)
    choice = (fmt or "auto").strip().lower()
    if choice == "int16":
        return _decode_int16(payload)
    if choice == "float32":
        return _decode_float32(payload)

    if len(payload) % 4 == 0:
        view = np.frombuffer(payload, dtype="<f4")
        if view.size and bool(np.all(np.isfinite(view))):
            peak = float(np.max(np.abs(view)))
            if peak <= 1.5:
                if peak >= 1e-4:
                    return _decode_float32(payload)
                int16_peak = 0.0
                if len(payload) % 2 == 0:
                    int16_peak = abs(float(np.max(np.abs(np.frombuffer(payload, dtype="<i2"))))) / 32768.0
                if int16_peak <= 1e-4:
                    return _decode_float32(payload)      # genuinely silent
                return _decode_int16(payload)            # silent float32 = misread int16
    return _decode_int16(payload)


def decode_json_audio(message: Dict[str, Any]) -> np.ndarray:
    """Decode a JSON control frame carrying PCM (list, base64 or nested dict)."""
    raw: Any = message.get("pcm", message.get("data"))
    fmt = str(message.get("format", "float32")).lower()
    if isinstance(raw, dict):
        raw = raw.get("b64") or raw.get("base64") or raw.get("float32") or raw.get("int16")
    if raw is None:
        return np.zeros(0, dtype=np.float32)
    if isinstance(raw, str):
        try:
            buf = base64.b64decode(raw, validate=False)
        except Exception as exc:
            raise ValueError(f"invalid base64 payload: {exc}") from exc
        if fmt in {"int16", "i16", "pcm16"}:
            return decode_pcm_frame(buf, "int16")
        return decode_pcm_frame(buf, fmt if fmt in PCM_FORMATS else "float32")
    arr = np.asarray(raw, dtype=np.float64).ravel()
    arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)
    if fmt in {"int16", "i16", "pcm16"} or (arr.size and float(np.max(np.abs(arr))) > 8.0):
        arr = arr / 32768.0
    return np.clip(arr, -1.0, 1.0).astype(np.float32, copy=False)


def decode_binary_control(payload: bytes) -> Optional[Dict[str, Any]]:
    """Treat a binary frame as JSON control data when it unambiguously is one.

    Lets a client keep a *single* binary pipeline (JSON frames encoded with
    TextEncoder) while the text channel stays available for tooling.
    """
    if len(payload) < 2 or len(payload) > 65536 or payload[:1] != b"{":
        return None
    try:
        data = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if isinstance(data, dict) and isinstance(data.get("type"), str):
        return data
    return None


async def iter_ws_frames(websocket: WebSocket) -> AsyncIterator[Tuple[str, Any]]:
    """Continuous frame pump for the simulator socket.

    Semantically identical to ``async for chunk in websocket.iter_bytes()`` -
    same Starlette receive loop, same ``WebSocketDisconnect`` handling - but it
    also surfaces text frames. That matters: ``receive_bytes`` returns ``None``
    for a text frame, so a bare ``iter_bytes()`` loop would silently swallow the
    JSON control channel (reset/stop/ping) that the dashboard client uses.
    """
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                return
            binary = message.get("bytes")
            if binary is not None:
                yield "binary", binary
                continue
            text = message.get("text")
            if text is not None:
                yield "text", text
    except WebSocketDisconnect:
        return
# ------------------------------------------------------ container -> PCM 16k
def _decode_with_soundfile(raw: bytes) -> Optional[np.ndarray]:
    try:
        import io

        import soundfile as sf

        data, sr = sf.read(io.BytesIO(raw), dtype="float32", always_2d=False)
    except Exception:
        return None
    audio = np.asarray(data, dtype=np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if sr != SAMPLE_RATE and audio.size:
        divisor = gcd(int(sr), SAMPLE_RATE) or 1
        audio = resample_poly(audio, SAMPLE_RATE // divisor, int(sr) // divisor).astype(np.float32)
    return audio


def _decode_with_ffmpeg(raw: bytes) -> Optional[np.ndarray]:
    """ffmpeg over stdin/stdout pipes - no temp file ever touches the disk."""
    exe = shutil.which("ffmpeg")
    if not exe:
        return None
    cmd = [exe, "-hide_banner", "-loglevel", "error", "-i", "pipe:0",
           "-f", "f32le", "-ac", "1", "-ar", str(SAMPLE_RATE), "pipe:1"]
    try:
        proc = subprocess.run(cmd, input=raw, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=30)
    except Exception:
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    audio = np.frombuffer(proc.stdout, dtype="<f4").astype(np.float32)
    return audio if audio.size else None


def load_audio_bytes(raw: bytes, filename: str = "upload.wav") -> np.ndarray:
    """Decode any uploaded container to mono float32 @16 kHz (soundfile -> ffmpeg)."""
    if not raw:
        raise ValueError("empty audio payload")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("audio exceeds 25 MB limit")
    ext = Path(filename or "upload.wav").suffix.lower()
    if ext and ext not in ALLOWED_EXTS:
        raise ValueError(f"unsupported extension '{ext}'")
    audio = _decode_with_soundfile(raw)
    if audio is None or audio.size == 0:
        audio = _decode_with_ffmpeg(raw)
    if audio is None or audio.size == 0:
        raise ValueError("could not decode audio (need wav/flac/ogg, or a working ffmpeg for mp3/m4a/webm)")
    audio = np.nan_to_num(np.asarray(audio, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(audio)))
    if peak > 0:
        audio = (audio / peak).astype(np.float32)
    return np.clip(audio, -1.0, 1.0)


def score_waveform(audio: np.ndarray, hop_ms: int = 100) -> Tuple[Dict[str, float], float]:
    """Frame a whole waveform through the *same* streaming feature path.

    Returns ``(mean_features, anomaly_score)`` so an upload and a live mic
    stream are scored by identical maths - including the voicing rule, which the
    previous version dropped by averaging only four of the five features.
    """
    arr = np.asarray(audio, dtype=np.float64).ravel()
    window = AudioBufferManager().capacity
    hop = max(1, SAMPLE_RATE * hop_ms // 1000)
    if arr.size < window:
        arr = np.pad(arr, (window - arr.size, 0))
    extractor = FeatureExtractor()
    frames: List[Dict[str, float]] = []
    for start in range(0, arr.size - window + 1, hop):
        frames.append(extractor.extract(arr[start:start + window]))
        if len(frames) >= 200:      # cap the work for long uploads (~20 s of hops)
            break
    if not frames:
        frames = [extractor.extract(arr[:window])]
    features = mean_features(frames)
    return features, calculate_anomaly_score(features)
# ------------------------------------------------------- speaker verification
def _mel_filterbank(n_mels: int = 26, n_fft: int = 512, sr: int = SAMPLE_RATE,
                    fmin: float = 50.0, fmax: float = 7600.0) -> np.ndarray:
    def hz_to_mel(f: float) -> float:
        return 2595.0 * np.log10(1.0 + f / 700.0)

    def mel_to_hz(m: np.ndarray) -> np.ndarray:
        return 700.0 * (10.0 ** (m / 2595.0) - 1.0)

    mel_points = np.linspace(hz_to_mel(fmin), hz_to_mel(fmax), n_mels + 2)
    bins = np.floor((n_fft + 1) * mel_to_hz(mel_points) / sr).astype(int)
    bins = np.clip(bins, 0, n_fft // 2)
    fb = np.zeros((n_mels, n_fft // 2 + 1), dtype=np.float64)
    for m in range(1, n_mels + 1):
        left, center, right = bins[m - 1], bins[m], bins[m + 1]
        if center <= left or right <= center:
            continue
        fb[m - 1, left:center] = np.linspace(0.0, 1.0, center - left, endpoint=False)
        fb[m - 1, center:right] = np.linspace(1.0, 0.0, right - center, endpoint=False)
    return fb


_MEL_FB = _mel_filterbank()


def mfcc_embedding(y: np.ndarray, sr: int = SAMPLE_RATE, n_mfcc: int = 20) -> np.ndarray:
    """Pure NumPy/SciPy MFCC (log-mel + DCT-II) embedding - no librosa needed."""
    audio = np.asarray(y, dtype=np.float64).ravel()
    if audio.size == 0:
        return np.zeros(n_mfcc * 2, dtype=np.float64)
    n_fft, hop = 512, 256
    if audio.size < n_fft:
        audio = np.pad(audio, (0, n_fft - audio.size))
    frames = max(1, min(1 + (audio.size - n_fft) // hop, 512))
    spec = np.empty((frames, n_fft // 2 + 1), dtype=np.float64)
    for i in range(frames):
        seg = audio[i * hop: i * hop + n_fft]
        spec[i] = np.abs(rfft(seg * np.hanning(seg.size))) ** 2
    mel = np.log(spec @ _MEL_FB.T + 1e-10)
    ceps = dct(mel, type=2, axis=1, norm="ortho")[:, 1:n_mfcc + 1]   # drop C0 (loudness)
    feat = np.concatenate([ceps.mean(axis=0), ceps.std(axis=0)])
    # Mean-centre across coefficients: removes the shared spectral-tilt direction
    # that otherwise pushes unrelated voices toward cosine ~1.0.
    feat = feat - feat.mean()
    norm = float(np.linalg.norm(feat))
    return feat / norm if norm > 0 else feat


def verify_speakers(y_test: np.ndarray, y_ref: np.ndarray) -> Dict[str, Any]:
    e1, e2 = mfcc_embedding(y_test), mfcc_embedding(y_ref)
    cos = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-10))
    score = float(np.clip((cos + 1.0) / 2.0, 0.0, 1.0))
    return {"speaker_match_score": round(score, 4), "cosine_similarity": round(cos, 4),
            "speaker_verified": bool(score >= 0.75), "threshold": 0.75}


# ------------------------------------------------- optional AASIST M2 model
_DETECTOR: Dict[str, Any] = {"obj": None, "resolved": False, "error": None, "loading": False}
_DETECTOR_LOCK = threading.Lock()


def get_deepfake_detector():
    """Lazy, thread-safe AASIST load - returns None (never raises) when absent.

    The lock is held across the load so concurrent uploads cannot each import
    torch and build the model. It is always called from a worker thread, never
    from the event loop.
    """
    with _DETECTOR_LOCK:
        if _DETECTOR["resolved"]:
            return _DETECTOR["obj"]
        _DETECTOR["loading"] = True
        obj, error = None, None
        try:
            from deepfake_detection.AASIST import AASISTDetector

            obj = AASISTDetector()
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        _DETECTOR.update(obj=obj, error=error, resolved=True, loading=False)
    return obj


def detector_state() -> Dict[str, Any]:
    """Non-blocking view of the optional model (never triggers a load)."""
    with _DETECTOR_LOCK:
        available = _DETECTOR["obj"] is not None
        return {
            "available": available,
            "resolved": bool(_DETECTOR["resolved"]),
            "loading": bool(_DETECTOR["loading"]),
            "error": _DETECTOR["error"],
        }


def probe_detector() -> Dict[str, Any]:
    """Warm the optional model in the background at startup."""
    get_deepfake_detector()
    return detector_state()


def run_aasist(audio: np.ndarray) -> Optional[Dict[str, float]]:
    detector = get_deepfake_detector()
    if detector is None:
        return None
    try:
        import torch
        from deepfake_detection.inference import TARGET_SAMPLES

        arr = np.asarray(audio, dtype=np.float32)
        arr = np.pad(arr, (0, max(0, TARGET_SAMPLES - arr.size)))[:TARGET_SAMPLES]
        with torch.no_grad():
            out = detector.predict(torch.tensor(arr, dtype=torch.float32).unsqueeze(0))
        if not isinstance(out, dict) or "synthetic_probability" not in out:
            return None
        return {k: float(v) for k, v in out.items() if isinstance(v, (int, float))}
    except Exception:
        with _DETECTOR_LOCK:
            _DETECTOR["error"] = traceback.format_exc(limit=1).strip().splitlines()[-1]
        return None
# ------------------------------------------------------------------- fusion
def build_detection(audio: np.ndarray) -> Tuple[Dict[str, Any], str]:
    """Acoustic anomaly + optional AASIST fusion -> detection payload + backend tag."""
    features, anomaly = score_waveform(audio)
    aasist = run_aasist(audio)
    acoustic_prob = float(np.clip(anomaly / 100.0, 0.0, 1.0))
    if aasist is not None:
        synthetic = float(np.clip(0.75 * aasist.get("synthetic_probability", acoustic_prob)
                                  + 0.25 * acoustic_prob, 0.0, 1.0))
        backend = "aasist + acoustic-fusion"
    else:
        synthetic = acoustic_prob
        backend = "acoustic-heuristic (aasist unavailable)"
    detection = {
        "synthetic_probability": round(synthetic, 4),
        "authentic_probability": round(1.0 - synthetic, 4),
        "model_confidence": round(max(synthetic, 1.0 - synthetic), 4),
        "class_0_probability": round(synthetic, 4),
        "class_1_probability": round(1.0 - synthetic, 4),
        "anomaly_score": anomaly,
        "acoustic_features": features,
        "band_scores": score_components(features),
        "aasist_used": aasist is not None,
    }
    return detection, backend


def combine_risk(synthetic_probability: float, speaker_match_score: float) -> Dict[str, Any]:
    """0.6*deepfake + 0.4*speaker-mismatch (mirrors risk_engine.calculate_risk)."""
    risk_pct = round((0.6 * float(synthetic_probability)
                      + 0.4 * (1.0 - float(speaker_match_score))) * 100.0, 2)
    level = classify_risk(risk_pct)
    return {"risk_score": clamp_score(risk_pct),
            "risk_level": LEVEL_TO_ENGINE_RISK.get(level, "MEDIUM"),
            "stream_level": level,
            "deepfake_risk": round(float(synthetic_probability) * 100.0, 2),
            "speaker_risk": round((1.0 - float(speaker_match_score)) * 100.0, 2)}


async def publish_upload_telemetry(risk: Dict[str, Any], detection: Dict[str, Any],
                                   latency_ms: float, source: str,
                                   session_id: str) -> Optional[Dict[str, Any]]:
    """Feed a file-based analysis into the same live dashboard stream.

    The freeze hook runs off the event loop (``freeze_transaction_async``) so a
    bank call can never stall the WebSocket telemetry cadence.
    """
    freeze: Optional[Dict[str, Any]] = None
    bank_status = "not triggered"
    freeze_count = HUB.state.freeze_count
    critical_events = HUB.state.critical_events
    latency_ema_ms = latency_ema(HUB.state.latency_ema_ms, latency_ms)
    if risk["stream_level"] == "CRITICAL FRAUD":
        freeze = await freeze_transaction_async(
            session_id, risk["risk_score"],
            reason="CRITICAL FRAUD detected on uploaded voice sample",
            idempotency_key=f"{session_id}:upload",
        )
        bank_status = "FROZEN"
        freeze_count = max(freeze_count, freeze_log_size())
        critical_events += 1
    HUB.publish(
        session_id=session_id,
        source=source,
        risk_score=float(risk["risk_score"]),
        raw_score=float(detection.get("anomaly_score", 0.0)),
        level=risk.get("stream_level", classify_risk(risk["risk_score"])),
        features=detection.get("acoustic_features", {}),
        band_scores=detection.get("band_scores", {}),
        latency_ms=latency_ms,
        latency_ema_ms=latency_ema_ms,
        latency_max_ms=max(HUB.state.latency_max_ms, latency_ms),
        latency_breakdown_ms={"upload_total": latency_ms},
        sla_ok=bool(latency_ema_ms <= LATENCY_BUDGET_MS),
        chunks_processed=HUB.state.chunks_processed + 1,
        critical_events=critical_events,
        freeze_count=freeze_count,
        bank_status=bank_status if freeze else HUB.state.bank_status,
        last_freeze=freeze or HUB.state.last_freeze,
    )
    return freeze
# ---------------------------------------------------------------- FastAPI app
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm the optional deepfake model off-loop so the first WS never stalls."""
    probe = asyncio.create_task(asyncio.to_thread(probe_detector))
    app.state.detector_probe = probe
    app.state.started_at = time.time()
    try:
        yield
    finally:
        if not probe.done():
            probe.cancel()


app = FastAPI(
    title="VoiceGuard API",
    version=APP_VERSION,
    description="SIH26104 - real-time voice deepfake detection, risk scoring and bank-freeze hook.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def health_payload() -> Dict[str, Any]:
    """Capabilities + config (never triggers a model load)."""
    detector = detector_state()
    if detector["available"]:
        backend = "aasist"
    elif not detector["resolved"] or detector["loading"]:
        backend = "aasist (probing, acoustic fallback live)"
    else:
        backend = "acoustic-heuristic"
    return {
        "status": "ok",
        "service": "voiceguard-api",
        "version": APP_VERSION,
        "frameworks": {"api": "fastapi", "dsp": "numpy+scipy", "realtime": "websockets"},
        "sample_rate": SAMPLE_RATE,
        "window_ms": WINDOW_MS,
        "window_samples": AudioBufferManager().capacity,
        "hop_samples": HOP_SAMPLES,
        "overlap": OVERLAP,
        "latency_budget_ms": LATENCY_BUDGET_MS,
        "broadcast_interval_ms": int(BROADCAST_INTERVAL_S * 1000),
        "instant_broadcast": True,
        "max_ws_frame_bytes": MAX_WS_FRAME_BYTES,
        "pcm_formats": _pcm_format_choices(),
        "deepfake_backend": backend,
        "deepfake_note": detector["error"],
        "detector": detector,
        "prevention_source": PREVENTION_SOURCE,
        "risk_thresholds": {band: f"{int(low)}-{int(high)}" for band, (low, high) in BANDS.items()},
        "feature_keys": list(FEATURE_KEYS),
        "voicing_rules": VOICING_RULES,
        "endpoints": {
            "rest": ["/api/health", "/api/analyze", "/api/features", "/api/verify",
                     "/api/telemetry", "/api/freeze-log", "/api/simulator/reset"],
            "ws": ["/ws/simulator", "/ws/dashboard"],
        },
    }


@app.get("/")
@app.get("/api/health")
async def health() -> Dict[str, Any]:
    return health_payload()


@app.get("/api/telemetry")
async def telemetry() -> Dict[str, Any]:
    return HUB.snapshot()


@app.get("/api/freeze-log")
async def freeze_log(limit: int = 50) -> Dict[str, Any]:
    events = get_freeze_log(limit=limit)
    return {"count": len(events), "events": events, "capacity": MAX_LOG_CAPACITY,
            "subscribers": HUB.subscriber_count}


@app.post("/api/simulator/reset")
async def reset_simulator() -> Dict[str, Any]:
    reset_hub()
    return {"status": "reset", "telemetry": HUB.snapshot(), "freeze_log_kept": True}
# ------------------------------------------------------------- upload helpers
async def read_upload(upload: UploadFile, field: str,
                      max_bytes: int = MAX_UPLOAD_BYTES) -> np.ndarray:
    """Read an upload with the size cap enforced *while* streaming it in.

    The old path buffered the whole body first and only then compared against
    25 MB, so a hostile upload could exhaust RAM before being rejected.
    """
    filename = upload.filename or f"{field}.wav"
    pieces: List[bytes] = []
    total = 0
    while True:
        piece = await upload.read(UPLOAD_READ_CHUNK)
        if not piece:
            break
        total += len(piece)
        if total > max_bytes:
            raise HTTPException(status_code=413,
                                detail=f"'{field}' exceeds the {max_bytes // (1024 * 1024)} MB limit")
        pieces.append(piece)
    if not pieces:
        raise HTTPException(status_code=400, detail=f"'{field}' file is empty")
    raw = b"".join(pieces)
    try:
        return await asyncio.to_thread(load_audio_bytes, raw, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"could not decode '{field}': {exc}") from exc


@app.post("/api/analyze")
async def analyze(
    audio: UploadFile = File(...),
    reference: Optional[UploadFile] = File(default=None),
    claimed_speaker: str = Form(default="unknown"),
) -> Dict[str, Any]:
    """File-based pipeline - identical DSP path to the live simulator."""
    started = time.perf_counter()
    session_id = f"upload-{uuid.uuid4().hex[:8]}"
    waveform = await read_upload(audio, "audio")
    if waveform.size < SAMPLE_RATE // 4:
        raise HTTPException(status_code=400, detail="audio too short (minimum ~0.25s)")

    # Decoding + AASIST + framing are CPU-bound: run them in a worker thread so
    # the /ws/dashboard telemetry keeps flowing while an upload is analysed.
    detection, backend = await asyncio.to_thread(build_detection, waveform)

    if reference is not None and reference.filename:
        ref_wave = await read_upload(reference, "reference")
        speaker = await asyncio.to_thread(verify_speakers, waveform, ref_wave)
        speaker["note"] = "MFCC cosine similarity vs reference voice"
    else:
        speaker = {"speaker_match_score": 0.5, "cosine_similarity": 0.0, "speaker_verified": False,
                   "threshold": 0.75, "note": "no reference provided; neutral 0.5 used"}
    speaker["claimed_identity"] = (claimed_speaker or "unknown").strip() or "unknown"

    risk = combine_risk(detection["synthetic_probability"], speaker["speaker_match_score"])
    action = prevention_action(risk["stream_level"])
    freeze = await publish_upload_telemetry(risk, detection, (time.perf_counter() - started) * 1000.0,
                                            source="upload", session_id=session_id)
    latency_ms = (time.perf_counter() - started) * 1000.0

    return JSONResponse({
        "session_id": session_id,
        "filename": audio.filename or "sample.wav",
        "duration_s": round(waveform.size / SAMPLE_RATE, 2),
        "deepfake_backend": backend,
        "detection": detection,
        "speaker": speaker,
        "risk": risk,
        "prevention": action,
        "bank_freeze": freeze,
        "latency_ms": round(latency_ms, 2),
        "sla_budget_ms": LATENCY_BUDGET_MS,
    })


@app.post("/api/features")
async def features(audio: UploadFile = File(...)) -> Dict[str, Any]:
    """Inspection endpoint: raw acoustic features + the loudest 200 ms window."""
    waveform = await read_upload(audio, "audio")
    mean_feats, anomaly = await asyncio.to_thread(score_waveform, waveform)
    window = AudioBufferManager().capacity
    if waveform.size >= window:
        energy = np.convolve(waveform.astype(np.float64) ** 2, np.ones(window) / window, mode="valid")
        start = int(np.argmax(energy))
        loudest = waveform[start:start + window]
    else:
        loudest = waveform
    snapshot = await asyncio.to_thread(extract_acoustic_features, loudest)
    return JSONResponse({
        "filename": audio.filename or "sample.wav",
        "duration_s": round(waveform.size / SAMPLE_RATE, 2),
        "mean_features": mean_feats,
        "loudest_window_features": snapshot,
        "anomaly_score": anomaly,
        "band_scores": score_components(snapshot),
        "thresholds": {k: list(v) for k, v in THRESHOLDS.items()},
        "voicing_rules": VOICING_RULES,
    })


@app.post("/api/verify")
async def verify(
    audio: UploadFile = File(...),
    reference: UploadFile = File(...),
    claimed_speaker: str = Form(default="unknown"),
) -> Dict[str, Any]:
    y_test = await read_upload(audio, "audio")
    y_ref = await read_upload(reference, "reference")
    result = await asyncio.to_thread(verify_speakers, y_test, y_ref)
    result["claimed_identity"] = (claimed_speaker or "unknown").strip() or "unknown"
    return JSONResponse(result)
# --------------------------------------------------------- WS: mic simulator
def _coerce_sample_rate(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        rate = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return rate if rate in ALLOWED_SAMPLE_RATES else default


def _coerce_overlap(value: Any, default: float = OVERLAP) -> float:
    try:
        overlap = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return float(min(max(overlap, 0.0), 0.9))


def _coerce_pcm_format(value: Any, default: str = "auto") -> str:
    choice = str(value or "").strip().lower()
    return choice if choice in PCM_FORMATS else default


async def send_error_frame(websocket: WebSocket, message: str) -> None:
    try:
        await websocket.send_json({"type": "error", "error": message})
    except Exception:  # socket already closing
        pass


async def handle_simulator_control(websocket: WebSocket, session: SimulatorSession,
                                   data: Dict[str, Any], state: Dict[str, Any]) -> None:
    """Serve the JSON control channel (audio payloads, reset, stop, ping, config)."""
    kind = str(data.get("type", "audio")).lower()

    if kind in {"audio", "pcm", "chunk"}:
        arrival = time.perf_counter()
        try:
            pcm = decode_json_audio(data)
        except ValueError as exc:
            await send_error_frame(websocket, str(exc))
            return
        if pcm.size == 0:
            await send_error_frame(websocket, "JSON audio frame carried no PCM")
            return
        decode_ms = (time.perf_counter() - arrival) * 1000.0
        await websocket.send_json(session.ingest(pcm, arrival_ts=arrival, decode_ms=decode_ms))
        return

    if kind == "reset":
        snapshot = session.reset()
        await websocket.send_json({"type": "reset", "session_id": session.session_id,
                                   "session": snapshot})
    elif kind == "stop":
        await websocket.send_json({
            "type": "summary",
            "session_id": session.session_id,
            "chunks_processed": session.chunks,
            "windows_scored": session.windows_scored,
            "final_risk_score": session.scorer.current,
            "final_level": session.scorer.level,
            "latency_max_ms": round(session.latency_max_ms, 3),
            "bank": {"status": session.bank_status, "freeze_count": session.freeze_count,
                     "last_freeze": session.last_freeze},
            "scorer": session.scorer.snapshot(),
            "buffer": session.buffer.stats(),
        })
    elif kind == "ping":
        await websocket.send_json({"type": "pong", "ts": time.time(),
                                   "latency_ms": HUB.state.latency_ms})
    elif kind == "config":
        applied = session.configure(
            sample_rate=_coerce_sample_rate(data.get("sample_rate")),
            overlap=data.get("overlap") if isinstance(data.get("overlap"), (int, float)) else None,
        )
        if data.get("pcm") is not None:
            state["pcm_format"] = _coerce_pcm_format(data.get("pcm"), state["pcm_format"])
        await websocket.send_json({"type": "config", "session_id": session.session_id,
                                   "pcm_format": state["pcm_format"], **applied})
    else:
        await send_error_frame(websocket, f"unsupported message type '{kind}'")
@app.websocket("/ws/simulator")
async def ws_simulator(websocket: WebSocket) -> None:
    """Continuous browser-mic PCM in, per-frame risk feedback out.

    The loop is a real-time pump (``iter_ws_frames`` is Starlette's
    ``iter_bytes`` receive loop plus the text control channel): every frame is
    timestamped on arrival, decoded, scored through the 50 %-overlapped RAM
    window and answered immediately with its ``delta_t``.
    """
    await websocket.accept()
    params = websocket.query_params
    session = SimulatorSession(
        session_id=params.get("session_id") or "",
        sample_rate=_coerce_sample_rate(params.get("sample_rate"), SAMPLE_RATE) or SAMPLE_RATE,
        overlap=_coerce_overlap(params.get("overlap")),
    )
    state = {"pcm_format": _coerce_pcm_format(params.get("pcm"))}
    await websocket.send_json({
        "type": "ready",
        "session_id": session.session_id,
        "sample_rate": session.sample_rate,
        "window_ms": WINDOW_MS,
        "window_samples": session.buffer.capacity,
        "hop_samples": session.buffer.hop,
        "overlap": session.buffer.overlap,
        "latency_budget_ms": LATENCY_BUDGET_MS,
        "pcm_format": state["pcm_format"],
        "pcm_formats": sorted(PCM_FORMATS),
        "max_frame_bytes": MAX_WS_FRAME_BYTES,
        "accepts": ["binary float32 LE PCM", "binary int16 LE PCM",
                    "JSON {type:'audio', pcm:[...]}", "JSON base64 float32"],
        "controls": ["reset", "stop", "ping", "config"],
    })
    try:
        async for kind, payload in iter_ws_frames(websocket):
            arrival = time.perf_counter()
            if kind == "text":
                try:
                    data = json.loads(payload)
                except json.JSONDecodeError:
                    await send_error_frame(websocket, "invalid JSON frame")
                    continue
                if not isinstance(data, dict):
                    await send_error_frame(websocket, "JSON frame must be an object")
                    continue
                await handle_simulator_control(websocket, session, data, state)
                continue

            if len(payload) > MAX_WS_FRAME_BYTES:
                await send_error_frame(websocket, f"frame exceeds {MAX_WS_FRAME_BYTES} bytes")
                continue
            control = decode_binary_control(payload)
            if control is not None:
                await handle_simulator_control(websocket, session, control, state)
                continue

            pcm = decode_pcm_frame(payload, state["pcm_format"])
            decode_ms = (time.perf_counter() - arrival) * 1000.0
            if pcm.size < MIN_WS_FRAME_SAMPLES:
                await send_error_frame(websocket, "binary frame carried no usable PCM samples")
                continue
            await websocket.send_json(session.ingest(pcm, arrival_ts=arrival, decode_ms=decode_ms))
    except WebSocketDisconnect:
        pass
    except Exception:
        traceback.print_exc()
        await send_error_frame(websocket, "internal simulator error")
    finally:
        HUB.publish(source="idle")
# ------------------------------------------------------------ WS: dashboard
async def dashboard_sender(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Push telemetry the instant a frame is scored; heartbeat when idle.

    ``publish`` enqueues a snapshot for every subscriber queue, so the wait
    completes immediately after each scored window (sub-250 ms, typically ~1 ms).
    When the stream is quiet the 200 ms timeout keeps the SLA clock and the
    dashboard cadence alive.
    """
    while True:
        try:
            payload = await asyncio.wait_for(queue.get(), timeout=BROADCAST_INTERVAL_S)
        except asyncio.TimeoutError:
            payload = HUB.snapshot()
        await websocket.send_json(payload)


async def dashboard_receiver(websocket: WebSocket) -> None:
    """Handle client control frames (ping / reset) on the dashboard socket."""
    while True:
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return
        text = message.get("text")
        if not text:
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        kind = str(data.get("type", "")).lower()
        if kind == "ping":
            await websocket.send_json({"type": "pong", "ts": time.time()})
        elif kind == "reset":
            reset_hub()
            await websocket.send_json({"type": "reset", "telemetry": HUB.snapshot()})


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket) -> None:
    """Live telemetry: risk score, FFT bins, SLA latency and bank-freeze state."""
    await websocket.accept()
    queue = HUB.subscribe()
    try:
        await websocket.send_json({"type": "hello", **health_payload(),
                                   "telemetry": HUB.snapshot()})
        tasks = [
            asyncio.create_task(dashboard_sender(websocket, queue)),
            asyncio.create_task(dashboard_receiver(websocket)),
        ]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:                    # surface real errors, ignore closes
            error = task.exception()
            if error is not None and not isinstance(error, WebSocketDisconnect):
                traceback.print_exception(type(error), error, error.__traceback__)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        HUB.unsubscribe(queue)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
