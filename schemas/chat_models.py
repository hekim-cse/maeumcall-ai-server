# schemas/chat_models.py
from __future__ import annotations
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 공통
Role = Literal["user", "assistant", "system", "ai"]
ConversationRole = Literal["user", "assistant"]
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

class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConversationTurn(APIModel):
    role: ConversationRole
    text: str = Field(min_length=1, max_length=4_000)


# === 대화 생성 ===
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=50)
    nickname: Optional[str] = Field(default=None, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=2_000)
    userMessage: str = Field(min_length=1, max_length=4_000)
    turns: Optional[List[ConversationTurn]] = Field(default=None, max_length=100)
    history: Optional[List[ConversationTurn]] = Field(default=None, max_length=100)

    # LangGraph 상태 기반 시나리오용
    conversationState: Optional[str] = Field(default=None, min_length=1, max_length=100)
    scenarioState: Optional[Dict[str, Any]] = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def require_one_history_field(self) -> "ChatRequest":
        if self.turns is not None and self.history is not None:
            raise ValueError("turns and history cannot be sent together")
        return self

    def serialized_history(self) -> List[Dict[str, str]]:
        turns = self.history if self.history is not None else self.turns
        return [turn.model_dump() for turn in (turns or [])]


class ChatResponse(APIModel):
    response: str = Field(min_length=1, max_length=4_000)
    etiquetteTip: Optional[str] = Field(default=None, max_length=1_000)

    # LangGraph 상태 기반 응답용
    recommendedReplies: List[str] = Field(max_length=10)
    conversationState: str = Field(min_length=1, max_length=100)
    shouldEndCall: bool
    scenarioState: Dict[str, Any]

# === 짧은 제안(suggest) ===
class SuggestRequest(APIModel):
    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)
    lastAgentUtterance: str = Field(min_length=1, max_length=4_000)

class SuggestResponse(APIModel):
    suggestions: List[str] = Field(min_length=3, max_length=3)

# === 개선(improve) ===
class ChatMessage(APIModel):
    role: Role
    text: str = Field(max_length=4_000)

class ImproveRequest(APIModel):
    messages: List[ChatMessage] = Field(min_length=1, max_length=100)
    category: Optional[ImproveCategory] = None

class ImproveResponse(APIModel):
    # user 메시지 위치에만 개선문이 있고 나머지는 None
    improved: List[Optional[str]]
    # user 메시지 위치에만 태그 배열이 있고 나머지는 None
    tags: List[Optional[List[str]]]
