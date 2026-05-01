# 📄 main.py
from __future__ import annotations
import os
from pathlib import Path

# 1) .env를 *가장 먼저* 로드
from dotenv import load_dotenv, find_dotenv
from typing import Optional

# (선택) 로딩 확인 로그
print("[env] OPENAI_API_KEY loaded? ", bool(os.getenv("OPENAI_API_KEY")))

# 2) 이제 FastAPI/라우터들을 임포트
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

from routes.chat_routes import router as chat_router
from routes.suggest_routes import (
    router as suggest_router,
    router_compat as suggest_router_compat,  # ← 추가
)
from routes.voice_routes import router as voice_router
from routes.voice_routes import analyze_audio_endpoint  # 레거시 별칭용
from routes.wordfreq_router import router as wordfreq_router
from server.api_call import router as call_router

# 3) 앱 생성
app = FastAPI(
    title="TalkSim Server",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# 4) CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5) 라우터 등록
app.include_router(chat_router)
app.include_router(suggest_router)         # /chat/suggest, /chat/improve
app.include_router(suggest_router_compat)  # /suggest, /improve
app.include_router(voice_router)
app.include_router(wordfreq_router)
app.include_router(call_router)

# 6) 헬스체크
@app.get("/health")
def health():
    return {"ok": True}

@app.get("/")
def root():
    return {"message": "TalkSim backend. See /docs"}

# 7) 레거시 업로드 엔드포인트(유지 시)
@app.post("/analyze", include_in_schema=False)
async def analyze_legacy(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None),
    mode: str = Form("normal"),
    strategy: str = Form("welford"),
):
    return await analyze_audio_endpoint(file=file, user_id=user_id, mode=mode, strategy=strategy)