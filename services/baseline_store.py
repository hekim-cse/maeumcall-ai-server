from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import hashlib
import hmac
import json
import math
import os
import time
import unicodedata
import threading
import numpy as np

from core.config import BASELINE_ID_HMAC_SECRET


class BaselineStoreError(RuntimeError):
    """Raised when persisted voice baseline data cannot be read safely."""

    code = "VOICE_BASELINE_STORE_FAILED"
    public_message = "음성 기준선 저장소를 처리하지 못했습니다."
    status_code = 500


class BaselineIdentityError(BaselineStoreError):
    """Raised when a user identifier cannot be safely pseudonymized."""

    code = "VOICE_BASELINE_ID_INVALID"
    public_message = "유효하지 않은 사용자 식별자입니다."
    status_code = 422


class BaselineIdentityConfigurationError(BaselineStoreError):
    """Raised when baseline pseudonymization is not configured."""

    code = "VOICE_BASELINE_SECURITY_NOT_CONFIGURED"
    public_message = "음성 기준선 보안 설정이 완료되지 않았습니다."
    status_code = 503

# 데이터 파일 경로
DB_PATH = (Path(__file__).resolve().parents[1] / "data" / "baseline_db.json")
CALIB_CACHE: Dict[str, List[Tuple[float, float, float]]] = {}
_STORE_LOCK = threading.RLock()

__all__ = (
    "load_db", "save_db",
    "update_baseline_welford",
    "update_baseline_persisted",
    "append_calib_sample", "clear_calib_cache",
    "finalize_calibration_simple", "delete_baseline",
    "get_persisted_baseline",
    "pct", "z", "normalize_user_id", "pseudonymize_user_id",
)


def normalize_user_id(user_id: str | None) -> str:
    """Validate the opaque account identifier received from the client."""
    if not isinstance(user_id, str):
        raise BaselineIdentityError("user_id must be a string")
    normalized = unicodedata.normalize("NFKC", user_id).strip()
    if not normalized:
        raise BaselineIdentityError("user_id must not be empty")
    if len(normalized) > 128:
        raise BaselineIdentityError("user_id must be at most 128 characters")
    if any(unicodedata.category(char).startswith("C") for char in normalized):
        raise BaselineIdentityError("user_id contains control characters")
    return normalized


def pseudonymize_user_id(user_id: str) -> str:
    normalized = normalize_user_id(user_id)
    if len(BASELINE_ID_HMAC_SECRET) < 32:
        raise BaselineIdentityConfigurationError(
            "BASELINE_ID_HMAC_SECRET must contain at least 32 characters"
        )
    digest = hmac.new(
        BASELINE_ID_HMAC_SECRET.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"user_hmac_sha256:{digest}"


def _ensure_parent():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_db() -> Dict[str, Any]:
    with _STORE_LOCK:
        _ensure_parent()
        if not DB_PATH.exists():
            return {}
        try:
            data = json.loads(DB_PATH.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise BaselineStoreError("Voice baseline store is unreadable") from exc
        if not isinstance(data, dict):
            raise BaselineStoreError("Voice baseline store must contain an object")
        return data


def save_db(db: Dict[str, Any]) -> None:
    """원자적 저장(staging file → rename) + 로그"""
    with _STORE_LOCK:
        _ensure_parent()
        tmp = DB_PATH.with_name(f".{DB_PATH.name}.{os.getpid()}.{threading.get_ident()}.tmp")
        data = json.dumps(db, ensure_ascii=False, indent=2)
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, DB_PATH)
        finally:
            if tmp.exists():
                tmp.unlink()


def pct(cur: float, base: float) -> float:
    if base == 0:
        return 0.0
    return round((cur - base) / base * 100.0, 3)


def z(cur: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return round((cur - mean) / std, 3)


def _extract(analysis: Dict[str, Any]) -> Tuple[float, float, float]:
    p = float(analysis["pitch"]["mean"])
    j = float(analysis["jitter"]["value"])
    s = float(analysis["shimmer"]["value"])
    return p, j, s


def update_baseline_welford(db: Dict[str, Any], user_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    user_key = pseudonymize_user_id(user_id)
    p, j, s = _extract(analysis)

    b = db.get(user_key, {
        "n": 0,
        "pitchHz": 0.0, "pitchStdHz": 0.0, "pitch_m2": 0.0,
        "jitterLocal": 0.0, "jitterStd": 0.0, "jitter_m2": 0.0,
        "shimmerLocal": 0.0, "shimmerStd": 0.0, "shimmer_m2": 0.0,
        "pitchIqrHz": 0.0,
        "samples": 0,
        "ts": int(time.time()),
    })

    n = int(b.get("n", 0)) + 1

    delta = p - b["pitchHz"]; mean_p = b["pitchHz"] + delta / n; m2_p = b["pitch_m2"] + delta * (p - mean_p)
    delta = j - b["jitterLocal"]; mean_j = b["jitterLocal"] + delta / n; m2_j = b["jitter_m2"] + delta * (j - mean_j)
    delta = s - b["shimmerLocal"]; mean_s = b["shimmerLocal"] + delta / n; m2_s = b["shimmer_m2"] + delta * (s - mean_s)

    std_p = math.sqrt(m2_p / (n - 1)) if n > 1 else 0.0
    std_j = math.sqrt(m2_j / (n - 1)) if n > 1 else 0.0
    std_s = math.sqrt(m2_s / (n - 1)) if n > 1 else 0.0

    b.update({
        "n": n,
        "pitchHz": round(mean_p, 6), "pitchStdHz": round(std_p, 6), "pitch_m2": m2_p,
        "jitterLocal": round(mean_j, 6), "jitterStd": round(std_j, 6), "jitter_m2": m2_j,
        "shimmerLocal": round(mean_s, 6), "shimmerStd": round(std_s, 6), "shimmer_m2": m2_s,
        "samples": n,
        "ts": int(time.time()),
    })
    db[user_key] = b
    return b


def update_baseline_persisted(user_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically apply one Welford sample and persist it within this process."""
    with _STORE_LOCK:
        db = load_db()
        baseline = update_baseline_welford(db, user_id, analysis)
        save_db(db)
        return baseline


def append_calib_sample(user_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    with _STORE_LOCK:
        user_key = pseudonymize_user_id(user_id)
        p, j, s = _extract(analysis)
        lst = CALIB_CACHE.setdefault(user_key, [])
        lst.append((p, j, s))
        n = len(lst)
        mean_p = sum(x[0] for x in lst) / n
        mean_j = sum(x[1] for x in lst) / n
        mean_s = sum(x[2] for x in lst) / n

        std = lambda arr, mean: math.sqrt(sum((v - mean) ** 2 for v in arr) / (n - 1)) if n > 1 else 0.0
        std_p = std([x[0] for x in lst], mean_p)
        std_j = std([x[1] for x in lst], mean_j)
        std_s = std([x[2] for x in lst], mean_s)

        return {
            "pitchHz": round(mean_p, 6), "pitchStdHz": round(std_p, 6),
            "jitterLocal": round(mean_j, 6), "jitterStd": round(std_j, 6),
            "shimmerLocal": round(mean_s, 6), "shimmerStd": round(std_s, 6),
            "samples": n,
            "ts": int(time.time()),
        }


def clear_calib_cache(user_id: str) -> None:
    with _STORE_LOCK:
        user_key = pseudonymize_user_id(user_id)
        CALIB_CACHE.pop(user_key, None)


def finalize_calibration_simple(user_id: str) -> Dict[str, Any]:
    with _STORE_LOCK:
        user_key = pseudonymize_user_id(user_id)
        samples = list(CALIB_CACHE.get(user_key, []))
        if not samples:
            return {"ok": False, "error": "no samples"}
        arr = np.array(samples, dtype=float)
        mean_p, mean_j, mean_s = arr.mean(axis=0)
        baseline = {
            "pitchHz": float(mean_p),
            "jitterLocal": float(mean_j),
            "shimmerLocal": float(mean_s),
            "samples": len(samples),
            "ts": int(time.time()),
        }
        db = load_db()
        db[user_key] = baseline
        save_db(db)
        CALIB_CACHE.pop(user_key, None)
        return {"ok": True, "baseline": baseline}


def delete_baseline(user_id: str) -> Dict[str, Any]:
    with _STORE_LOCK:
        user_key = pseudonymize_user_id(user_id)
        db = load_db()
        existed = user_key in db
        if existed:
            db.pop(user_key, None)
            save_db(db)
        CALIB_CACHE.pop(user_key, None)
        return {"ok": True, "deleted": existed}


def get_persisted_baseline(user_id: str) -> Dict[str, Any] | None:
    user_key = pseudonymize_user_id(user_id)
    return load_db().get(user_key)
