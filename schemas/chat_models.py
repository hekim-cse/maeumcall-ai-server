# schemas/chat_models.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel

# 공통
Role = Literal["user", "assistant", "system", "ai"]  # ← 3번과 연결

# === 대화 생성 ===
class ChatRequest(BaseModel):
    category: str
    nickname: Optional[str] = None    # ⬅️ 추가
    title: str
    description: str
    userMessage: str
    turns: Optional[List[Dict[str, str]]] = None
    history: Optional[List[Dict[str, str]]] = None

class ChatResponse(BaseModel):
    response: str
    etiquetteTip: Optional[str] = None  # ✅ 추가

# === 짧은 제안(suggest) ===
class SuggestRequest(BaseModel):
    category: str
    title: str
    lastAgentUtterance: str

class SuggestResponse(BaseModel):
    suggestions: List[str]

# === 개선(improve) ===
class ChatMessage(BaseModel):
    role: Role
    text: str

class ImproveRequest(BaseModel):
    messages: List[ChatMessage]
    # 선택: 친구/가족/교수님/직장상사/상담원 등 카테고리
    category: Optional[str] = None

class ImproveResponse(BaseModel):
    # user 메시지 위치에만 개선문이 있고 나머지는 None
    improved: List[Optional[str]]
    # user 메시지 위치에만 태그 배열이 있고 나머지는 None
    tags: List[Optional[List[str]]]