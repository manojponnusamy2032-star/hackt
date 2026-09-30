"""EMA-smoothed risk scoring: SAFE / WARNING / CRITICAL FRAUD (SIH26104).

This module owns the *only* definition of the risk bands:

    0 - 34   SAFE
    35 - 69  WARNING
    70 - 100 CRITICAL FRAUD  -> triggers the mock bank freeze hook

The EMA (alpha = 0.3) damps frame-to-frame whipsaw, and the scorer additionally
tracks a *critical episode* with hysteresis so a score hovering around 70 opens
the bank freeze exactly once instead of flapping on every frame.
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

ALPHA = 0.3                  # EMA smoothing factor
SAFE_MAX = 34.0              # 0-34 SAFE
WARNING_MIN = 35.0           # 35-69 WARNING
WARNING_MAX = 69.0
CRITICAL_MIN = 70.0          # 70-100 CRITICAL FRAUD
RELEASE_BELOW = 65.0         # close a critical episode once risk decays here
HISTORY_LEN = 64

BANDS: Dict[str, tuple] = {
    "SAFE": (0.0, SAFE_MAX),
    "WARNING": (WARNING_MIN, WARNING_MAX),
    "CRITICAL FRAUD": (CRITICAL_MIN, 100.0),
}


def clamp_score(value: float) -> float:
    """Clamp any numeric-ish value into 0-100; non-finite input becomes 0.0.

    Guards the NaN trap: ``max(0.0, min(100.0, float('nan')))`` evaluates to
    **100.0** in Python, which would let one malformed frame fire a bank freeze.
    """
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(score):
        return 0.0
    return float(min(100.0, max(0.0, score)))


def classify_risk(score: float) -> str:
    """Map a 0-100 score onto the three risk bands."""
    value = clamp_score(score)
    if value >= CRITICAL_MIN:
        return "CRITICAL FRAUD"
    if value >= WARNING_MIN:
        return "WARNING"
    return "SAFE"


@dataclass(frozen=True)
class RiskState:
    """Result of one scoring step (safe to serialise straight to the UI)."""

    raw_score: float          # this frame's anomaly score
    smoothed_score: float     # EMA output (the number the dashboard shows)
    level: str                # SAFE | WARNING | CRITICAL FRAUD
    critical: bool            # smoothed score is inside the critical band
    bank_freeze: bool         # rising edge -> fire the bank hook now
    episode_id: Optional[str] = None
    invalid: bool = False     # frame was non-finite and ignored

    def to_dict(self) -> Dict[str, object]:
        return {
            "raw_score": self.raw_score,
            "risk_score": self.smoothed_score,
            "level": self.level,
            "critical": self.critical,
            "bank_freeze": self.bank_freeze,
            "episode_id": self.episode_id,
            "invalid": self.invalid,
        }


class RiskScorer:
    """Stateful EMA risk filter with episode-based bank-freeze triggering.

    * ``alpha`` (default 0.3) controls smoothing: ``ema = a*raw + (1-a)*ema``.
    * Non-finite input (NaN/Inf) is **ignored**, never allowed to move the EMA -
      a corrupt frame must not be able to trigger a freeze.
    * ``RiskState.bank_freeze`` is True only on the *rising edge* into the
      critical band, and the episode closes once the EMA decays below
      ``release_below`` (hysteresis), so one incident freezes the account once.
    """

    def __init__(self, alpha: float = ALPHA, initial: float = 0.0,
                 release_below: float = RELEASE_BELOW) -> None:
        if not 0.0 < float(alpha) <= 1.0:
            raise ValueError("alpha must be in (0, 1]")
        self.alpha = float(alpha)
        self.release_below = clamp_score(release_below)
        self._initial = clamp_score(initial)
        self._ema: Optional[float] = None
        self.updates = 0
        self.invalid_updates = 0
        self.freezes_triggered = 0      # critical episodes opened
        self.critical_frames = 0        # frames spent inside the critical band
        self.history: Deque[float] = deque(maxlen=HISTORY_LEN)
        self._episode_open = False
        self._episode_seq = 0

    # ------------------------------------------------------------------ ingest
    def update(self, anomaly_score: float) -> RiskState:
        """Fold one frame score into the EMA and report the smoothed state."""
        invalid = False
        try:
            raw = float(anomaly_score)
        except (TypeError, ValueError):
            raw, invalid = 0.0, True
        if invalid or not math.isfinite(raw):
            # Hold the current estimate instead of decaying it: a broken frame
            # carries no information, it must not move risk in either direction.
            raw = float(self._ema) if self._ema is not None else self._initial
            invalid = True
            self.invalid_updates += 1
        raw = clamp_score(raw)

        if self._ema is None:
            self._ema = self._initial + self.alpha * (raw - self._initial)
        else:
            self._ema = self.alpha * raw + (1.0 - self.alpha) * self._ema
        self._ema = clamp_score(self._ema)
        self.updates += 1
        self.history.append(round(self._ema, 2))

        level = classify_risk(self._ema)
        critical = level == "CRITICAL FRAUD"
        if critical:
            self.critical_frames += 1

        bank_freeze = False
        episode_id: Optional[str] = None
        if critical and not self._episode_open:          # rising edge
            self._episode_open = True
            self._episode_seq += 1
            self.freezes_triggered += 1
            bank_freeze = True
        elif self._episode_open and self._ema < self.release_below:   # hysteresis
            self._episode_open = False
        if self._episode_open:
            episode_id = f"EP-{self._episode_seq:04d}"

        return RiskState(
            raw_score=round(raw, 2),
            smoothed_score=round(float(self._ema), 2),
            level=level,
            critical=critical,
            bank_freeze=bank_freeze,
            episode_id=episode_id,
            invalid=invalid,
        )

    # ------------------------------------------------------------------ views
    @property
    def current(self) -> float:
        return round(clamp_score(self._ema if self._ema is not None else self._initial), 2)

    @property
    def level(self) -> str:
        return classify_risk(self.current)

    @property
    def in_critical_episode(self) -> bool:
        return self._episode_open

    def snapshot(self) -> Dict[str, object]:
        return {
            "risk_score": self.current,
            "level": self.level,
            "alpha": self.alpha,
            "updates": self.updates,
            "invalid_updates": self.invalid_updates,
            "critical_frames": self.critical_frames,
            "freezes_triggered": self.freezes_triggered,
            "critical_episode": self._episode_open,
            "history": list(self.history),
        }

    def reset(self, initial: float = 0.0) -> None:
        self._initial = clamp_score(initial)
        self._ema = None
        self.updates = 0
        self.invalid_updates = 0
        self.freezes_triggered = 0
        self.critical_frames = 0
        self.history.clear()
        self._episode_open = False
        self._episode_seq = 0

