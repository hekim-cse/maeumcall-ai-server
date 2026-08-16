from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from pathlib import Path
from typing import Optional
import os
import mimetypes
import subprocess
import tempfile
import uuid
import logging

from core.config import AUDIO_UPLOAD_MAX_BYTES
from praat_voice_analysis import analyze_audio
from services.analysis_service import (
    build_payload,
    get_baseline,
    accumulate_baseline,
)
from services.baseline_store import (
    normalize_user_id,
    finalize_calibration_simple, delete_baseline
)

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


def _safe_unlink(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("Failed to remove voice analysis file: %s", path, exc_info=True)


@router.post("/analyze")
async def analyze_audio_endpoint(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    mode: str = Form("normal"),       # "normal" | "calibrate"
    strategy: str = Form("simple"),  # "simple" | "welford"
):
    """
    업로드된 오디오를 분석하여 통일된 JSON 포맷으로 반환합니다.
    - 성공: { ok: true, mode, data: {...} }
    - 실패: { ok: false, error, detail }
    """
    logger.debug("Voice analysis requested: mode=%s mime=%s", mode, file.content_type)

    if mode not in {"normal", "calibrate"}:
        return JSONResponse(status_code=422, content={"ok": False, "error": "invalid_mode"})
    if strategy not in {"welford", "simple"}:
        return JSONResponse(status_code=422, content={"ok": False, "error": "invalid_strategy"})

    content = await file.read(AUDIO_UPLOAD_MAX_BYTES + 1)
    if len(content) > AUDIO_UPLOAD_MAX_BYTES:
        return JSONResponse(status_code=413, content={"ok": False, "error": "file_too_large"})

    suffix = Path(file.filename or "").suffix.lower()
    if len(suffix) > 10 or not suffix.replace(".", "").isalnum():
        suffix = ".bin"
    tmp_in = os.path.join(tempfile.gettempdir(), f"maeumcall_{uuid.uuid4().hex}{suffix}")
    with open(tmp_in, "wb") as f:
        f.write(content)

    mime = file.content_type or (mimetypes.guess_type(file.filename or "")[0] or "")
    tmp_for_praat = tmp_in
    converted_tmp = None
    cur: Optional[dict] = None

    try:
        # WAV가 아니면 변환
        is_wav = mime.endswith("/wav") or (file.filename or "").lower().endswith(".wav")
        if not is_wav:
            try:
                subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True, timeout=10)
            except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": "convert_missing", "detail": "ffmpeg 미설치/실행 불가"},
                )
            converted_tmp = f"{tmp_in}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_in, "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", converted_tmp],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                return JSONResponse(
                    status_code=408,
                    content={"ok": False, "error": "convert_timeout"},
                )
            except subprocess.CalledProcessError as e:
                return JSONResponse(
                    status_code=400,
                    content={"ok": False, "error": "convert_failed", "detail": e.stderr.decode("utf-8", "ignore")},
                )
            tmp_for_praat = converted_tmp

        # 실제 Praat 분석
        cur = analyze_audio(tmp_for_praat)
        if not isinstance(cur, dict):
            return JSONResponse(status_code=400, content={"ok": False, "error": "analyze_invalid"})

        # 사용자 ID 정규화
        uid = normalize_user_id(user_id) if user_id else None
        baseline = None
        if uid:
            if mode == "calibrate":
                baseline = accumulate_baseline(uid, cur, strategy=strategy)
            else:
                baseline = get_baseline(uid).get("baseline")

        # 클라이언트로 보낼 payload 생성
        payload = build_payload(cur, baseline)

        # 캘리브레이션 모드일 경우, 샘플 수도 같이 보냄
        if uid and mode == "calibrate" and baseline:
            return JSONResponse(
                content={
                    "ok": True,
                    "mode": "calibrate",
                    "data": payload,
                    "samples": baseline.get("samples", baseline.get("n", 0)),
                }
            )

        return JSONResponse(content={"ok": True, "mode": mode, "data": payload})

    except Exception:
        logger.exception("Voice analysis failed")
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": "analyze_failed"},
        )

    finally:
        _safe_unlink(tmp_in)
        if converted_tmp and converted_tmp != tmp_in:
            _safe_unlink(converted_tmp)


@router.get("/baseline")
def baseline_get(user_id: str = Query(...)):
    """기준선 조회"""
    uid = normalize_user_id(user_id)
    res = get_baseline(uid)
    return JSONResponse(content=res)


@router.post("/calibrate/finalize")
def calibrate_finalize(user_id: str = Form(...)):
    """샘플 모음을 평균내서 기존 값을 덮어쓰기"""
    res = finalize_calibration_simple(normalize_user_id(user_id))
    return JSONResponse(content=res)


@router.post("/baseline/delete")
def api_delete_baseline(user_id: str = Form(None), q_user_id: str = Query(None)):
    """user_id는 POST form 또는 GET query 중 하나로 받음"""
    raw = user_id or q_user_id
    if not raw:
        return {"ok": False, "error": "missing user_id"}
    uid = normalize_user_id(raw)
    return delete_baseline(uid)


@router.post("/calibrate/reset")
def calibrate_reset(user_id: str = Form(...)):
    """메모리 캐시/DB 기준선 리셋"""
    uid = normalize_user_id(user_id)
    result = delete_baseline(uid)
    return JSONResponse(content={"ok": True, "deleted": result["deleted"]})


@router.get("/health")
def voice_health():
    return JSONResponse(content={"ok": True})


@router.post("/ping")
async def voice_post_ping(user_id: Optional[str] = Form(None)):
    return JSONResponse(content={"ok": True, "user_id": user_id or None})
