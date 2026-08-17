import pytest
from fastapi.testclient import TestClient

from main import app
from services.korean_text_analyzer import KoreanTextAnalyzer, KoreanTextAnalyzerError


pytestmark = pytest.mark.unit


def test_word_frequency_accepts_typed_turns():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={
            "turns": [
                {"role": "user", "text": "음 오늘 일정 알려주세요"},
                {"role": "assistant", "text": "오늘 일정은 두 개입니다"},
            ],
            "scope": "user",
        },
    )

    assert response.status_code == 200
    assert response.json()["total_messages"] == 1
    assert response.json()["filler_count"] == 1


def test_word_frequency_uses_morpheme_base_forms_instead_of_whitespace_tokens():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"messages": ["학교에서 공부했고 학교를 좋아합니다"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert ["학교", 2] in body["top_words"]
    assert all("학교에서" != word for word, _ in body["top_words"])


def test_word_frequency_counts_interjections_by_pos_contract():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"messages": ["어 음 병원에 예약하고 싶어요"]},
    )

    assert response.status_code == 200
    assert response.json()["filler_count"] == 2
    assert response.json()["top_fillers"] == [["어", 1], ["음", 1]]


class _FailingTokenizer:
    def tokenize(self, text: str, *, normalize_coda: bool):
        raise RuntimeError("native analyzer failed")


def test_analyzer_exposes_typed_failure_instead_of_whitespace_fallback():
    analyzer = KoreanTextAnalyzer(_FailingTokenizer())

    with pytest.raises(KoreanTextAnalyzerError) as raised:
        analyzer.analyze(["공백 분리로 대체하면 안 됩니다"])

    assert raised.value.code == "KOREAN_TEXT_ANALYSIS_FAILED"


def test_word_frequency_rejects_unregistered_role_instead_of_inferring_it():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"turns": [{"role": "bot", "text": "안녕하세요"}]},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "REQUEST_VALIDATION_FAILED"


def test_word_frequency_rejects_ambiguous_input_sources():
    response = TestClient(app).post(
        "/analysis/wordfreq",
        json={"messages": ["안녕하세요"], "turns": []},
    )

    assert response.status_code == 422


def test_word_frequency_rejects_duplicate_category_keys():
    response = TestClient(app).post(
        "/analysis/wordfreq/by-category",
        json={
            "items": [
                {"category": "예약", "messages": ["병원 예약"]},
                {"category": "예약", "messages": ["식당 예약"]},
            ]
        },
    )

    assert response.status_code == 422
