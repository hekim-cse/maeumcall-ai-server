# 📄 main.py
from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import shutil
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from core.config import (
    BASELINE_ID_HMAC_SECRET,
    CORS_ALLOW_ORIGINS,
    HF_LOCAL_MODEL_ENABLED,
    OPENAI_API_KEY,
)
from core.database import database_is_ready, dispose_engine
from core.observability import record_contract_failure, render_metrics
from llm.errors import AIServiceError
from routes.chat_routes import router as chat_router
from routes.suggest_routes import router as suggest_router
from routes.voice_routes import router as voice_router
from routes.wordfreq_router import router as wordfreq_router
from server.api_call import router as call_router
from services.baseline_store import BaselineStoreError
from services.flow.common.state_contract import ScenarioStateContractError

logger = logging.getLogger("maeumcall.http")


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(
    title="MaeumCall AI Server",
    description=(
        "마음콜의 고도화 프로젝트: LangGraph 기반 상태 관리, 검증 가능한 "
        "응답 생성, 통화 음성 분석을 제공하는 AI 서버"
    ),
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

allow_all_origins = CORS_ALLOW_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed request_id=%s method=%s path=%s",
            request_id,
            request.method,
            request.url.path,
        )
        raise
    elapsed_ms = (time.perf_counter() - started_at) * 1_000
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request_completed request_id=%s method=%s path=%s status=%d elapsed_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
    )
    return response


@app.exception_handler(AIServiceError)
async def handle_ai_service_error(_: Request, exc: AIServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.public_message}},
    )


@app.exception_handler(ScenarioStateContractError)
async def handle_scenario_state_error(_: Request, exc: ScenarioStateContractError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.public_message}},
    )


@app.exception_handler(BaselineStoreError)
async def handle_baseline_store_error(_: Request, exc: BaselineStoreError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.public_message}},
    )


@app.exception_handler(StarletteHTTPException)
async def handle_http_error(_: Request, exc: StarletteHTTPException):
    if isinstance(exc.detail, dict):
        code = str(exc.detail.get("code") or "HTTP_ERROR")
        message = str(exc.detail.get("message") or "요청을 처리하지 못했습니다.")
    else:
        code = "HTTP_ERROR"
        message = str(exc.detail)
    if 400 <= exc.status_code < 500:
        record_contract_failure("http_request", code)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": code, "message": message}},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_: Request, exc: RequestValidationError):
    record_contract_failure("request_body", "REQUEST_VALIDATION_FAILED")
    details = [
        {
            "location": [str(part) for part in error["loc"]],
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "REQUEST_VALIDATION_FAILED",
                "message": "요청 형식이 API 계약과 일치하지 않습니다.",
                "details": details,
            }
        },
    )


app.include_router(chat_router)
app.include_router(suggest_router)
app.include_router(voice_router)
app.include_router(wordfreq_router)
app.include_router(call_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health/ready")
async def readiness():
    components = {
        "openai": {"ready": bool(OPENAI_API_KEY)},
        "local_nlu": {"ready": HF_LOCAL_MODEL_ENABLED},
        "voice_baseline_security": {
            "ready": len(BASELINE_ID_HMAC_SECRET) >= 32,
        },
        "postgresql": {"ready": await database_is_ready()},
        "ffmpeg": {"ready": shutil.which("ffmpeg") is not None},
    }
    ready = all(component["ready"] for component in components.values())
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "components": components,
        },
    )


@app.get("/")
def root():
    return {
        "name": "MaeumCall AI Server",
        "version": app.version,
        "docs": "/docs",
    }
