from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import firebase_admin
import httpx
from fastapi import Header
from firebase_admin import auth as firebase_auth

from core.config import (
    AUTH_SUBJECT_HMAC_SECRET,
    FIREBASE_PROJECT_ID,
    KAKAO_APP_ID,
    KAKAO_TOKEN_VERIFY_TIMEOUT,
)

KAKAO_TOKEN_INFO_URL = "https://kapi.kakao.com/v1/user/access_token_info"


class AuthenticationError(RuntimeError):
    def __init__(self, code: str, public_message: str, *, status_code: int) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str


class KakaoTokenVerifier(Protocol):
    async def verify(self, access_token: str) -> str: ...


class FirebaseIdentityProvider(Protocol):
    async def create_custom_token(self, uid: str) -> str: ...

    async def verify_id_token(self, id_token: str) -> str: ...


def _require_secret(secret: str) -> bytes:
    encoded = secret.encode("utf-8")
    if len(encoded) < 32:
        raise AuthenticationError(
            "AUTH_CONFIGURATION_INVALID",
            "사용자 인증 서버 설정이 완료되지 않았습니다.",
            status_code=503,
        )
    return encoded


def derive_internal_uid(kakao_subject: str, secret: str) -> str:
    normalized = kakao_subject.strip()
    if not normalized:
        raise AuthenticationError(
            "KAKAO_IDENTITY_INVALID",
            "카카오 사용자 정보를 확인하지 못했습니다.",
            status_code=401,
        )
    digest = hmac.new(
        _require_secret(secret),
        f"kakao:{normalized}".encode(),
        hashlib.sha256,
    ).digest()
    encoded = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"user_{encoded}"


def validate_kakao_token_info(payload: Mapping[str, Any], *, expected_app_id: str) -> str:
    if str(payload.get("app_id", "")) != expected_app_id:
        raise AuthenticationError(
            "KAKAO_TOKEN_AUDIENCE_MISMATCH",
            "다른 애플리케이션에서 발급된 로그인 정보입니다.",
            status_code=401,
        )
    subject = str(payload.get("id", "")).strip()
    if not subject:
        raise AuthenticationError(
            "AUTH_PROVIDER_RESPONSE_INVALID",
            "로그인 제공자의 응답을 검증하지 못했습니다.",
            status_code=502,
        )
    return subject


def validate_firebase_identity(decoded: Mapping[str, Any]) -> str:
    uid = str(decoded.get("uid") or decoded.get("sub") or "").strip()
    if not uid:
        raise AuthenticationError(
            "FIREBASE_TOKEN_INVALID",
            "로그인 세션에서 사용자 정보를 확인하지 못했습니다.",
            status_code=401,
        )
    if decoded.get("identity_provider") != "kakao":
        raise AuthenticationError(
            "FIREBASE_IDENTITY_PROVIDER_FORBIDDEN",
            "카카오 로그인이 필요한 기능입니다.",
            status_code=403,
        )
    return uid


class KakaoRemoteTokenVerifier:
    def __init__(self, *, app_id: str, timeout_seconds: int) -> None:
        if not app_id.strip():
            raise AuthenticationError(
                "AUTH_CONFIGURATION_INVALID",
                "사용자 인증 서버 설정이 완료되지 않았습니다.",
                status_code=503,
            )
        self._app_id = app_id.strip()
        self._timeout = httpx.Timeout(timeout_seconds)

    async def verify(self, access_token: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    KAKAO_TOKEN_INFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as exc:
            raise AuthenticationError(
                "AUTH_PROVIDER_UNAVAILABLE",
                "로그인 제공자에 연결하지 못했습니다.",
                status_code=503,
            ) from exc

        if response.status_code in {401, 403}:
            raise AuthenticationError(
                "KAKAO_TOKEN_INVALID",
                "카카오 로그인 정보가 만료되었거나 올바르지 않습니다.",
                status_code=401,
            )
        if response.status_code != 200:
            raise AuthenticationError(
                "AUTH_PROVIDER_UNAVAILABLE",
                "로그인 제공자가 요청을 처리하지 못했습니다.",
                status_code=503,
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise AuthenticationError(
                "AUTH_PROVIDER_RESPONSE_INVALID",
                "로그인 제공자의 응답을 검증하지 못했습니다.",
                status_code=502,
            ) from exc
        if not isinstance(payload, Mapping):
            raise AuthenticationError(
                "AUTH_PROVIDER_RESPONSE_INVALID",
                "로그인 제공자의 응답을 검증하지 못했습니다.",
                status_code=502,
            )

        return validate_kakao_token_info(payload, expected_app_id=self._app_id)


class FirebaseAdminIdentityProvider:
    def __init__(self, project_id: str) -> None:
        if not project_id.strip():
            raise AuthenticationError(
                "AUTH_CONFIGURATION_INVALID",
                "사용자 인증 서버 설정이 완료되지 않았습니다.",
                status_code=503,
            )
        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            try:
                self._app = firebase_admin.initialize_app(options={"projectId": project_id.strip()})
            except Exception as exc:
                raise AuthenticationError(
                    "AUTH_CONFIGURATION_INVALID",
                    "Firebase 인증 서버를 초기화하지 못했습니다.",
                    status_code=503,
                ) from exc

    async def create_custom_token(self, uid: str) -> str:
        try:
            token = await asyncio.to_thread(
                firebase_auth.create_custom_token,
                uid,
                {"identity_provider": "kakao"},
                self._app,
            )
        except Exception as exc:
            raise AuthenticationError(
                "AUTH_TOKEN_ISSUE_FAILED",
                "앱 로그인 세션을 생성하지 못했습니다.",
                status_code=503,
            ) from exc
        return token.decode("utf-8") if isinstance(token, bytes) else str(token)

    async def verify_id_token(self, id_token: str) -> str:
        try:
            decoded: Mapping[str, Any] = await asyncio.to_thread(
                firebase_auth.verify_id_token,
                id_token,
                self._app,
                True,
            )
        except Exception as exc:
            raise AuthenticationError(
                "FIREBASE_TOKEN_INVALID",
                "로그인 세션이 만료되었거나 올바르지 않습니다.",
                status_code=401,
            ) from exc
        return validate_firebase_identity(decoded)


class IdentityService:
    def __init__(
        self,
        *,
        kakao_verifier: KakaoTokenVerifier,
        firebase_identity: FirebaseIdentityProvider,
        subject_secret: str,
    ) -> None:
        _require_secret(subject_secret)
        self._kakao_verifier = kakao_verifier
        self._firebase_identity = firebase_identity
        self._subject_secret = subject_secret

    async def exchange_kakao_token(self, access_token: str) -> str:
        subject = await self._kakao_verifier.verify(access_token)
        uid = derive_internal_uid(subject, self._subject_secret)
        return await self._firebase_identity.create_custom_token(uid)

    async def authenticate_firebase_token(self, id_token: str) -> AuthenticatedUser:
        uid = await self._firebase_identity.verify_id_token(id_token)
        return AuthenticatedUser(uid=uid)


@lru_cache(maxsize=1)
def get_identity_service() -> IdentityService:
    return IdentityService(
        kakao_verifier=KakaoRemoteTokenVerifier(
            app_id=KAKAO_APP_ID,
            timeout_seconds=KAKAO_TOKEN_VERIFY_TIMEOUT,
        ),
        firebase_identity=FirebaseAdminIdentityProvider(FIREBASE_PROJECT_ID),
        subject_secret=AUTH_SUBJECT_HMAC_SECRET,
    )


def authentication_configuration_ready() -> bool:
    return bool(
        KAKAO_APP_ID and FIREBASE_PROJECT_ID and len(AUTH_SUBJECT_HMAC_SECRET.encode("utf-8")) >= 32
    )


def parse_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AuthenticationError(
            "AUTHORIZATION_REQUIRED",
            "로그인이 필요한 요청입니다.",
            status_code=401,
        )
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise AuthenticationError(
            "AUTHORIZATION_INVALID",
            "Authorization 헤더가 Bearer 토큰 형식이 아닙니다.",
            status_code=401,
        )
    return token.strip()


async def require_authenticated_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser:
    token = parse_bearer_token(authorization)
    return await get_identity_service().authenticate_firebase_token(token)


async def optional_authenticated_user(
    authorization: str | None = Header(default=None),
) -> AuthenticatedUser | None:
    if authorization is None:
        return None
    token = parse_bearer_token(authorization)
    return await get_identity_service().authenticate_firebase_token(token)
