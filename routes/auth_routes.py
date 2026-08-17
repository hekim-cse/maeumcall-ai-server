from __future__ import annotations

from fastapi import APIRouter, Header
from pydantic import BaseModel, ConfigDict, Field

from core.auth import IdentityService, get_identity_service, parse_bearer_token

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    firebaseCustomToken: str = Field(min_length=1)


@router.post("/kakao/exchange", response_model=AuthSessionResponse)
async def exchange_kakao_session(
    authorization: str | None = Header(default=None),
) -> AuthSessionResponse:
    kakao_access_token = parse_bearer_token(authorization)
    identity_service: IdentityService = get_identity_service()
    custom_token = await identity_service.exchange_kakao_token(kakao_access_token)
    return AuthSessionResponse(firebaseCustomToken=custom_token)
