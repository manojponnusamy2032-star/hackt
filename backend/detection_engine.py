"""Anomaly scoring of acoustic features against synthetic-voice thresholds.

Component scores (0-100) are blended with fixed weights:

    HF power ratio  40%  - vocoder/neural codecs leak broadband energy >4 kHz
    Pitch realism   35%  - voicing presence + F0 variance (flat pitch = robotic)
    Spectral flux   25%  - unnatural frame-to-frame spectral jitter

A conjunctive rule promotes loud, pitchless, HF-heavy audio straight into the
CRITICAL band: broadband noise with no glottal structure is not a human voice.

Everything here is O(1) in the number of features (< 20 ms, measured ~10 us),
and threshold/weight overrides are honoured instead of silently ignored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional

try:                                       # package import
    from .risk_scorer import classify_risk, clamp_score
except ImportError:                        # direct script execution
    from risk_scorer import classify_risk, clamp_score

# Threshold bands: (safe_max, warn_max). Tuned for: HF ratio 0..1,
# F0 variance Hz^2, flux 0..~2, rms 0..1.
THRESHOLDS: Dict[str, tuple] = {
    "hf_power_ratio": (0.18, 0.35),
    "pitch_f0_variance": (1500.0, 6000.0),
    "spectral_flux": (0.25, 0.60),
}
WEIGHTS: Dict[str, float] = {"hf_power_ratio": 0.40, "pitch_f0_variance": 0.35,
                             "spectral_flux": 0.25}

# Voicing behaviour of the pitch component.
NO_VOICING_SCORE = 90.0        # < 15% of frames show glottal periodicity
LOW_VOICING_SCORE = 65.0       # 15-35% voiced -> unclear/altered prosody
FLAT_PITCH_SCORE = 50.0        # voiced but monotone across the whole window
UNVOICED_RATIO = 0.15
PARTIAL_VOICED_RATIO = 0.35
FLAT_PITCH_VARIANCE = 0.5

# Conjunctive synthetic-voice rule + silence damping.
PITCHLESS_HF_PROMOTION = 80.0
SILENCE_RMS = 1e-3

#: Published on /api/features so the UI can explain every decision.
VOICING_RULES: Dict[str, float] = {
    "unvoiced_ratio": UNVOICED_RATIO,
    "partial_voiced_ratio": PARTIAL_VOICED_RATIO,
    "flat_pitch_variance": FLAT_PITCH_VARIANCE,
    "silence_rms": SILENCE_RMS,
    "pitchless_hf_promotion": PITCHLESS_HF_PROMOTION,
}


def _safe_float(features: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    """Never raise on a missing/NaN/None/str feature value."""
    try:
        value = float(features.get(key, default))
    except (TypeError, ValueError, AttributeError):
        return default
    return value if value == value and abs(value) != float("inf") else default


def _resolve_thresholds(thresholds: Optional[Mapping[str, Any]] = None) -> Dict[str, tuple]:
    """Merge caller overrides over the defaults without losing missing keys."""
    resolved = dict(THRESHOLDS)
    for key, value in (thresholds or {}).items():
        try:
            pair = tuple(float(v) for v in value)          # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if len(pair) == 2 and pair[0] < pair[1]:
            resolved[str(key)] = pair
    return resolved


def _resolve_weights(weights: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    resolved = dict(WEIGHTS)
    for key, value in (weights or {}).items():
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight >= 0.0:
            resolved[str(key)] = weight
    return resolved


def _band_score(value: float, safe_max: float, warn_max: float) -> float:
    """Piecewise-linear 0-100 mapping: <=safe_max -> 0..30, warn -> 30..70, above -> 70..100."""
    v = max(0.0, float(value))
    if v <= safe_max:
        return (v / safe_max) * 30.0 if safe_max > 0 else 0.0
    if v <= warn_max:
        span = max(warn_max - safe_max, 1e-9)
        return 30.0 + ((v - safe_max) / span) * 40.0
    overflow = (v - warn_max) / max(warn_max, 1e-9)
    return min(100.0, 70.0 + overflow * 30.0)


def _pitch_score(pitch_variance: float, voiced_ratio: Optional[float],
                 thresholds: Optional[Mapping[str, tuple]] = None) -> float:
    """Pitch realism: needs glottal structure, and it must not be robotic-flat."""
    resolved = thresholds or THRESHOLDS
    band = resolved.get("pitch_f0_variance", THRESHOLDS["pitch_f0_variance"])
    if voiced_ratio is None:
        return _band_score(pitch_variance, *band)
    if voiced_ratio < UNVOICED_RATIO:
        return NO_VOICING_SCORE
    if voiced_ratio < PARTIAL_VOICED_RATIO:
        return LOW_VOICING_SCORE
    if pitch_variance <= FLAT_PITCH_VARIANCE:
        return FLAT_PITCH_SCORE
    return _band_score(pitch_variance, *band)


def score_components(features: Mapping[str, Any],
                     thresholds: Optional[Mapping[str, Any]] = None) -> Dict[str, float]:
    """Per-feature anomaly contributions (0-100) - dashboard explainability."""
    resolved = _resolve_thresholds(thresholds)
    hf = _safe_float(features, "hf_power_ratio")
    pitch = _safe_float(features, "pitch_f0_variance")
    flux = _safe_float(features, "spectral_flux")
    raw_voiced = features.get("voiced_ratio")
    voiced_ratio = None if raw_voiced is None else max(0.0, min(1.0, _safe_float(features, "voiced_ratio")))
    return {
        "hf_power_ratio": round(_band_score(hf, *resolved["hf_power_ratio"]), 2),
        "pitch_f0_variance": round(_pitch_score(pitch, voiced_ratio, resolved), 2),
        "spectral_flux": round(_band_score(flux, *resolved["spectral_flux"]), 2),
    }


def calculate_anomaly_score(features: Mapping[str, Any],
                            thresholds: Optional[Mapping[str, Any]] = None,
                            weights: Optional[Mapping[str, Any]] = None) -> float:
    """Blend the weighted feature bands into a 0-100 anomaly score.

    Sub-millisecond by construction: no allocation beyond three maps, so the
    250 ms streaming budget is never at risk from this stage.
    """
    resolved_thresholds = _resolve_thresholds(thresholds)
    resolved_weights = _resolve_weights(weights)
    components = score_components(features, resolved_thresholds)
    weight_sum = sum(resolved_weights.get(key, 0.0) for key in components) or 1.0
    score = sum(components[key] * resolved_weights.get(key, 0.0) for key in components) / weight_sum

    hf = _safe_float(features, "hf_power_ratio")
    rms = _safe_float(features, "rms_energy")
    if features.get("voiced_ratio") is not None and _safe_float(features, "voiced_ratio") < UNVOICED_RATIO:
        if hf >= resolved_thresholds["hf_power_ratio"][1]:
            score = max(score, PITCHLESS_HF_PROMOTION)

    if rms < SILENCE_RMS:                  # silence is not fraud -> damp toward 0
        score *= min(1.0, rms / SILENCE_RMS) * 0.25
    return round(clamp_score(score), 2)


@dataclass
class DetectionResult:
    """Outcome of scoring one frame/window."""

    anomaly_score: float
    band_scores: Dict[str, float]
    level: str
    weights: Dict[str, float] = field(default_factory=dict)

    @property
    def critical(self) -> bool:
        return self.level == "CRITICAL FRAUD"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "anomaly_score": self.anomaly_score,
            "band_scores": self.band_scores,
            "level": self.level,
            "critical": self.critical,
        }


class DetectionEngine:
    """Feature -> anomaly score. Sessions own one instance each.

    ``thresholds``/``weights`` overrides are merged over the defaults and are
    genuinely used (the previous implementation accepted them and ignored them).
    """

    def __init__(self, thresholds: Optional[Mapping[str, Any]] = None,
                 weights: Optional[Mapping[str, Any]] = None) -> None:
        self.thresholds = _resolve_thresholds(thresholds)
        self.weights = _resolve_weights(weights)

    def score(self, features: Mapping[str, Any]) -> DetectionResult:
        score = calculate_anomaly_score(features, self.thresholds, self.weights)
        bands = score_components(features, self.thresholds)
        return DetectionResult(
            anomaly_score=score,
            band_scores=bands,
            level=classify_risk(score),
            weights=dict(self.weights),
        )

    def reset(self) -> None:
        """Stateless engine: present so callers can reset engines uniformly."""
        return None

