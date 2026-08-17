# services/analysis_service.py
from __future__ import annotations

from math import isfinite
from typing import Dict, Any, Optional

from services.baseline_store import (
    BaselineMeasurementError,
    extract_measurement,
    normalize_user_id,
    get_persisted_baseline,
    update_baseline_persisted,
    append_calib_sample,
    finalize_calibration_simple,
    pct,
    z,
)


BASELINE_REQUIRED_FIELDS = (
    "pitchHz",
    "pitchStdHz",
    "jitterLocal",
    "jitterStd",
    "shimmerLocal",
    "shimmerStd",
    "samples",
    "ts",
)


def build_payload(
    cur: Dict[str, Any], baseline: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """클라이언트가 기대하는 공통 포맷으로 패킹"""
    cp, cj, cs = extract_measurement(cur)
    payload = {
        "pitch": {"mean": cp, "comment": _comment(cur, "pitch")},
        "jitter": {"value": cj, "comment": _comment(cur, "jitter")},
        "shimmer": {"value": cs, "comment": _comment(cur, "shimmer")},
    }
    if baseline:
        normalized = _validated_baseline(baseline)
        bp = normalized["pitchHz"]
        bj = normalized["jitterLocal"]
        bs = normalized["shimmerLocal"]
        sp = normalized["pitchStdHz"]
        sj = normalized["jitterStd"]
        ss = normalized["shimmerStd"]

        payload["baseline"] = {
            key: normalized[key]
            for key in (*BASELINE_REQUIRED_FIELDS, "pitchIqrHz")
            if key in normalized
        }
        if all(std > 0 for std in (sp, sj, ss)):
            payload["z"] = {
                "pitch": z(cp, bp, sp),
                "jitter": z(cj, bj, sj),
                "shimmer": z(cs, bs, ss),
            }
        if all(value > 0 for value in (bp, bj, bs)):
            payload["deltaPct"] = {
                "pitch": pct(cp, bp),
                "jitter": pct(cj, bj),
                "shimmer": pct(cs, bs),
            }
    return payload


def _comment(cur: Dict[str, Any], metric: str) -> str:
    value = cur.get(metric)
    comment = value.get("comment") if isinstance(value, dict) else None
    if not isinstance(comment, str) or not comment.strip():
        raise BaselineMeasurementError("voice measurement comment is invalid")
    return comment.strip()


def _validated_baseline(baseline: Dict[str, Any]) -> Dict[str, Any]:
    try:
        normalized: Dict[str, Any] = {
            "pitchHz": float(baseline["pitchHz"]),
            "pitchStdHz": float(baseline["pitchStdHz"]),
            "jitterLocal": float(baseline["jitterLocal"]),
            "jitterStd": float(baseline["jitterStd"]),
            "shimmerLocal": float(baseline["shimmerLocal"]),
            "shimmerStd": float(baseline["shimmerStd"]),
            "samples": int(baseline["samples"]),
            "ts": int(baseline["ts"]),
        }
        if baseline.get("pitchIqrHz") is not None:
            normalized["pitchIqrHz"] = float(baseline["pitchIqrHz"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BaselineMeasurementError("baseline fields are incomplete") from exc

    numeric = [
        value
        for key, value in normalized.items()
        if key not in {"samples", "ts"}
    ]
    if (
        normalized["samples"] <= 0
        or not all(isfinite(value) for value in numeric)
        or normalized["pitchHz"] <= 0
        or normalized["jitterLocal"] < 0
        or normalized["shimmerLocal"] < 0
        or normalized["pitchStdHz"] < 0
        or normalized["jitterStd"] < 0
        or normalized["shimmerStd"] < 0
        or normalized.get("pitchIqrHz", 0.0) < 0
    ):
        raise BaselineMeasurementError("baseline values are out of range")
    return normalized


async def finalize_calibration(user_id: str) -> Dict[str, Any]:
    """Persist collected calibration samples and clear them in one transaction."""
    uid = normalize_user_id(user_id)
    return await finalize_calibration_simple(uid)


async def get_baseline(user_id: str) -> Dict[str, Any]:
    """현재 저장된 기준선 조회"""
    uid = normalize_user_id(user_id)
    b = await get_persisted_baseline(uid)
    if not b:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "baseline": b}


async def accumulate_baseline(
    user_id: str, analysis: dict, strategy: str = "welford"
) -> dict:
    """
    캘리브레이션 누적:
    - 'welford'  : 증분평균/표준편차를 즉시 DB에 반영 (실시간 누적형)
    - 'simple': PostgreSQL 샘플 테이블에 누적하고 finalize 시 한 트랜잭션으로 확정
    """
    uid = normalize_user_id(user_id)

    if strategy == "welford":
        return await update_baseline_persisted(uid, analysis)

    if strategy == "simple":
        return await append_calib_sample(uid, analysis)

    raise ValueError(f"unsupported calibration strategy: {strategy}")
