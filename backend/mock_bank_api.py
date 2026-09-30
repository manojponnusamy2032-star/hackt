"""Mock bank freeze hook: auditable, bounded, non-blocking (SIH26104).

``freeze_transaction`` is deliberately O(1) and RAM-only (a deque append), so it
can be called from inside the real-time WebSocket loop without risking the
250 ms budget. ``freeze_transaction_async`` is the integration point used by the
FastAPI routes: it hands the hook to a worker thread so the event loop keeps
streaming telemetry while the "bank" is notified.
"""
from __future__ import annotations

import asyncio
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:                                   # package import
    from .risk_scorer import clamp_score
except ImportError:                    # direct script execution
    from risk_scorer import clamp_score

MAX_LOG_ENTRIES = 500                  # bounded: the audit log cannot grow forever
ACTION = "FREEZE_ALL_OUTBOUND"
MAX_SESSION_ID_LEN = 128
DEFAULT_REASON = "CRITICAL FRAUD voice risk"

FREEZE_LOG: deque = deque(maxlen=MAX_LOG_ENTRIES)
_LOCK = threading.Lock()
_SEEN_KEYS: "Dict[str, dict]" = {}


def _clean_session_id(session_id: Optional[str]) -> str:
    text = str(session_id or "").strip()[:MAX_SESSION_ID_LEN]
    return text or "unknown-session"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def freeze_transaction(session_id: str, risk_score: float, reason: str = DEFAULT_REASON,
                       idempotency_key: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> dict:
    """Freeze the mocked transaction and return the audit payload.

    * Non-blocking: no I/O, no locks held across awaits, O(1) work.
    * Idempotent when ``idempotency_key`` is supplied (a retried freeze returns
      the original event marked ``duplicate`` instead of double-logging).
    """
    started = time.perf_counter()
    sid = _clean_session_id(session_id)
    score = clamp_score(risk_score)
    key = str(idempotency_key).strip() if idempotency_key else None

    if key:
        with _LOCK:
            existing = _SEEN_KEYS.get(key)
        if existing is not None:
            return {**existing, "duplicate": True}

    now = _utc_now()
    payload: Dict[str, Any] = {
        "event": "TRANSACTION_FREEZE",
        "freeze_id": f"FRZ-{uuid.uuid4().hex[:10].upper()}",
        "session_id": sid,
        "risk_score": round(score, 2),
        "reason": str(reason or DEFAULT_REASON)[:256],
        "action": ACTION,
        "status": "FROZEN",
        "frozen_at": now.isoformat(),
        "frozen_at_ts": round(now.timestamp(), 3),
        "idempotency_key": key,
        "duplicate": False,
        "audit": {
            "account_locked": True,
            "otp_step_up": True,
            "analyst_notified": True,
            "retention_days": 90,
        },
    }
    if metadata:
        payload["metadata"] = {str(k): v for k, v in list(metadata.items())[:16]}
    payload["hook_latency_us"] = round((time.perf_counter() - started) * 1e6, 2)

    with _LOCK:
        FREEZE_LOG.append(payload)
        if key:
            _SEEN_KEYS[key] = dict(payload)
            if len(_SEEN_KEYS) > MAX_LOG_ENTRIES:
                live = {event.get("idempotency_key") for event in FREEZE_LOG}
                for stale in [k for k in _SEEN_KEYS if k not in live]:
                    _SEEN_KEYS.pop(stale, None)
    return {"ok": True, **payload}


async def freeze_transaction_async(session_id: str, risk_score: float,
                                  reason: str = DEFAULT_REASON,
                                  idempotency_key: Optional[str] = None,
                                  metadata: Optional[Dict[str, Any]] = None) -> dict:
    """Non-blocking wrapper: runs the hook off the event loop thread."""
    return await asyncio.to_thread(
        freeze_transaction, session_id, risk_score, reason, idempotency_key, metadata
    )


def get_freeze_log(limit: int = 50) -> List[dict]:
    """Most recent freeze events, newest last (defensive copies)."""
    try:
        count = max(1, int(limit))
    except (TypeError, ValueError):
        count = 50
    with _LOCK:
        events = list(FREEZE_LOG)[-count:]
    return [dict(event) for event in events]


def freeze_log_size() -> int:
    with _LOCK:
        return len(FREEZE_LOG)


def is_frozen(session_id: str) -> bool:
    """True when this session currently has a freeze on the audit log."""
    sid = _clean_session_id(session_id)
    with _LOCK:
        return any(event.get("session_id") == sid and event.get("status") == "FROZEN"
                   for event in FREEZE_LOG)


def clear_freeze_log() -> int:
    """Drop the audit log (test/demo reset) and return how many rows went."""
    with _LOCK:
        count = len(FREEZE_LOG)
        FREEZE_LOG.clear()
        _SEEN_KEYS.clear()
    return count
