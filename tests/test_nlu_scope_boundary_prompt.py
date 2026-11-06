"""Every detailed NLU graph applies the shared scope decision before extraction."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.structured_nlu.ai_heldout import AIHeldoutCase, AIHeldoutRequestPolicy
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from llm.structured_output import SCOPE_BOUNDARY_GUIDANCE
from scripts.run_ai_heldout_pair import _run_case
from services.flow.professor.appointment.llm_structured import (
    build_professor_appointment_analysis_prompt,
)

REVIEWED = (
    Path(__file__).resolve().parents[1]
    / "evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json"
)
_cases = [AIHeldoutCase.model_validate(case) for case in json.loads(REVIEWED.read_text())["cases"]]
CASES = tuple(case for case in _cases if "hard_negative" in case.tags)
POLICY = AIHeldoutRequestPolicy.model_validate_json(
    REVIEWED.parent.joinpath("q4-q5-request-policy.v1.json").read_bytes()
)
EXPECTED_PURPOSES = {
    "고객센터:a/s 접수": "제품 고장 증상을 받아 점검 또는 수리 접수를 진행하는 것",
    "고객센터:요금/약정 상담": "현재 요금 청구, 요금제 또는 약정에 관한 상담을 진행하는 것",
    "고객센터:인터넷/통화 문제 문의": "인터넷 또는 통화 장애의 증상을 받아 점검과 해결 절차를 진행하는 것",
    "교수님:결석 사유 전달": "학생의 결석 사실과 사유를 교수님께 전달하는 것",
    "교수님:과제 문의": "수업 과제의 내용, 제출 또는 수행 방법을 문의하는 것",
    "교수님:면담 예약": "교수님과의 면담 일정을 예약하는 것",
    "배달:배달 지연 문의": "진행 중인 주문의 지연 상황, 위치 또는 도착 예상 정보를 확인하는 것",
    "배달:주문 변경": "진행 중인 주문의 메뉴, 수량, 옵션 또는 배달 정보를 변경하는 것",
    "배달:환불/재배달 문의": "현재 주문의 누락·오배송·품질·미수령 문제에 대한 처리 상담을 진행하는 것",
    "시청:대형폐기물 배출": "대형폐기물의 신고, 수수료, 배출 장소와 수거 절차를 안내하는 것",
    "시청:여권 발급 문의": "여권의 신규 발급 또는 재발급에 필요한 절차를 안내하는 것",
    "시청:주민등록 등본 문의": "주민등록등본 또는 초본의 발급 절차를 안내하는 것",
    "예약:미용실 예약": "미용실 시술 예약을 진행하는 것",
    "예약:병원 예약": "병원 진료 예약을 진행하는 것",
    "예약:스터디룸 예약": "스터디룸 이용 시간을 예약하는 것",
    "예약:식당 예약": "식당 좌석을 예약하는 것",
}


@pytest.mark.parametrize("case", CASES, ids=lambda case: case.id)
def test_scope_boundary_instruction_reaches_each_live_analyzer(case: AIHeldoutCase) -> None:
    observed_messages: list[list[dict[str, str]]] = []

    def capture(_endpoint, _model_id, messages, _policy):
        observed_messages.append(messages)
        return "{}"

    _run_case(
        case,
        endpoint="http://127.0.0.1:18080/v1/chat/completions",
        model_id="offline-test",
        policy=POLICY,
        completion_post=capture,
    )

    assert observed_messages
    assert all(SCOPE_BOUNDARY_GUIDANCE in messages[0]["content"] for messages in observed_messages)
    assert all(
        f"현재 지원 목적: {EXPECTED_PURPOSES[case.scenario_key]}" in messages[0]["content"]
        for messages in observed_messages
    )
    if case.scenario_key == "고객센터:a/s 접수":
        assert all(
            "안전 처리를 우선한다" in messages[0]["content"] for messages in observed_messages
        )


def test_shared_workflows_declare_their_supported_purpose() -> None:
    specs = (
        contract.workflow_spec
        for contract in EVALUATION_CONTRACTS.values()
        if contract.workflow_spec is not None
    )
    assert all(spec.scope_purpose and spec.scope_purpose.strip() for spec in specs)


def test_appointment_prompt_preserves_explicit_purpose_and_missing_name() -> None:
    prompt = build_professor_appointment_analysis_prompt(
        conversation_state="greeting",
        user_message="교환학생 지원 계획을 상의하고 싶습니다.",
    )
    assert "사용자가 말한 면담 목적을 그대로 보존" in prompt
    assert "이름이 없으면 null" in prompt
    assert "자리표시자를 만들지 않음" in prompt
