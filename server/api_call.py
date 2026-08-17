# -*- coding: utf-8 -*-
from fastapi import APIRouter
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from services.call_policy import is_incoming_scenario, random_connect_delay_ms, choose_opening

router = APIRouter(prefix="/call", tags=["call"])

class CallSetupReq(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)

class CallSetupResp(BaseModel):
    direction: Literal["incoming", "outgoing"]
    who_starts: Literal["agent", "user"]
    delay_ms: int = Field(ge=0, le=3_000)
    opening: str = Field(min_length=1, max_length=500)

@router.post("/setup", response_model=CallSetupResp)
def setup_call(req: CallSetupReq):
    incoming = is_incoming_scenario(req.category, req.title)
    direction = "incoming" if incoming else "outgoing"
    delay_ms = 0 if incoming else random_connect_delay_ms()
    # ✅ 수신/발신에 따라 다른 오프닝 생성
    opening = choose_opening(req.category, req.title, incoming=incoming)
    who_starts = "agent"

    return CallSetupResp(
        direction=direction,
        who_starts=who_starts,
        delay_ms=delay_ms,
        opening=opening,
    )
