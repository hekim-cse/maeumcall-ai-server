# 📄 main.py
from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from core.config import CORS_ALLOW_ORIGINS
from routes.chat_routes import router as chat_router
from routes.suggest_routes import (
    router as suggest_router,
    router_compat as suggest_router_compat,  # ← 추가
)
from routes.voice_routes import router as voice_router
from routes.voice_routes import analyze_audio_endpoint  # 레거시 별칭용
from routes.wordfreq_router import router as wordfreq_router
from server.api_call import router as call_router
from llm.errors import AIServiceError

app = FastAPI(
    title="MaeumCall AI Server",
    description=(
        "마음콜의 고도화 프로젝트: LangGraph 기반 상태 관리, 검증 가능한 "
        "응답 생성, 통화 음성 분석을 제공하는 AI 서버"
    ),
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

allow_all_origins = CORS_ALLOW_ORIGINS == ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=not allow_all_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AIServiceError)
async def handle_ai_service_error(_: Request, exc: AIServiceError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.public_message}},
    )

app.include_router(chat_router)
app.include_router(suggest_router)         # /chat/suggest, /chat/improve
app.include_router(suggest_router_compat)  # /suggest, /improve
app.include_router(voice_router)
app.include_router(wordfreq_router)
app.include_router(call_router)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {
        "name": "MaeumCall AI Server",
        "version": app.version,
        "docs": "/docs",
    }

@app.post("/analyze", include_in_schema=False)
async def analyze_legacy(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    mode: str = Form("normal"),
    strategy: str = Form("simple"),
):
    return await analyze_audio_endpoint(file=file, user_id=user_id, mode=mode, strategy=strategy)
