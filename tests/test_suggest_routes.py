import pytest
from fastapi.testclient import TestClient

from main import app
from routes.suggest_routes import _suggest_prompt, _validate_suggestions
from schemas.chat_models import SuggestRequest


pytestmark = pytest.mark.unit


def test_company_suggest_prompt_keeps_business_rules():
    prompt = _suggest_prompt(
        SuggestRequest(category="회사", title="보고서 제출", lastAgentUtterance="몇 시까지 가능합니까?")
    )

    assert "격식/존댓말" in prompt
    assert "구체 정보" in prompt


def test_suggestion_contract_requires_three_unique_items():
    with pytest.raises(ValueError):
        _validate_suggestions({"suggestions": ["네, 확인하겠습니다."]})

    suggestions = _validate_suggestions(
        {"suggestions": ["네, 확인하겠습니다.", "일정을 알려주세요.", "다른 방법도 확인할게요."]}
    )
    assert len(suggestions) == 3
    assert len(set(suggestions)) == 3


def test_suggest_rejects_unregistered_scenario():
    response = TestClient(app).post(
        "/suggest",
        json={
            "category": "회사",
            "title": "등록되지 않은 업무",
            "lastAgentUtterance": "말씀해 주세요.",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "UNSUPPORTED_SCENARIO"


def test_improve_rejects_unregistered_category_before_model_call():
    response = TestClient(app).post(
        "/improve",
        json={
            "category": "기타",
            "messages": [{"role": "user", "text": "안녕하세요"}],
        },
    )

    assert response.status_code == 422
