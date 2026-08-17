from __future__ import annotations

from fastapi import APIRouter, Depends, UploadFile, File, Form
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
from core.auth import (
    AuthenticatedUser,
    AuthenticationError,
    optional_authenticated_user,
    require_authenticated_user,
)
from praat_voice_analysis import analyze_audio
from services.analysis_service import (
    build_payload,
    get_baseline,
    accumulate_baseline,
)
from services.baseline_store import (
    BaselineStoreError, normalize_user_id,
    clear_calib_cache, finalize_calibration_simple, delete_baseline
)

router = APIRouter(prefix="/voice", tags=["voice"])
logger = logging.getLogger(__name__)


def _voice_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}},
    )


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
    mode: str = Form("normal"),       # "normal" | "calibrate"
    strategy: str = Form("simple"),  # "simple" | "welford"
    authenticated_user: Optional[AuthenticatedUser] = Depends(
        optional_authenticated_user
    ),
):
    """
    업로드된 오디오를 분석하여 통일된 JSON 포맷으로 반환합니다.
    - 성공: { ok: true, mode, data: {...} }
    - 실패: { ok: false, error, detail }
    """
    logger.debug("Voice analysis requested: mode=%s mime=%s", mode, file.content_type)

    if mode not in {"normal", "calibrate"}:
        return _voice_error(422, "VOICE_MODE_INVALID", "지원하지 않는 음성 분석 모드입니다.")
    if strategy not in {"welford", "simple"}:
        return _voice_error(422, "VOICE_STRATEGY_INVALID", "지원하지 않는 기준선 계산 방식입니다.")
    if mode == "calibrate" and authenticated_user is None:
        raise AuthenticationError(
            "AUTHORIZATION_REQUIRED",
            "음성 기준선 캘리브레이션에는 로그인이 필요합니다.",
            status_code=401,
        )

    content = await file.read(AUDIO_UPLOAD_MAX_BYTES + 1)
    if len(content) > AUDIO_UPLOAD_MAX_BYTES:
        return _voice_error(413, "VOICE_FILE_TOO_LARGE", "업로드한 음성 파일이 허용 크기를 초과했습니다.")

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
                return _voice_error(503, "VOICE_CONVERTER_UNAVAILABLE", "음성 변환기를 사용할 수 없습니다.")
            converted_tmp = f"{tmp_in}.wav"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", tmp_in, "-ac", "1", "-ar", "16000", "-sample_fmt", "s16", converted_tmp],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
            except subprocess.TimeoutExpired:
                return _voice_error(408, "VOICE_CONVERSION_TIMEOUT", "음성 변환 시간이 제한을 초과했습니다.")
            except subprocess.CalledProcessError:
                return _voice_error(422, "VOICE_CONVERSION_FAILED", "지원되는 음성 파일로 변환하지 못했습니다.")
            tmp_for_praat = converted_tmp

        # 실제 Praat 분석
        cur = analyze_audio(tmp_for_praat)
        if not isinstance(cur, dict):
            return _voice_error(502, "VOICE_ANALYSIS_INVALID", "음성 분석 결과가 계약과 일치하지 않습니다.")

        # 사용자 ID 정규화
        uid = (
            normalize_user_id(authenticated_user.uid)
            if authenticated_user is not None
            else None
        )
        baseline = None
        if uid:
            if mode == "calibrate":
                baseline = await accumulate_baseline(uid, cur, strategy=strategy)
            else:
                baseline = (await get_baseline(uid)).get("baseline")

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

    except BaselineStoreError:
        raise
    except Exception:
        logger.exception("Voice analysis failed")
        return _voice_error(500, "VOICE_ANALYSIS_FAILED", "음성 분석을 완료하지 못했습니다.")

    finally:
        _safe_unlink(tmp_in)
        if converted_tmp and converted_tmp != tmp_in:
            _safe_unlink(converted_tmp)


@router.get("/baseline")
async def baseline_get(
    authenticated_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """기준선 조회"""
    uid = normalize_user_id(authenticated_user.uid)
    res = await get_baseline(uid)
    if not res.get("ok"):
        return _voice_error(404, "VOICE_BASELINE_NOT_FOUND", "저장된 음성 기준선이 없습니다.")
    return JSONResponse(content=res)


@router.post("/calibrate/finalize")
async def calibrate_finalize(
    authenticated_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """샘플 모음을 평균내서 기존 값을 덮어쓰기"""
    res = await finalize_calibration_simple(normalize_user_id(authenticated_user.uid))
    if not res.get("ok"):
        return _voice_error(409, "VOICE_CALIBRATION_EMPTY", "확정할 캘리브레이션 샘플이 없습니다.")
    return JSONResponse(content=res)


@router.post("/baseline/delete")
async def api_delete_baseline(
    authenticated_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """인증된 사용자의 확정 기준선과 진행 중인 샘플을 삭제한다."""
    uid = normalize_user_id(authenticated_user.uid)
    return await delete_baseline(uid)


@router.post("/calibrate/reset")
async def calibrate_reset(
    authenticated_user: AuthenticatedUser = Depends(require_authenticated_user),
):
    """진행 중인 샘플만 비우고 확정된 기준선은 유지한다."""
    uid = normalize_user_id(authenticated_user.uid)
    await clear_calib_cache(uid)
    return JSONResponse(content={"ok": True})


@router.get("/health")
def voice_health():
    return JSONResponse(content={"ok": True})


@router.post("/ping")
async def voice_post_ping():
    return JSONResponse(content={"ok": True})
