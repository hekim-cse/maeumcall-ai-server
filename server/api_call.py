from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from services.call_policy import create_call_plan
from services.flow.registry import get_flow_registration


CALL_SETUP_CONTRACT_VERSION = 1

router = APIRouter(prefix="/call", tags=["call"])


class CallSetupReq(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    contract_version: int = Field(ge=1)
    category: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=100)


class CallSetupResp(BaseModel):
    contract_version: Literal[1]
    scenario_key: str = Field(min_length=3, max_length=200)
    direction: Literal["incoming", "outgoing"]
    who_starts: Literal["agent", "user"]
    delay_ms: int = Field(ge=0, le=3_000)
    opening: str = Field(min_length=1, max_length=500)


@router.post("/setup", response_model=CallSetupResp)
def setup_call(req: CallSetupReq):
    if req.contract_version != CALL_SETUP_CONTRACT_VERSION:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CALL_SETUP_VERSION_UNSUPPORTED",
                "message": "지원하지 않는 통화 준비 계약 버전입니다.",
            },
        )

    registration = get_flow_registration(req.category, req.title)
    if registration is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_SCENARIO",
                "message": "등록되지 않은 카테고리와 제목 조합입니다.",
            },
        )

    plan = create_call_plan(registration.key)
    return CallSetupResp(
        contract_version=CALL_SETUP_CONTRACT_VERSION,
        scenario_key=registration.key,
        direction=plan.direction,
        who_starts="agent",
        delay_ms=plan.delay_ms,
        opening=plan.opening,
    )
