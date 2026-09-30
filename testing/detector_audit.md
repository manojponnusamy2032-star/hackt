# VoiceGuard Detector Audit

Audit date: 2026-09-30

## Active Paths

- The React dashboard calls `POST /api/analyze` on `backend.main:app`.
- `backend.main` lazily loads one `deepfake_detection.AASIST.AASISTDetector` at FastAPI startup and retains it in a module-level cache. The active environment has CUDA unavailable; one-window CPU inference measured 278-384 ms in a local runtime check.
- The upload detector uses `models/deepfake/AASIST.pth`. The checkpoint is a 1.2 MB `OrderedDict` with 229 tensors and no embedded dataset, label-map, calibration, or model-version metadata. The repository history records that the file was added, but not its upstream provenance.
- The code assumes AASIST class 0 means spoof. That convention matches the official AASIST ASVspoof 2019 loader, which maps bona-fide to class 1 and spoof to class 0. This verifies the convention, not the provenance or training of this particular checkpoint.
- Official AASIST code is MIT-licensed and its published experiment uses ASVspoof 2019 LA. Published benchmark results do not establish this local checkpoint's performance.

## Upload Preprocessing and Inference

- `read_upload` decodes with SoundFile and falls back to ffmpeg, downmixes stereo by arithmetic mean, resamples to 16 kHz, replaces non-finite values, and peak-normalizes. It does not remove DC offset, estimate speech activity, or assess clipping/noise/silence quality.
- Uploads shorter than 0.25 seconds are rejected. Other clips are sent to AASIST as mono float32 at 16 kHz with exactly 64,600 samples (4.0375 seconds); short inputs are zero-padded and long inputs are truncated to their first 4.0375 seconds.
- Verified truncation defect: two 10-second signals with the same first 4.0375 seconds but different tails returned identical AASIST scores (`0.99999988`).
- `build_detection` currently blends AASIST softmax output (75%) with an acoustic heuristic score (25%). Acoustic features are computed over 200 ms windows at a 100 ms hop, averaged for up to 200 frames. The acoustic path uses handcrafted HF-energy, pitch/voicing, and spectral-flux rules.
- Softmax output is exposed as `synthetic_probability`; no calibration is present. `model_confidence` is just `max(p, 1-p)`, not a validated confidence estimate. The 75/25 fusion is not dataset-calibrated.

## Streaming, Speaker, and Risk

- The WebSocket stream uses 200 ms audio windows with 50% overlap (100 ms hop). It scores handcrafted acoustic features only; it does not call AASIST. Risk is EMA-smoothed at alpha 0.3, but a single crossing into the critical band can trigger the freeze action.
- AASIST's measured CPU inference time exceeds the 200 ms update cadence, so synchronously adding it to each transport update would block the stream. Any live AASIST integration needs a rolling context, bounded asynchronous inference, and measured queue/latency behavior.
- Active speaker verification is a handcrafted MFCC mean/std cosine embedding, not the unexecuted `resemblyzer` notebook experiment. With no reference audio, the API returns a neutral 0.5 match. The risk layer combines spoof score and speaker mismatch with fixed 0.6/0.4 weights; these weights have not been validated.

## Evaluation Evidence and Gaps

- No ASVspoof audio, keys, speaker-disjoint split, or other labeled dataset is present in the repository. No model training or probability calibration artifacts are present.
- `backend/test_backend.py` passes 19 groups, but its synthetic and human-like signals are procedurally generated. It checks a synthetic score above 0.6 and that one harmonic test is not CRITICAL; it does not calculate accuracy, FPR/FNR, ROC-AUC, or EER and does not validate real speech generalization.
- `testing/test_report.md` contains one manually reported human case; remaining cases and all aggregate metrics are blank. The speaker-verification notebooks are unexecuted and contain local Windows paths; their RMS VAD/noise-reduction cells are not used by the active API.
- Therefore no defensible real-world accuracy claim or calibrated threshold can be reported until a labeled, speaker-disjoint evaluation set is configured.

## Improvement Priorities

1. Score overlapping AASIST windows across the full upload, aggregate recent window scores robustly, and preserve per-window raw scores and measured inference latency.
2. Add a quality assessment that can return insufficient-quality/unavailable rather than treating low-quality input as bona-fide or spoof.
3. Keep model output, acoustic features, speaker match, quality, and fused risk as separate fields; label softmax as an uncalibrated model score until calibration data exists.
4. Add a reproducible manifest-driven evaluator for accuracy, precision/recall/F1, ROC-AUC, FPR/FNR, and EER. Print “Evaluation dataset not configured” when no labeled manifest is supplied; do not fabricate benchmark results.
5. Do not run AASIST in the live path at the 200 ms cadence until a bounded asynchronous rolling-window design is benchmarked on the supported CPU/GPU targets.