from __future__ import annotations
from pathlib import Path
from typing import Dict, Any, List, Tuple
import json, math, time, re, unicodedata, os
import numpy as np
from urllib.parse import unquote

# 데이터 파일 경로
DB_PATH = (Path(__file__).resolve().parents[1] / "data" / "baseline_db.json")
CALIB_CACHE: Dict[str, List[Tuple[float, float, float]]] = {}

__all__ = (
    "load_db", "save_db", "debug_db_info",
    "update_baseline_welford",
    "append_calib_sample", "clear_calib_cache",
    "finalize_calibration_simple", "delete_baseline",
    "pct", "z", "normalize_user_id",
)


def debug_db_info() -> Dict[str, Any]:
    """현재 서버 프로세스가 사용하는 DB 파일 절대경로/크기/키 목록 확인용"""
    _ensure_parent()
    path = str(DB_PATH.resolve())
    exists = DB_PATH.exists()
    size = DB_PATH.stat().st_size if exists else 0
    try:
        db = load_db()
        keys = list(db.keys())
    except Exception:
        db, keys = {}, []
    return {"path": path, "exists": exists, "size": size, "keys": keys}


def normalize_user_id(user_id: str | None) -> str:
    """카카오 ID나 문자열 user_id를 안전하게 정규화"""
    if not user_id:
        return "guest"
    user_id = unquote(user_id)
    user_id = unicodedata.normalize("NFKC", user_id)
    user_id = user_id.strip()
    user_id = re.sub(r"\s+", " ", user_id)
    if len(user_id) > 64:
        user_id = user_id[:64]
    return user_id


def _ensure_parent():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_db() -> Dict[str, Any]:
    _ensure_parent()
    if not DB_PATH.exists():
        return {}
    try:
        return json.loads(DB_PATH.read_text("utf-8"))
    except Exception:
        return {}


def save_db(db: Dict[str, Any]) -> None:
    """원자적 저장(임시파일 → rename) + 로그"""
    _ensure_parent()
    tmp = DB_PATH.with_suffix(".json.tmp")
    data = json.dumps(db, ensure_ascii=False, indent=2)
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, DB_PATH)
    print(f"[srv] save_db -> {DB_PATH.resolve()} (keys={len(db)})")


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
    user_id = normalize_user_id(user_id)
    p, j, s = _extract(analysis)

    b = db.get(user_id, {
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
    db[user_id] = b
    return b


def append_calib_sample(user_id: str, analysis: Dict[str, Any]) -> Dict[str, Any]:
    user_id = normalize_user_id(user_id)
    p, j, s = _extract(analysis)
    lst = CALIB_CACHE.setdefault(user_id, [])
    lst.append((p, j, s))

    n = len(lst)
    mean_p = sum(x[0] for x in lst) / n
    mean_j = sum(x[1] for x in lst) / n
    mean_s = sum(x[2] for x in lst) / n

    std = lambda arr, m: math.sqrt(sum((v - m) ** 2 for v in arr) / (n - 1)) if n > 1 else 0.0
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
    user_id = normalize_user_id(user_id)
    CALIB_CACHE.pop(user_id, None)


def finalize_calibration_simple(user_id: str) -> Dict[str, Any]:
    user_id = normalize_user_id(user_id)
    samples = CALIB_CACHE.get(user_id, [])
    if not samples:
        return {"ok": False, "error": "no samples"}

    arr = np.array(samples, dtype=float)
    mean_p, mean_j, mean_s = arr.mean(axis=0)

    baseline = {
        "pitchHz":     float(mean_p),
        "jitterLocal": float(mean_j),
        "shimmerLocal":float(mean_s),
        "samples":     len(samples),
        "ts":          int(time.time()),
    }

    db = load_db()
    db[user_id] = baseline
    save_db(db)
    CALIB_CACHE.pop(user_id, None)
    return {"ok": True, "baseline": baseline}


def delete_baseline(user_id: str) -> Dict[str, Any]:
    user_id = normalize_user_id(user_id)
    db = load_db()
    existed = user_id in db
    if existed:
        db.pop(user_id, None)
        save_db(db)
    CALIB_CACHE.pop(user_id, None)
    return {"ok": True, "deleted": existed}