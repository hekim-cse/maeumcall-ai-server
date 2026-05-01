from __future__ import annotations

from fastapi import APIRouter, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse
from typing import Optional
import os
import mimetypes
import subprocess
import uuid

from praat_voice_analysis import analyze_audio
from services.analysis_service import (
    build_payload,
    get_baseline,
    accumulate_baseline,
)
from services.baseline_store import (
    normalize_user_id, load_db, save_db, clear_calib_cache,
    finalize_calibration_simple, delete_baseline, debug_db_info
)

router = APIRouter(prefix="/voice", tags=["voice"])


def _safe_unlink(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.remove(path)
    except Exception:
        pass


@router.post("/analyze")
async def analyze_audio_endpoint(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    mode: str = Form("normal"),       # "normal" | "calibrate"
    strategy: str = Form("welford"),  # "welford" | "median" | "simple"
):
    """
    업로드된 오디오를 분석하여 통일된 JSON 포맷으로 반환합니다.
    - 성공: { ok: true, mode, data: {...} }
    - 실패: { ok: false, error, detail }
    """
    print(f"[srv] /voice/analyze HIT user_id={user_id} mode={mode} mime={file.content_type}")

    tmp_in = f"/tmp/{uuid.uuid4().hex}_{file.filename or 'audio'}"
    with open(tmp_in, "wb") as f:
        f.write(await file.read())

    mime = file.content_type or (mimetypes.guess_type(file.filename or "")[0] or "")
    tmp_for_praat = tmp_in
    converted_tmp = None
    cur: Optional[dict] = None

    try:
        # WAV가 아니면 변환
        is_wav = mime.endswith("/wav") or (file.filename or "").lower().endswith(".wav")
        if not is_wav:
            try:
                subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
            except (FileNotFoundError, subprocess.CalledProcessError):
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
        print(f"[srv] analyze: uid={uid} mode={mode} strategy={strategy}")

        baseline = None
        if uid:
            if mode == "calibrate":
                baseline = accumulate_baseline(uid, cur, strategy=strategy)
                # welford면 DB 즉시 반영됨 → 확인 로그
                if strategy == "welford":
                    snap = load_db().get(uid)
                    print(f"[srv] welford saved -> key={uid}, exists={bool(snap)}, snap={snap}")
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

    except Exception as e:
        return JSONResponse(status_code=400, content={"ok": False, "error": "analyze_failed", "detail": str(e)})

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
    clear_calib_cache(uid)

    db = load_db()
    if uid in db:
        db.pop(uid, None)
        save_db(db)

    return JSONResponse(content={"ok": True})


@router.get("/health")
def voice_health():
    return JSONResponse(content={"ok": True})


@router.post("/ping")
async def voice_post_ping(user_id: Optional[str] = Form(None)):
    return JSONResponse(content={"ok": True, "user_id": user_id or None})


@router.get("/db/debug")
def db_debug():
    """현재 서버가 사용하는 baseline_db.json의 경로/키 확인"""
    return JSONResponse(content={"ok": True, **debug_db_info()})