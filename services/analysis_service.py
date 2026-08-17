# services/analysis_service.py
from __future__ import annotations
from typing import Dict, Any, Optional

from services.baseline_store import (
    normalize_user_id,
    get_persisted_baseline,
    update_baseline_persisted,
    append_calib_sample,
    finalize_calibration_simple,
    pct, z,
)

def build_payload(cur: Dict[str, Any], baseline: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """클라이언트가 기대하는 공통 포맷으로 패킹"""
    payload = {
        "pitch":   {"mean": float(cur["pitch"]["mean"]),     "comment": cur["pitch"]["comment"]},
        "jitter":  {"value": float(cur["jitter"]["value"]),  "comment": cur["jitter"]["comment"]},
        "shimmer": {"value": float(cur["shimmer"]["value"]), "comment": cur["shimmer"]["comment"]},
    }
    if baseline:
        cp, cj, cs = float(cur["pitch"]["mean"]), float(cur["jitter"]["value"]), float(cur["shimmer"]["value"])
        bp = float(baseline.get("pitchHz", 0))
        bj = float(baseline.get("jitterLocal", 0))
        bs = float(baseline.get("shimmerLocal", 0))
        sp = float(baseline.get("pitchStdHz", 0))
        sj = float(baseline.get("jitterStd", 0))
        ss = float(baseline.get("shimmerStd", 0))

        payload["baseline"] = {
            k: baseline[k]
            for k in ("pitchHz","pitchStdHz","pitchIqrHz","jitterLocal","jitterStd","shimmerLocal","shimmerStd","samples","ts")
            if k in baseline
        }
        payload["z"] = {"pitch": z(cp, bp, sp), "jitter": z(cj, bj, sj), "shimmer": z(cs, bs, ss)}
        payload["deltaPct"] = {"pitch": pct(cp, bp), "jitter": pct(cj, bj), "shimmer": pct(cs, bs)}
    return payload


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
