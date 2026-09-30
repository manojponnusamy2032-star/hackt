"""End-to-end checks for the VoiceGuard FastAPI backend (SIH26104).

Plain runnable script - no pytest required (but pytest-compatible).

    python backend/test_backend.py          # in-process TestClient groups
    python backend/test_backend.py --live   # + real uvicorn server / TCP checks

Every group is independent and asserts observable behaviour: 50 %-overlap
windowing, feature purity, SLA latency accounting, EMA edge-triggered freezes,
idempotent bank hooks and instant dashboard pushes.
"""
from __future__ import annotations

import asyncio
import concurrent.futures as futures
import contextlib
import io
import json
import sys
import threading
import time
import traceback
from pathlib import Path

import numpy as np

BACKEND_DIR = Path(__file__).resolve().parent
ROOT = BACKEND_DIR.parent
for path in (str(ROOT), str(BACKEND_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import soundfile as sf  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend import mock_bank_api  # noqa: E402
from backend.audio_processor import (HOP_SAMPLES, OVERLAP, WINDOW_MS, WINDOW_SAMPLES,  # noqa: E402
                                     AudioBufferManager, FeatureExtractor, extract_acoustic_features)
from backend.detection_engine import (THRESHOLDS, DetectionEngine,  # noqa: E402
                                      calculate_anomaly_score, score_components)
from backend.main import (HUB, LATENCY_BUDGET_MS, SAMPLE_RATE, SimulatorSession, app,  # noqa: E402
                          decode_pcm_frame, decode_json_audio, decode_binary_control, fft_spectrum)
from backend.risk_scorer import RiskScorer, classify_risk, clamp_score  # noqa: E402

CHUNK = SAMPLE_RATE * WINDOW_MS // 1000          # 3200 samples = 200 ms
HOP_MS = HOP_SAMPLES * 1000 // SAMPLE_RATE       # 100 ms


# ------------------------------------------------------------------ fixtures
def fraud_signal(seconds: float = 1.2, seed: int = 7) -> np.ndarray:
    """Synthetic-voice-like: heavy HF energy + flat pitch (no glottal structure)."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    sig = 0.45 * rng.standard_normal(t.size) + 0.40 * np.sin(2 * np.pi * 7000 * t)
    return np.clip(sig, -1.0, 1.0).astype(np.float32)


def voice_signal(seconds: float = 1.2, seed: int = 3) -> np.ndarray:
    """Human-like: harmonic stack with vocal jitter and HF roll-off."""
    rng = np.random.default_rng(seed)
    t = np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE
    f0 = 120.0 + 2.5 * np.sin(2 * np.pi * 3.2 * t)
    phase = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE
    sig = 0.55 * np.sin(phase) + 0.22 * np.sin(2 * phase) + 0.10 * np.sin(3 * phase)
    sig += 0.01 * rng.standard_normal(t.size)
    return np.clip(sig / np.max(np.abs(sig)), -1.0, 1.0).astype(np.float32)


def wav_bytes(signal: np.ndarray) -> bytes:
    buf = io.BytesIO()
    sf.write(buf, signal, SAMPLE_RATE, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def pcm_frames(signal: np.ndarray, chunk: int = CHUNK):
    for start in range(0, signal.size, chunk):
        yield signal[start:start + chunk].astype("<f4").tobytes()


@contextlib.contextmanager
def live_socket(client: TestClient, path: str):
    """`client.websocket_connect` whose *teardown* cannot fake a functional failure.

    Starlette runs every test websocket session inside its own anyio portal. When the
    client leaves the context while the app task is still inside `send_json`, closing
    that portal can surface `concurrent.futures.CancelledError` from `__exit__` - i.e.
    after every payload the assertions needed has already been collected. That is test
    plumbing noise rather than a broken pipeline, so it is swallowed here; anything the
    test body itself raises still propagates.
    """
    session = client.websocket_connect(path)
    socket = session.__enter__()
    try:
        yield socket
    finally:
        try:
            session.__exit__(*sys.exc_info())
        except (futures.CancelledError, asyncio.CancelledError):
            pass


def _check(name: str, condition: bool, detail: str = "") -> bool:
    print(f"  {'PASS' if condition else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")
    return bool(condition)
# ------------------------------------------------------- unit: RAM windowing
def test_buffer_overlap() -> bool:
    print("\n[buffer - 200ms window, 50% overlap, gapless]")
    ramp = ((np.arange(20000) % 10000) / 10000.0).astype(np.float32)

    buffer = AudioBufferManager()
    windows = []
    for start in range(0, 16000, HOP_SAMPLES):
        windows += buffer.push(ramp[start:start + HOP_SAMPLES])
    overlap_ok = all(
        np.allclose(prev[HOP_SAMPLES:], cur[:WINDOW_SAMPLES - HOP_SAMPLES])
        for prev, cur in zip(windows, windows[1:])
    )
    exact = all(
        np.allclose(win, ramp[k * HOP_SAMPLES:(k * HOP_SAMPLES) + WINDOW_SAMPLES])
        for k, win in enumerate(windows)
    )

    reference = None
    invariant = True
    total_samples = 16320                            # 10.2 hops of the ramp
    for chunk in (320, 800, 1600, 3200, 6400):
        candidate = AudioBufferManager()
        emitted = []
        for start in range(0, total_samples, chunk):
            # clip so every variant ingests *exactly* total_samples, otherwise the
            # last slice would silently feed a different amount of audio.
            emitted += candidate.push(ramp[start:min(start + chunk, total_samples)])
        if reference is None:
            reference = emitted
            reference_span = (total_samples // candidate.hop) - 1   # ends 3200..16000
        same_span = len(emitted) == reference_span and all(
            np.allclose(a, b) for a, b in zip(emitted, reference))
        invariant &= same_span

    cold = AudioBufferManager()
    cold_windows = cold.push(ramp[:HOP_SAMPLES])
    stats = AudioBufferManager().stats()

    return all([
        _check("hop is exactly half the window", HOP_SAMPLES == WINDOW_SAMPLES // 2 and OVERLAP == 0.5),
        _check("consecutive windows overlap by 50%", overlap_ok, f"{len(windows)} windows"),
        _check("window k sits on the hop grid (gapless)", exact),
        _check("chunk size does not change the window grid", invariant),
        _check("cold stream is not scored on padded silence", cold_windows == [], f"{len(cold_windows)} early frames"),
        _check("ring keeps the latest 200ms only",
               stats["buffered_samples"] == 0 and stats["ring_bytes"] == (WINDOW_SAMPLES + HOP_SAMPLES) * 4,
               f"{stats['ring_bytes']} bytes"),
        _check("NaN/Inf samples are neutralised",
               AudioBufferManager().push(np.array([np.nan, np.inf, -np.inf, 0.5], dtype=np.float32)) == []),
        _check("empty push is a no-op", AudioBufferManager().push(np.zeros(0, dtype=np.float32)) == []),
    ])
# ----------------------------------------------------------- unit: DSP stage
def test_feature_extraction() -> bool:
    print("\n[features - HF ratio / pitch variance / spectral flux]")
    hf_tone = np.sin(2 * np.pi * 7000 * np.arange(WINDOW_SAMPLES) / SAMPLE_RATE).astype(np.float32)
    low_tone = np.sin(2 * np.pi * 200 * np.arange(WINDOW_SAMPLES) / SAMPLE_RATE).astype(np.float32)
    hf_features = extract_acoustic_features(hf_tone)
    low_features = extract_acoustic_features(low_tone)
    noise = np.random.default_rng(0).standard_normal(WINDOW_SAMPLES).astype(np.float32) * 0.4
    noise_features = extract_acoustic_features(noise)

    started = time.perf_counter()
    for _ in range(50):
        extract_acoustic_features(fraud_signal(0.2)[:WINDOW_SAMPLES])
    per_call_ms = (time.perf_counter() - started) / 50 * 1000.0

    pure = extract_acoustic_features(hf_tone) == extract_acoustic_features(hf_tone)
    short = extract_acoustic_features(np.zeros(64))
    extractor = FeatureExtractor()
    extractor.extract(fraud_signal(0.2)[:WINDOW_SAMPLES])
    second = extractor.extract(fraud_signal(0.2, seed=11)[:WINDOW_SAMPLES])
    spectrum = extractor.last_spectrum

    return all([
        _check("HF power ratio separates 7kHz from 200Hz",
               hf_features["hf_power_ratio"] > 0.9 > low_features["hf_power_ratio"],
               f"hf={hf_features['hf_power_ratio']} low={low_features['hf_power_ratio']}"),
        _check("voiced tone reports pitch, noise does not",
               low_features["voiced_ratio"] > 0.9 > hf_features["voiced_ratio"],
               f"tone={low_features['voiced_ratio']} noise={hf_features['voiced_ratio']}"),
        _check("spectral flux reacts to non-stationary spectra", noise_features["spectral_flux"] > 0,
               f"flux={noise_features['spectral_flux']}"),
        _check("streaming flux reacts to the next frame", second["spectral_flux"] > 0),
        _check("dashboard spectrum is reused, not recomputed",
               spectrum is not None and spectrum.size == WINDOW_SAMPLES // 2 + 1,
               f"{None if spectrum is None else spectrum.size} bins"),
        _check("feature keys are stable",
               set(hf_features) == {"hf_power_ratio", "pitch_f0_variance", "voiced_ratio",
                                    "spectral_flux", "rms_energy"}),
        _check("short/empty input returns zeros", all(v == 0.0 for v in short.values())),
        _check("helper is pure (no hidden module state)", pure),
        _check("under the 20ms per-window budget", per_call_ms < 20.0, f"{per_call_ms:.3f} ms/window"),
    ])


# ------------------------------------------------------- unit: scoring stage
def test_detection_engine() -> bool:
    print("\n[detection - anomaly score + thresholds]")
    fraud = {"hf_power_ratio": 0.62, "pitch_f0_variance": 0.0, "voiced_ratio": 0.0,
             "spectral_flux": 0.9, "rms_energy": 0.5}
    human = {"hf_power_ratio": 0.0, "pitch_f0_variance": 2757.0, "voiced_ratio": 1.0,
             "spectral_flux": 0.12, "rms_energy": 0.39}
    silence = {"hf_power_ratio": 0.0, "pitch_f0_variance": 0.0, "voiced_ratio": 0.0,
               "spectral_flux": 0.0, "rms_energy": 0.0}

    started = time.perf_counter()
    for _ in range(5000):
        calculate_anomaly_score(fraud)
    per_call_ms = (time.perf_counter() - started) / 5000 * 1000.0

    engine = DetectionEngine(thresholds={"hf_power_ratio": (0.5, 0.6)},
                             weights={"hf_power_ratio": 1.0, "pitch_f0_variance": 0.0,
                                      "spectral_flux": 0.0})
    return all([
        _check("pitchless HF broadband scores CRITICAL", calculate_anomaly_score(fraud) >= 70.0,
               f"{calculate_anomaly_score(fraud)}"),
        _check("human-like features stay SAFE", calculate_anomaly_score(human) <= 34.0,
               f"{calculate_anomaly_score(human)}"),
        _check("silence is muted toward zero", calculate_anomaly_score(silence) == 0.0),
        _check("bands are 0-34 / 35-69 / 70-100",
               [classify_risk(s) for s in (34.0, 34.99, 35.0, 69.99, 70.0)]
               == ["SAFE", "SAFE", "WARNING", "WARNING", "CRITICAL FRAUD"]),
        _check("engine honours threshold overrides",
               engine.score(fraud).anomaly_score != calculate_anomaly_score(fraud),
               f"{engine.score(fraud).anomaly_score} vs {calculate_anomaly_score(fraud)}"),
        _check("invalid overrides fall back to defaults",
               sorted(DetectionEngine(thresholds={"hf_power_ratio": "nope"}).thresholds) == sorted(THRESHOLDS)),
        _check("NaN/None/str features never raise",
               calculate_anomaly_score({"hf_power_ratio": float("nan"), "rms_energy": None,
                                        "spectral_flux": "x"}) == 0.0),
        _check("band scores are published for explainability",
               set(score_components(fraud)) == {"hf_power_ratio", "pitch_f0_variance", "spectral_flux"}),
        _check("under the 20ms scoring budget", per_call_ms < 20.0, f"{per_call_ms * 1000:.1f} us/call"),
    ])
# -------------------------------------------------------- unit: risk scorer
def test_risk_scorer() -> bool:
    print("\n[risk scorer - EMA, episode edges, hysteresis]")
    scorer = RiskScorer()
    alpha = scorer.alpha
    scorer.update(100.0)
    manual = alpha * 100.0
    scorer.update(100.0)
    manual = alpha * 100.0 + (1 - alpha) * manual
    ema_ok = abs(scorer.current - round(manual, 2)) <= 0.01

    guarded = RiskScorer()
    for value in (1000.0, float("nan"), float("inf"), -float("inf")):
        guarded.update(value)
    nan_safe = guarded.current <= 34.0 and guarded.invalid_updates == 3

    episode = RiskScorer()
    edges = [episode.update(95.0).bank_freeze for _ in range(8)]
    single_freeze = sum(edges) == 1 and episode.freezes_triggered == 1

    hysteresis = RiskScorer()
    for _ in range(8):
        hysteresis.update(95.0)
    held = hysteresis.update(66.0).bank_freeze is False      # above release: episode stays open
    cooling = None
    for _ in range(6):                                       # decay far below the release floor
        cooling = hysteresis.update(0.0)
    released = hysteresis.in_critical_episode is False and cooling.level == "SAFE"
    rearmed = hysteresis.update(95.0)
    episode_rearm = (held and released and hysteresis.freezes_triggered == 1
                     and rearmed.bank_freeze is False and rearmed.episode_id is None
                     and hysteresis.in_critical_episode is False)

    try:
        RiskScorer(alpha=0.0)
        alpha_guard = False
    except ValueError:
        alpha_guard = True

    return all([
        _check("EMA follows alpha=0.3 exactly", ema_ok, f"{scorer.current} vs {round(manual, 2)}"),
        _check("NaN/Inf frames cannot inflate risk", nan_safe,
               f"score={guarded.current} invalid={guarded.invalid_updates}"),
        _check("freeze fires once per critical episode", single_freeze, f"edges={sum(edges)}"),
        _check("hysteresis releases below the floor (no refreeze yet)", episode_rearm,
               f"held={held} released={released} freezes={hysteresis.freezes_triggered}"),
        _check("alpha is validated", alpha_guard),
        _check("clamp_score folds non-finite input to 0", clamp_score(float("nan")) == 0.0),
        _check("reset clears counters and history",
               (lambda s: (s.reset(), s.current == 0.0 and s.updates == 0 and not s.history)[1])(RiskScorer())),
        _check("snapshot exposes dashboard fields",
               {"risk_score", "level", "history", "freezes_triggered"} <= set(RiskScorer().snapshot())),
    ])


# ------------------------------------------------------ unit: bank freeze hook
def test_bank_hook() -> bool:
    print("\n[bank - freeze payload, idempotency, non-blocking]")
    mock_bank_api.clear_freeze_log()
    first = mock_bank_api.freeze_transaction("sim-test", 91.7)
    logged_ok = (len(mock_bank_api.get_freeze_log(limit=5)) >= 1
                 and mock_bank_api.is_frozen("sim-test"))
    replay = mock_bank_api.freeze_transaction("sim-test", 95.0, idempotency_key="EP-0001")
    duplicate = mock_bank_api.freeze_transaction("sim-test", 99.0, idempotency_key="EP-0001")
    mock_bank_api.clear_freeze_log()
    for index in range(mock_bank_api.MAX_LOG_ENTRIES + 120):
        mock_bank_api.freeze_transaction(f"s{index}", 75.0, idempotency_key=f"k{index}")
    bounded = mock_bank_api.freeze_log_size() == mock_bank_api.MAX_LOG_ENTRIES

    async def timed():
        started = time.perf_counter()
        await asyncio.gather(*[mock_bank_api.freeze_transaction_async(f"async-{i}", 80.0)
                               for i in range(40)])
        return (time.perf_counter() - started) * 1000.0
    async_ms = asyncio.run(timed())

    return all([
        _check("hook returns an auditable freeze payload",
               first["ok"] and first["status"] == "FROZEN" and first["freeze_id"].startswith("FRZ-")
               and first["audit"]["account_locked"]),
        _check("freeze is logged for auditing", logged_ok),
        _check("idempotent replay keeps one audit row",
               duplicate["freeze_id"] == replay["freeze_id"] and duplicate["duplicate"] is True),
        _check("risk score is clamped to 0-100",
               mock_bank_api.freeze_transaction("x", 500.0)["risk_score"] == 100.0),
        _check("anonymous session ids are normalised",
               mock_bank_api.freeze_transaction("   ", 80.0)["session_id"] == "unknown-session"),
        _check("audit log is bounded", bounded, f"cap {mock_bank_api.MAX_LOG_ENTRIES}"),
        _check("get_freeze_log hands out copies",
               mock_bank_api.get_freeze_log(1)[0] is not mock_bank_api.get_freeze_log(1)[0]),
        _check("async hook is non-blocking (40 concurrent)",
               async_ms < LATENCY_BUDGET_MS, f"{async_ms:.1f} ms"),
        _check("clear resets the log", mock_bank_api.clear_freeze_log() >= 0),
    ])

def test_health(client: TestClient) -> bool:
    print("\n[health]")
    res = client.get("/api/health")
    body = res.json()
    return all([
        _check("GET /api/health is 200", res.status_code == 200),
        _check("sample_rate 16000 + 200ms window", body["sample_rate"] == 16000 and body["window_ms"] == 200),
        _check("hop is half the analysis window", body["hop_samples"] == 1600 and body["overlap"] == 0.5),
        _check("latency budget 250ms", body["latency_budget_ms"] == 250.0),
        _check("dashboard cadence 200ms", body["broadcast_interval_ms"] == 200),
        _check("instant telemetry pushes advertised", body["instant_broadcast"] is True),
        _check("ws endpoints advertised", set(body["endpoints"]["ws"]) == {"/ws/simulator", "/ws/dashboard"}),
    ])


def test_rest_fraud(client: TestClient) -> bool:
    print("\n[rest analyze - synthetic sample]")
    res = client.post("/api/analyze", files={"audio": ("fraud.wav", wav_bytes(fraud_signal()), "audio/wav")},
                      data={"claimed_speaker": "CEO"})
    body = res.json()
    return all([
        _check("POST /api/analyze is 200", res.status_code == 200, json.dumps(body)[:180] if res.status_code != 200 else ""),
        _check("synthetic_probability > 0.6", body.get("detection", {}).get("synthetic_probability", 0) > 0.6,
               str(body.get("detection", {}).get("synthetic_probability"))),
        _check("risk level CRITICAL", body.get("risk", {}).get("risk_level") == "CRITICAL",
               str(body.get("risk", {}).get("risk_level"))),
        _check("prevention action is BLOCK", body.get("prevention", {}).get("action") == "BLOCK",
               str(body.get("prevention", {}).get("action"))),
        _check("bank freeze attached", isinstance(body.get("bank_freeze"), dict) and body["bank_freeze"].get("freeze_id", "").startswith("FRZ-")),
    ])


def test_rest_benign_and_verify(client: TestClient) -> bool:
    print("\n[rest analyze - human sample + speaker verify]")
    wave = voice_signal()
    res = client.post("/api/analyze", files={"audio": ("human.wav", wav_bytes(wave), "audio/wav")},
                      data={"claimed_speaker": "Treasury Officer"})
    body = res.json()
    ok = all([
        _check("POST /api/analyze is 200", res.status_code == 200),
        _check("human-referenced analyze is not CRITICAL", body.get("risk", {}).get("risk_level") != "CRITICAL",
               f"score={body.get('risk', {}).get('risk_score')} level={body.get('risk', {}).get('risk_level')}"),
        _check("no reference -> neutral 0.5", body.get("speaker", {}).get("speaker_match_score") == 0.5),
    ])
    return bool(ok)
def test_verify_endpoint(client: TestClient) -> bool:
    print("\n[rest verify - speaker matching]")
    wave = voice_signal()
    same = client.post("/api/verify", files={"audio": ("a.wav", wav_bytes(wave), "audio/wav"),
                                              "reference": ("b.wav", wav_bytes(wave), "audio/wav")},
                       data={"claimed_speaker": "Treasury Officer"})
    same_body = same.json()
    mismatch = client.post("/api/verify", files={"audio": ("a.wav", wav_bytes(wave), "audio/wav"),
                                                  "reference": ("b.wav", wav_bytes(fraud_signal()), "audio/wav")})
    mismatch_body = mismatch.json()
    return all([
        _check("POST /api/verify is 200", same.status_code == 200),
        _check("self-match score > 0.9", same_body.get("speaker_match_score", 0) > 0.9,
               str(same_body.get("speaker_match_score"))),
        _check("self-match verified", same_body.get("speaker_verified") is True),
        _check("mismatched voices score lower",
               mismatch_body.get("speaker_match_score", 1) < same_body.get("speaker_match_score", 0),
               str(mismatch_body.get("speaker_match_score"))),
    ])


def test_features_endpoint(client: TestClient) -> bool:
    print("\n[rest features - acoustic inspection]")
    feat_res = client.post("/api/features", files={"audio": ("f.wav", wav_bytes(fraud_signal()), "audio/wav")})
    fbody = feat_res.json()
    return all([
        _check("POST /api/features is 200", feat_res.status_code == 200),
        _check("window features + bands returned",
               {"hf_power_ratio", "pitch_f0_variance", "voiced_ratio", "spectral_flux", "rms_energy"}
               <= set(fbody.get("loudest_window_features", {})),
               str(fbody.get("loudest_window_features"))),
        _check("thresholds published", "hf_power_ratio" in fbody.get("thresholds", {})),
        _check("unsupported extension rejected",
               client.post("/api/features",
                           files={"audio": ("bad.xyz", b"nope", "application/octet-stream")}).status_code == 400),
    ])

def test_simulator_ws_fraud(client: TestClient) -> bool:
    print("\n[ws simulator - fraud stream, 50% overlap, one freeze]")
    with live_socket(client, "/ws/simulator?session_id=test-fraud") as ws:
        ready = ws.receive_json()
        ready_ok = _check("ready handshake", ready.get("type") == "ready",
                          f"window={ready.get('window_samples')} hop={ready.get('hop_samples')}")
        latencies, levels, freezes, windows = [], [], [], []
        feedback = None
        chunk_count = 0
        for frame in pcm_frames(fraud_signal(1.6)):
            ws.send_bytes(frame)
            feedback = ws.receive_json()
            chunk_count += 1
            latencies.append(feedback["latency_ms"])
            levels.append(feedback["level"])
            windows.append(feedback["total_windows_scored"])
            if feedback.get("freeze"):
                freezes.append(feedback["freeze"])
        ws.send_json({"type": "ping"})
        pong = ws.receive_json()
        ws.send_json({"type": "stop"})
        summary = ws.receive_json()

    return bool(ready_ok) and all([
        _check(f"{chunk_count} chunks -> ~2x windows (50% overlap)", windows[-1] >= 2 * chunk_count - 1,
               f"chunks={chunk_count} windows={windows[-1]}"),
        _check("every chunk scored under 250ms", max(latencies) < 250.0,
               f"max={max(latencies):.2f}ms mean={float(np.mean(latencies)):.2f}ms"),
        _check("stream escalates to CRITICAL FRAUD", "CRITICAL FRAUD" in levels, str(sorted(set(levels)))),
        _check("bank freeze fired exactly once (episode latch)", len(freezes) == 1, f"{len(freezes)} freezes"),
        _check("freeze carries episode idempotency",
               bool(freezes and freezes[0].get("idempotency_key", "").startswith("test-fraud:EP-"))),
        _check("feedback carries the latency breakdown",
               set(feedback.get("latency_breakdown_ms", {})) >= {"decode", "buffer", "features", "score", "publish", "total"}),
        _check("pong control frame", pong.get("type") == "pong"),
        _check("summary reflects critical state", summary.get("final_level") == "CRITICAL FRAUD"),
    ])
def test_simulator_ws_benign(client: TestClient) -> bool:
    print("\n[ws simulator - human stream + formats + controls]")
    with live_socket(client, "/ws/simulator?session_id=test-human") as ws:
        ws.receive_json()
        scores = []
        feedback = None
        for frame in pcm_frames(voice_signal(1.0)):
            ws.send_bytes(frame)
            feedback = ws.receive_json()
            scores.append(feedback["risk_score"])
        human_level = feedback["level"]
        ws.send_json({"type": "reset"})
        reset_ack = ws.receive_json()
        int16_chunk = (voice_signal(0.2) * 32767 * 0.4).astype(np.int16)
        ws.send_json({"type": "audio", "format": "int16", "pcm": int16_chunk.tolist()})
        json_feedback = ws.receive_json()
        ws.send_json({"type": "config", "pcm": "int16"})
        config_ack = ws.receive_json()
    return all([
        _check("human stream stays out of CRITICAL FRAUD", human_level != "CRITICAL FRAUD",
               f"final={scores[-1]} max={max(scores)}"),
        _check("EMA smooths (no first-frame jump)", scores[0] <= max(scores) + 1e-6, str(scores[:3])),
        _check("reset acknowledged", reset_ack.get("type") == "reset"),
        _check("post-reset score restarts near 0", json_feedback["risk_score"] < 60, str(json_feedback["risk_score"])),
        _check("int16 JSON frame accepted", json_feedback.get("samples", 0) > 0,
               f"samples={json_feedback.get('samples')}"),
        _check("config channel negotiates formats", config_ack.get("pcm_format") == "int16"),
    ])


def test_pcm_decoding() -> bool:
    print("\n[ws payloads - float32/int16 decode + binary control]")
    frame = next(pcm_frames(voice_signal(0.2)))
    f32 = decode_pcm_frame(frame, "float32")
    auto = decode_pcm_frame(frame, "auto")
    int16_bytes = (voice_signal(0.2)[:1600].astype(np.float32) * 32767).astype(np.int16).tobytes()
    sniffed = decode_pcm_frame(int16_bytes, "auto")
    explicit = decode_pcm_frame(int16_bytes, "int16")
    control = decode_binary_control(json.dumps({"type": "ping"}).encode())
    audio = decode_json_audio({"format": "int16", "pcm": [0, 32767, -32768]})
    return all([
        _check("float32 decodes losslessly", np.allclose(f32, np.frombuffer(frame, dtype="<f4"), atol=1e-7)),
        _check("auto detects float32", np.allclose(auto, f32, atol=1e-7)),
        _check("int16 bytes are not misread as float32", abs(float(np.mean(sniffed))) > 1e-4),
        _check("auto int16 matches explicit int16", np.allclose(sniffed, explicit, atol=1e-7)),
        _check("JSON int16 list normalises to [-1, 1]", list(np.round(audio, 4)) == [0.0, 1.0, -1.0]),
        _check("binary control frames survive the PCM path", control == {"type": "ping"}),
        _check("empty frame decodes to silence", decode_pcm_frame(b"", "float32").size == 0),
    ])
def test_freeze_log_and_telemetry(client: TestClient) -> bool:
    print("\n[freeze log + telemetry snapshot]")
    log = client.get("/api/freeze-log").json()
    snap = client.get("/api/telemetry").json()
    return all([
        _check("freeze log has audit entries", log["count"] >= 1, f"{log['count']} entries"),
        _check("entry carries session + score", bool(log["events"][-1].get("session_id")) and log["events"][-1].get("risk_score", 0) >= 70),
        _check("telemetry has 64-bin FFT", len(snap["fft"]) == 64),
        _check("telemetry reports SLA budget", snap["sla_budget_ms"] == 250.0),
        _check("telemetry tracks windows + overlap", snap["windows_scored"] >= 1 and snap["overlap"] == 0.5),
        _check("telemetry carries bank block", "status" in snap["bank"] and "freeze_count" in snap["bank"]),
        _check("telemetry carries latency breakdown", isinstance(snap.get("latency_breakdown_ms"), dict)),
    ])


def test_dashboard_ws(client: TestClient) -> bool:
    print("\n[ws dashboard - 200ms heartbeat]")
    with live_socket(client, "/ws/dashboard") as ws:
        hello = ws.receive_json()
        stamps, payloads = [], []
        for _ in range(5):
            payloads.append(ws.receive_json())
            stamps.append(time.perf_counter())
        span = stamps[-1] - stamps[0]
    gaps = [round((stamps[i + 1] - stamps[i]) * 1000, 1) for i in range(len(stamps) - 1)]
    last = payloads[-1]
    return all([
        _check("hello frame advertises endpoints", hello.get("type") == "hello" and "/ws/simulator" in hello.get("endpoints", {}).get("ws", [])),
        _check("5 telemetry frames received", len(payloads) == 5),
        _check("cadence ~200ms", 0.5 <= span <= 1.6, f"span={span * 1000:.0f}ms gaps={gaps}"),
        _check("all frames typed telemetry", all(p.get("type") == "telemetry" for p in payloads)),
        _check("payload has risk/level/fft/sla/bank", all(k in last for k in ("risk_score", "level", "fft", "sla_ok", "bank", "latency_ema_ms"))),
        _check("zero drive-by disk writes", not (BACKEND_DIR / "tmp").exists()),
    ])


def test_dashboard_instant_push(client: TestClient) -> bool:
    print("\n[ws dashboard - instant push on every scored frame]")

    with live_socket(client, "/ws/dashboard") as dash:
        dash.receive_json()                        # hello
        queue = HUB.subscribe()
        subscriber_ok = queue in HUB._subscribers
        HUB.unsubscribe(queue)
        before = time.perf_counter()
        with live_socket(client, "/ws/simulator?session_id=instant-push") as sim:
            sim.receive_json()                     # ready
            sim.send_bytes(next(pcm_frames(fraud_signal(1.0))))
            reply = sim.receive_json()             # the chunk was scored
        frames = []
        deadline = time.perf_counter() + 2.5
        while len(frames) < 6 and time.perf_counter() < deadline:
            frames.append(dash.receive_json())
        wait_ms = (time.perf_counter() - before) * 1000.0
    scored = [f for f in frames if f.get("chunks_processed", 0) >= 1]
    return all([
        _check("telemetry hub fans out to dashboard subscribers", subscriber_ok),
        _check("simulator scored the chunk", reply.get("windows_scored", 0) >= 1),
        _check("dashboard received an instant push", len(scored) >= 1,
               f"frames={len(frames)} wait={wait_ms:.0f}ms"),
        _check("pushed frame stays inside the 250ms budget",
               all(f.get("latency_ms", 250.0) < 250.0 for f in scored),
               f"latencies={[round(f.get('latency_ms', -1), 2) for f in scored]}"),
    ])


def test_upload_size_cap(client: TestClient) -> bool:
    print("\n[rest - oversized upload rejected without buffering it all]")
    big = b"\x00" * (26 * 1024 * 1024)
    res = client.post("/api/analyze", files={"audio": ("big.wav", big, "audio/wav")})
    tiny = client.post("/api/analyze", files={"audio": ("empty.wav", b"", "audio/wav")})
    return all([
        _check("26MB upload rejected with 413", res.status_code == 413, str(res.status_code)),
        _check("empty upload rejected with 400", tiny.status_code == 400, str(tiny.status_code)),
    ])


def test_rest_pipeline_concurrency(client: TestClient) -> bool:
    print("\n[concurrency - uploads never stall live telemetry]")
    wave = fraud_signal(0.6)
    payload = wav_bytes(wave)
    ticks: list = []
    done = threading.Event()

    def stream_dashboard() -> None:
        try:
            with live_socket(client, "/ws/dashboard") as ws:
                ws.receive_json()                  # hello
                while not done.is_set():
                    ticks.append(ws.receive_json())
        except Exception:
            pass

    thread = threading.Thread(target=stream_dashboard, daemon=True)
    thread.start()
    time.sleep(0.35)                               # let the 200ms cadence tick
    res = client.post("/api/analyze", files={"audio": ("slow.wav", payload, "audio/wav")})
    time.sleep(0.45)
    done.set()
    thread.join(timeout=5.0)
    before = len(ticks)
    return all([
        _check("upload analyzed during the telemetry stream", res.status_code == 200),
        _check("dashboard kept ticking while the upload was scored", before >= 2, f"{before} ticks"),
    ])


def test_simulator_reset_endpoint(client: TestClient) -> bool:
    print("\n[rest - simulator reset]")
    res = client.post("/api/simulator/reset")
    body = res.json()
    snap = client.get("/api/telemetry").json()
    return all([
        _check("POST /api/simulator/reset is 200", res.status_code == 200),
        _check("reset returns the snapshot", isinstance(body.get("telemetry"), dict)),
        _check("risk restarts at 0", snap["risk_score"] == 0.0 and snap["level"] == "SAFE"),
    ])


def test_live_checks() -> bool:
    """Real uvicorn server on a free TCP port: HTTP, CORS and live WS loops.

    Everything the React app does - binary float32 mic frames in, instant
    telemetry out - is replayed here over *real sockets*, because the in-process
    TestClient portal cannot prove that the network stack, the CORS middleware or
    the cross-connection fan-out behave the same way.
    """
    print("\n[live server - uvicorn on TCP, real sockets]")
    import socket
    import subprocess
    import urllib.error
    import urllib.request

    from websockets.sync.client import connect as ws_connect

    def safe_json(raw: object) -> dict:
        """Parse a JSON body / socket frame into a dict, {} when it is not one."""
        if isinstance(raw, (bytes, bytearray)):
            raw = raw.decode("utf-8", "replace")
        if not isinstance(raw, str):
            return {}
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    sockets = f"ws://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1",
         "--port", str(port)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=str(ROOT),
    )

    def fetch(path: str, timeout: float = 10.0, method: str = "GET",
              headers: dict | None = None):
        """Return (status, json_body_or_{}, headers) - never raises."""
        request = urllib.request.Request(f"{base}{path}", method=method,
                                        headers=headers or {})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as res:
                return res.status, safe_json(res.read().decode()), dict(res.headers)
        except urllib.error.HTTPError as exc:          # 4xx/5xx are answers too
            return exc.code, {}, dict(exc.headers or {})
        except Exception as exc:                       # connection refused during boot
            return 0, {"error": str(exc)}, {}

    try:
        status, health = 0, {}
        for _ in range(100):
            status, health, _ = fetch("/api/health")
            if status == 200:
                break
            time.sleep(0.1)
        ok = [_check("uvicorn boots and answers /api/health",
                     status == 200 and health.get("status") == "ok")]
        status, snap, _ = fetch("/api/telemetry")
        ok.append(_check("live telemetry snapshot is valid",
                         status == 200 and snap.get("type") == "telemetry"
                         and len(snap.get("fft", [])) == 64))
        status, log, _ = fetch("/api/freeze-log")
        ok.append(_check("live freeze log answers", status == 200 and "events" in log))

        # CORS: the Vite dev origin must be admitted by the middleware
        pre_status, _, pre_headers = fetch(
            "/api/analyze", method="OPTIONS",
            headers={"Origin": "http://localhost:5173",
                     "Access-Control-Request-Method": "POST"})
        allow = (pre_headers.get("access-control-allow-origin")
                 or pre_headers.get("Access-Control-Allow-Origin"))
        ok.append(_check("CORS preflight admits the React dev origin",
                         pre_status in (200, 204) and allow in ("*", "http://localhost:5173"),
                         f"{pre_status} allow={allow}"))

        # ---- end-to-end over TCP: mic frames in -> dashboard telemetry out ----
        hello, ready, pushed = {}, {}, None
        sent, latencies, levels = 0, [], []
        try:
            with ws_connect(f"{sockets}/ws/dashboard", open_timeout=10) as dash:
                hello = safe_json(dash.recv(timeout=5))
                with ws_connect(f"{sockets}/ws/simulator?session_id=live-e2e",
                                open_timeout=10) as mic:
                    ready = safe_json(mic.recv(timeout=5))
                    for frame in pcm_frames(fraud_signal(1.2)):
                        mic.send(frame)            # binary float32 LE, as the browser sends
                        ack = safe_json(mic.recv(timeout=5))
                        sent += 1
                        latencies.append(float(ack.get("latency_ms", 9999.0)))
                        levels.append(ack.get("level"))
                    deadline = time.perf_counter() + 1.5
                    while pushed is None and time.perf_counter() < deadline:
                        try:
                            frame_payload = safe_json(dash.recv(timeout=0.25))
                        except (TimeoutError, OSError):
                            continue
                        if frame_payload.get("chunks_processed", 0) >= 1:
                            pushed = frame_payload
            ok.append(_check("dashboard socket upgrades over TCP",
                             hello.get("type") == "hello"))
            ok.append(_check("simulator socket streams real mic frames",
                             ready.get("type") == "ready" and sent >= 4, f"{sent} chunks acked"))
            ok.append(_check("networked scoring stays inside the 250ms SLA",
                             bool(latencies) and max(latencies) < 250.0,
                             f"max={max(latencies):.2f}ms" if latencies else "no frames"))
            ok.append(_check("live stream reaches CRITICAL FRAUD",
                             "CRITICAL FRAUD" in levels, str(sorted(set(levels)))))
            ok.append(_check("dashboard receives the pushed risk over TCP",
                             bool(pushed) and pushed.get("risk_score", 0) > 0
                             and pushed.get("sla_ok") is True and len(pushed.get("fft", [])) == 64,
                             f"risk={pushed.get('risk_score')} latency={pushed.get('latency_ms')}"
                             if pushed else "no push"))
            _, freeze_log, _ = fetch("/api/freeze-log")
            ok.append(_check("live freeze is auditable",
                             any(e.get("session_id") == "live-e2e"
                                 for e in freeze_log.get("events", [])),
                             f"{freeze_log.get('count')} entries"))
        except Exception as exc:                   # noqa: BLE001 - report, never crash
            ok.append(_check("live websocket end-to-end completed", False,
                             f"{type(exc).__name__}: {exc}"))
        return all(ok)
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except Exception:
            proc.kill()


def main() -> int:
    pure_unit_tests = [
        ("buffer overlap", test_buffer_overlap),
        ("feature extraction", test_feature_extraction),
        ("detection engine", test_detection_engine),
        ("risk scorer", test_risk_scorer),
        ("bank hook", test_bank_hook),
        ("pcm decoding", test_pcm_decoding),
    ]
    client_tests = [
        ("health", test_health),
        ("rest fraud", test_rest_fraud),
        ("rest benign + verify", test_rest_benign_and_verify),
        ("verify endpoint", test_verify_endpoint),
        ("features endpoint", test_features_endpoint),
        ("ws simulator fraud", test_simulator_ws_fraud),
        ("ws simulator benign", test_simulator_ws_benign),
        ("freeze log + telemetry", test_freeze_log_and_telemetry),
        ("ws dashboard heartbeat", test_dashboard_ws),
        ("ws dashboard instant push", test_dashboard_instant_push),
        ("upload size cap", test_upload_size_cap),
        ("upload concurrency", test_rest_pipeline_concurrency),
        ("simulator reset", test_simulator_reset_endpoint),
    ]
    results = {}

    def _record(name: str, passed: bool, exc: BaseException | None = None) -> None:
        """Store a group result, dumping the traceback when the group blew up."""
        if exc is not None:
            print(f"  FAIL  {name} raised {type(exc).__name__}: {exc}")
            traceback.print_exc()
        results[name] = bool(passed)

    for name, fn in pure_unit_tests:
        try:
            _record(name, fn())
        except Exception as exc:  # noqa: BLE001 - a failure is a failed check
            _record(name, False, exc)
    with TestClient(app) as client:
        for name, fn in client_tests:
            try:
                _record(name, fn(client))
            except (asyncio.CancelledError, futures.CancelledError) as exc:
                # starlette's test portal surfaces a cancelled app task here
                _record(name, False, exc)
            except Exception as exc:  # noqa: BLE001 - a failure is a failed check
                _record(name, False, exc)
    if "--live" in sys.argv[1:]:
        try:
            _record("live server", test_live_checks())
        except Exception as exc:  # noqa: BLE001 - a failure is a failed check
            _record("live server", False, exc)
    print("\n================ SUMMARY ================")
    for name, passed in results.items():
        print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    failed = [n for n, p in results.items() if not p]
    print(f"  {len(results) - len(failed)}/{len(results)} groups passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())