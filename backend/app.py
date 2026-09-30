"""VoiceGuard Flask API - LEGACY / SUPERSEDED.

Frozen reference implementation of the original monolithic pipeline. The live
backend is now FastAPI + WebSockets in `backend/main.py`:

    uvicorn backend.main:app --reload --port 8000

`main.py` serves the same REST routes (/api/health, /api/analyze, /api/verify)
and adds /api/features, /api/telemetry, /api/freeze-log, /ws/simulator and
/ws/dashboard. Keep this file only for reference/diffing; `run.sh` no longer
starts it.
"""
import os, sys, tempfile, traceback
from pathlib import Path
import numpy as np
import soundfile as sf
from flask import Flask, jsonify, request
from flask_cors import CORS

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from risk_engine.prevention import take_action
from risk_engine.risk_engine import calculate_risk

_detector = None
_detector_error = None

def get_detector():
    global _detector, _detector_error
    if _detector is not None:
        return _detector
    if _detector_error is not None:
        return None
    try:
        from deepfake_detection.AASIST import AASISTDetector
        _detector = AASISTDetector()
    except Exception as exc:
        _detector_error = f"{type(exc).__name__}: {exc}"
        _detector = None
    return _detector

TARGET_SR = 16000
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}

def load_mono_16k(raw_bytes, filename_hint="upload"):
    suffix = Path(filename_hint).suffix.lower() or ".wav"
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        tmp.write(bytes(raw_bytes)); tmp.close()
        src = tmp.name
        try:
            import librosa
            y, _ = librosa.load(src, sr=TARGET_SR, mono=True)
            return np.asarray(y, dtype=np.float32)
        except Exception:
            y, sr = sf.read(src, dtype="float32")
            if getattr(y, "ndim", 1) > 1:
                y = np.mean(y, axis=1)
            if sr != TARGET_SR:
                from scipy.signal import resample_poly
                from math import gcd
                g = gcd(int(sr), TARGET_SR)
                y = resample_poly(y, TARGET_SR // g, int(sr) // g).astype(np.float32)
            peak = float(np.max(np.abs(y))) if len(y) else 0.0
            if peak > 0:
                y = (y / peak).astype(np.float32)
            return np.asarray(y, dtype=np.float32)
    finally:
        try:
            os.remove(tmp.name)
        except OSError:
            pass

def heuristic_deepfake(y):
    y = np.asarray(y, dtype=np.float32)
    if len(y) < 2048:
        y = np.pad(y, (0, 2048 - len(y)))
    frame = y[:TARGET_SR * 4] if len(y) > TARGET_SR * 4 else y
    spec = np.abs(np.fft.rfft(frame * np.hanning(len(frame)))) + 1e-10
    geo = float(np.exp(np.mean(np.log(spec))))
    arith = float(np.mean(spec))
    flatness = geo / (arith + 1e-10)
    synthetic = float(np.clip((flatness - 0.08) * 4.2, 0.02, 0.97))
    authentic = 1.0 - synthetic
    return {"synthetic_probability": round(synthetic, 4), "authentic_probability": round(authentic, 4), "model_confidence": round(max(synthetic, authentic), 4), "class_0_probability": round(synthetic, 4), "class_1_probability": round(authentic, 4)}

def run_deepfake(y):
    det = get_detector()
    if det is not None:
        try:
            import torch
            from deepfake_detection.inference import TARGET_SAMPLES
            audio = np.asarray(y, dtype=np.float32)
            peak = float(np.max(np.abs(audio))) if len(audio) else 0.0
            if peak > 0:
                audio = audio / peak
            if len(audio) < TARGET_SAMPLES:
                audio = np.pad(audio, (0, TARGET_SAMPLES - len(audio)))
            audio = audio[:TARGET_SAMPLES]
            tensor = torch.tensor(audio, dtype=torch.float32).unsqueeze(0)
            return det.predict(tensor), "aasist"
        except Exception:
            traceback.print_exc()
    note = ("heuristic (AASIST unavailable: %s)" % _detector_error) if _detector_error else "heuristic"
    return heuristic_deepfake(y), note

def mfcc_embedding(y, sr=16000, n_mfcc=20):
    y = np.asarray(y, dtype=np.float32)
    try:
        import librosa
        mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=n_mfcc)
        feat = np.concatenate([mfcc.mean(axis=1), mfcc.std(axis=1)]).astype(np.float64)
    except Exception:
        n = min(len(y), sr * 4); seg = y[:n] if n else y
        mag = np.abs(np.fft.rfft(seg)) + 1e-10
        bands = np.array_split(mag, n_mfcc)
        logm = np.log(np.array([b.mean() for b in bands]) + 1e-10)
        feat = np.concatenate([logm, (logm - logm.mean())]).astype(np.float64)
    norm = np.linalg.norm(feat)
    if norm > 0:
        feat = feat / norm
    return feat

def verify_speakers(y_test, y_ref):
    e1, e2 = mfcc_embedding(y_test), mfcc_embedding(y_ref)
    cos = float(np.dot(e1, e2) / (np.linalg.norm(e1) * np.linalg.norm(e2) + 1e-10))
    score = float(np.clip((cos + 1.0) / 2.0, 0.0, 1.0))
    return {"speaker_match_score": round(score, 4), "cosine_similarity": round(cos, 4), "speaker_verified": bool(score >= 0.75), "threshold": 0.75}

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

@app.get("/api/health")
def health():
    det = get_detector()
    return jsonify({"status": "ok", "service": "voiceguard-api", "deepfake_backend": "aasist" if det is not None else "heuristic", "deepfake_note": None if det is not None else _detector_error, "sample_rate": TARGET_SR})

@app.post("/api/analyze")
def analyze():
    if "audio" not in request.files:
        return jsonify({"error": "missing 'audio' file field"}), 400
    audio_file = request.files["audio"]
    if not audio_file.filename:
        return jsonify({"error": "empty filename"}), 400
    if Path(audio_file.filename).suffix.lower() not in ALLOWED_EXTS:
        return jsonify({"error": "unsupported type"}), 400
    claimed = (request.form.get("claimed_speaker") or "unknown").strip() or "unknown"
    try:
        y = load_mono_16k(audio_file.read(), audio_file.filename)
    except Exception as exc:
        return jsonify({"error": f"could not decode audio: {exc}"}), 400
    if len(y) < TARGET_SR // 4:
        return jsonify({"error": "audio too short (min ~0.25s)"}), 400
    detection, backend = run_deepfake(y)
    if "reference" in request.files and request.files["reference"].filename:
        ref_file = request.files["reference"]
        try:
            y_ref = load_mono_16k(ref_file.read(), ref_file.filename or "reference.wav")
            speaker = verify_speakers(y, y_ref)
            speaker["claimed_identity"] = claimed
        except Exception as exc:
            return jsonify({"error": f"could not decode reference: {exc}"}), 400
    else:
        speaker = {"speaker_match_score": 0.5, "cosine_similarity": 0.0, "speaker_verified": False, "threshold": 0.75, "claimed_identity": claimed, "note": "no reference provided; neutral 0.5 used"}
    risk = calculate_risk({"synthetic_probability": detection["synthetic_probability"], "model_confidence": detection["model_confidence"]}, {"speaker_match_score": speaker["speaker_match_score"]})
    action = take_action(risk["risk_level"])
    return jsonify({"filename": audio_file.filename, "duration_s": round(len(y) / TARGET_SR, 2), "deepfake_backend": backend, "detection": detection, "speaker": speaker, "risk": risk, "prevention": action})

@app.post("/api/verify")
def verify():
    if "audio" not in request.files or "reference" not in request.files:
        return jsonify({"error": "need both 'audio' and 'reference'"}), 400
    try:
        y = load_mono_16k(request.files["audio"].read(), request.files["audio"].filename or "a.wav")
        y_ref = load_mono_16k(request.files["reference"].read(), request.files["reference"].filename or "b.wav")
    except Exception as exc:
        return jsonify({"error": f"could not decode audio: {exc}"}), 400
    result = verify_speakers(y, y_ref)
    result["claimed_identity"] = (request.form.get("claimed_speaker") or "unknown").strip() or "unknown"
    return jsonify(result)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=True)
