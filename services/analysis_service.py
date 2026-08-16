# services/analysis_service.py
from __future__ import annotations
from typing import Dict, Any, Optional

from services.baseline_store import (
    normalize_user_id,
    load_db,
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


def finalize_calibration(user_id: str) -> Dict[str, Any]:
    """
    CALIB_CACHE에 누적된 샘플을 평균내서 baseline_db.json에 '덮어쓰기' 저장.
    완료 후 캐시는 비워짐.
    """
    uid = normalize_user_id(user_id)
    return finalize_calibration_simple(uid)


def get_baseline(user_id: str) -> Dict[str, Any]:
    """현재 저장된 기준선 조회"""
    uid = normalize_user_id(user_id)
    db = load_db()
    b = db.get(uid)
    if not b:
        return {"ok": False, "error": "not_found"}
    return {"ok": True, "baseline": b}


def accumulate_baseline(user_id: str, analysis: dict, strategy: str = "welford") -> dict:
    """
    캘리브레이션 누적:
    - 'welford'  : 증분평균/표준편차를 즉시 DB에 반영 (실시간 누적형)
    - 'simple': 메모리 캐시에 누적하고 finalize 시 산술 평균을 DB에 반영
    """
    uid = normalize_user_id(user_id)

    if strategy == "welford":
        return update_baseline_persisted(uid, analysis)

    if strategy == "simple":
        return append_calib_sample(uid, analysis)

    raise ValueError(f"unsupported calibration strategy: {strategy}")
