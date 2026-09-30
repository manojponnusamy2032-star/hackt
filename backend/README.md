# VoiceGuard backend - SIH26104

Real-time voice-fraud detection service: **FastAPI + WebSockets** for streaming,
NumPy/SciPy for all DSP, **zero disk I/O** on the live path.

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000     # REST + WS
python backend/test_backend.py                    # 19 in-process groups
python backend/test_backend.py --live             # + real-socket uvicorn E2E
```

The suite boots a real `uvicorn` process for `--live` and talks to it over TCP:
health/telemetry/freeze-log, a CORS preflight for the Vite origin, a float32 mic
stream on `/ws/simulator` while `/ws/dashboard` is listened to on another socket,
and the resulting audit row. Every group also asserts the SLA (`latency_ms`
arrival -> publish) stays under 250 ms.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | Service/model/SLA metadata (also `GET /`) |
| POST | `/api/analyze` | File analysis: `audio`, optional `reference`, `claimed_speaker` |
| POST | `/api/verify` | Speaker verification (MFCC cosine) |
| POST | `/api/features` | Raw acoustic features + band scores of the loudest 200ms window |
| GET | `/api/telemetry` | Latest dashboard snapshot |
| GET | `/api/freeze-log` | Audit trail of bank freezes |
| POST | `/api/simulator/reset` | Clear the shared telemetry snapshot |
| WS | `/ws/simulator` | Browser/mic PCM in, per-chunk feedback out |
| WS | `/ws/dashboard` | Telemetry pushed instantly per scored frame + 200ms heartbeat |

### `/ws/simulator` protocol

Send (any mix):
* **binary** `Float32` little-endian PCM frames, mono, ideally 16 kHz
  (`?sample_rate=8000|16000|22050|44100|48000`, `?pcm=float32|int16|auto`,
  `?overlap=0..0.9`, int16 auto-detected per frame)
* `{"type":"audio","pcm":[...]}` (float list, or int16 list / base64 with `"format"`)
* a binary JSON frame (`{"type":"audio"|...}` encoded as UTF-8 bytes) works too
* `{"type":"reset"}` | `{"type":"stop"}` | `{"type":"ping"}` | `{"type":"config",
  "sample_rate":16000, "overlap":0.5, "pcm":"auto"}`

Receive:
* `{"type":"ready", session_id, sample_rate, window_samples, hop_samples,
  overlap, latency_budget_ms, pcm_format, ...}` on connect
* `{"type":"feedback", chunk_index, windows_scored, window_ready, features,
  band_scores, raw_score, risk_score, level, critical, episode_id,
  bank_freeze, freeze, latency_ms, latency_breakdown_ms, sla_ok}` per chunk
* `{"type":"pong"}` / `{"type":"summary"}` / `{"type":"error"}` for control frames

### `/ws/dashboard` payload (instant push + 200ms heartbeat)

`{risk_score, raw_score, level, features, band_scores, fft[64], latency_ms,
latency_ema_ms, latency_max_ms, latency_breakdown_ms, sla_budget_ms, sla_ok,
chunks_processed, windows_scored, critical_events, window_fill, hop_samples,
overlap, bank:{status, freeze_count, last_freeze}, source}`

## Pipeline (RAM only)

```
Arrival-timestamped PCM frames -> AudioBufferManager (200ms/3200-sample float32
ring `capacity + hop`; hop-aligned emission = 50% overlap, gapless for any
browser chunk size) -> FeatureExtractor (one FFT/frame: HF power ratio,
low-passed autocorrelation F0 variance + voiced ratio, spectral flux, RMS)
-> DetectionEngine (weighted bands HF .40 / pitch .35 / flux .25 + voicing and
pitchless-HF rules) -> RiskScorer (EMA alpha=0.3; SAFE 0-34, WARNING 35-69,
CRITICAL FRAUD 70-100; freeze fires on the rising edge, hysteresis release)
-> mock_bank_api.freeze_transaction() (idempotent FRZ-... audit row) +
TelemetryHub fan-out to /ws/dashboard (instant push + 200ms heartbeat)
```

* Files uploaded to `/api/analyze` are decoded in memory (`soundfile`, falling back to
  an `ffmpeg` stdin/stdout pipe) - no temp files are created. The 25 MB cap is
  enforced while the body streams in, and all DSP/AASIST work runs in a worker
  thread so live WebSocket telemetry never stalls.
* Every chunk must score in **<250ms**; each feedback frame carries the measured
  `arrival -> decoded -> scored -> published` latency and its per-stage breakdown
  (observed ~1-4ms on CPU, dominated by the pitch autocorrelation).
* `/api/analyze` additionally fuses the optional AASIST neural detector
  (0.75 weight) when its checkpoint is loadable; the streaming path stays DSP-only
  so the 250ms budget holds.

## Files

* `audio_processor.py` - buffer + feature extraction
* `detection_engine.py` - anomaly bands/weights
* `risk_scorer.py` - EMA smoothing + risk classification
* `mock_bank_api.py` - mock freeze hook + audit log
* `main.py` - FastAPI app (REST + both WebSockets)
* `test_backend.py` - end-to-end assertions (REST, WS, SLA, freeze, dashboard)
* `app.py` - legacy Flask monolith, superseded, kept for reference
