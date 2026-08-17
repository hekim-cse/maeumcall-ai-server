from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from core.auth import (
    AuthenticationError,
    IdentityService,
    derive_internal_uid,
    validate_kakao_token_info,
    validate_firebase_identity,
)
from main import app


pytestmark = pytest.mark.unit


class KakaoVerifierDouble:
    def __init__(self, subject: str = "123456789") -> None:
        self.subject = subject
        self.tokens: list[str] = []

    async def verify(self, access_token: str) -> str:
        self.tokens.append(access_token)
        return self.subject


class FirebaseIdentityDouble:
    def __init__(self) -> None:
        self.issued_uids: list[str] = []
        self.verified_tokens: list[str] = []

    async def create_custom_token(self, uid: str) -> str:
        self.issued_uids.append(uid)
        return f"firebase-custom-token:{uid}"

    async def verify_id_token(self, id_token: str) -> str:
        self.verified_tokens.append(id_token)
        return "verified-firebase-user"


def _identity_service() -> tuple[IdentityService, KakaoVerifierDouble, FirebaseIdentityDouble]:
    kakao = KakaoVerifierDouble()
    firebase = FirebaseIdentityDouble()
    service = IdentityService(
        kakao_verifier=kakao,
        firebase_identity=firebase,
        subject_secret="authentication-test-secret-32-bytes-minimum",
    )
    return service, kakao, firebase


def test_internal_uid_is_stable_and_does_not_contain_kakao_subject():
    secret = "authentication-test-secret-32-bytes-minimum"

    first = derive_internal_uid("123456789", secret)
    second = derive_internal_uid("123456789", secret)

    assert first == second
    assert first.startswith("user_")
    assert "123456789" not in first


def test_short_identity_secret_is_rejected():
    with pytest.raises(AuthenticationError) as error:
        derive_internal_uid("123456789", "short")

    assert error.value.code == "AUTH_CONFIGURATION_INVALID"


def test_kakao_token_info_requires_the_configured_application():
    with pytest.raises(AuthenticationError) as error:
        validate_kakao_token_info(
            {"app_id": 999, "id": 123456789}, expected_app_id="100"
        )

    assert error.value.code == "KAKAO_TOKEN_AUDIENCE_MISMATCH"


def test_kakao_token_info_returns_the_verified_subject():
    subject = validate_kakao_token_info(
        {"app_id": 100, "id": 123456789}, expected_app_id="100"
    )

    assert subject == "123456789"


def test_firebase_identity_requires_kakao_provider_claim():
    with pytest.raises(AuthenticationError) as error:
        validate_firebase_identity({"uid": "anonymous-user"})

    assert error.value.code == "FIREBASE_IDENTITY_PROVIDER_FORBIDDEN"
    assert error.value.status_code == 403


def test_firebase_identity_returns_uid_for_kakao_session():
    assert (
        validate_firebase_identity(
            {"uid": "internal-user", "identity_provider": "kakao"}
        )
        == "internal-user"
    )


def test_kakao_exchange_returns_firebase_custom_token(monkeypatch):
    service, kakao, firebase = _identity_service()
    monkeypatch.setattr("routes.auth_routes.get_identity_service", lambda: service)
    response = TestClient(app).post(
        "/auth/kakao/exchange",
        headers={"Authorization": "Bearer kakao-access-token"},
    )

    assert response.status_code == 200
    assert kakao.tokens == ["kakao-access-token"]
    assert firebase.issued_uids == [
        derive_internal_uid(
            "123456789", "authentication-test-secret-32-bytes-minimum"
        )
    ]
    assert response.json()["firebaseCustomToken"].startswith(
        "firebase-custom-token:user_"
    )


def test_kakao_exchange_requires_bearer_token():
    response = TestClient(app).post("/auth/kakao/exchange")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "AUTHORIZATION_REQUIRED"


def test_voice_baseline_requires_authenticated_session():
    response = TestClient(app).get("/voice/baseline")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHORIZATION_REQUIRED"


def test_voice_calibration_requires_authenticated_session():
    response = TestClient(app).post(
        "/voice/analyze",
        data={"mode": "calibrate"},
        files={"file": ("voice.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHORIZATION_REQUIRED"
