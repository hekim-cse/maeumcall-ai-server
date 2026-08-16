# schemas/chat_models.py
from __future__ import annotations
from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel

# 공통
Role = Literal["user", "assistant", "system", "ai"]  # ← 3번과 연결
ImproveCategory = Literal[
    "가족",
    "친구",
    "연인",
    "회사",
    "예약",
    "교수님",
    "고객센터",
    "시청",
    "배달",
    "일반",
]

# === 대화 생성 ===
class ChatRequest(BaseModel):
    category: str
    nickname: Optional[str] = None
    title: str
    description: str
    userMessage: str
    turns: Optional[List[Dict[str, str]]] = None
    history: Optional[List[Dict[str, str]]] = None

    # LangGraph 상태 기반 시나리오용
    conversationState: Optional[str] = None
    scenarioState: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    etiquetteTip: Optional[str] = None

    # LangGraph 상태 기반 응답용
    recommendedReplies: Optional[List[str]] = None
    conversationState: Optional[str] = None
    shouldEndCall: Optional[bool] = None
    scenarioState: Optional[Dict[str, Any]] = None

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
    category: Optional[ImproveCategory] = None

class ImproveResponse(BaseModel):
    # user 메시지 위치에만 개선문이 있고 나머지는 None
    improved: List[Optional[str]]
    # user 메시지 위치에만 태그 배열이 있고 나머지는 None
    tags: List[Optional[List[str]]]
