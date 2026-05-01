# -*- coding: utf-8 -*-
from fastapi import APIRouter
from pydantic import BaseModel
from services.call_policy import is_incoming_scenario, random_connect_delay_ms, choose_opening

router = APIRouter(prefix="/call", tags=["call"])

class CallSetupReq(BaseModel):
    category: str
    title: str

class CallSetupResp(BaseModel):
    direction: str          # "incoming" | "outgoing"
    who_starts: str         # "agent" | "user"
    delay_ms: int           # 발신일 때 1000~3000, 수신이면 0
    opening: str            # 첫 멘트

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