from __future__ import annotations

import random
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from services.flow.common.state_contract import build_scenario_key
from services.flow.registry import FLOW_REGISTRY

NEUTRAL_OUTGOING_OPENINGS = (
    "네, 전화 받았습니다. 무슨 용건이신가요?",
    "네, 연결됐습니다. 어떤 일로 전화하셨죠?",
    "네. 어떤 용건으로 전화 주셨을까요?",
)

COMPANY_INCOMING_OPENINGS = {
    build_scenario_key("회사", "보고서 제출"): (
        "전산팀입니다. 이번 주 수요일까지 제출하기로 한 보고서, 언제까지 올리실 수 있습니까?",
        "전산팀입니다. 보고서 마감 일정 확인 건입니다. ETA를 구체적으로 말씀해 주십시오.",
        "전산팀입니다. 보고서 마감 건으로 연락드렸습니다. 오늘 중 제출 가능합니까?",
        "전산팀입니다. 보고서 제출 일정 확인하려고 연락드렸습니다. 정확한 제출 시점 말씀해 주세요.",
        "전산팀입니다. 보고서 제출 지연 사유와 보완 일정 제출 바랍니다.",
    ),
    build_scenario_key("회사", "진행상황 보고"): (
        "전산팀입니다. 이번 프로젝트 진행 현황 간단히 브리핑해 주시죠. 지금 바로 가능합니까?",
        "전산팀입니다. 진행 상황 업데이트 필요합니다. 핵심만 바로 보고해 주세요.",
        "전산팀입니다. 현재까지 달성률과 리스크 요인 짚어서 보고해 주세요.",
    ),
    build_scenario_key("회사", "회의 일정 조율"): (
        "전산팀입니다. 오늘 4시 회의를 5시로 미루고자 합니다. 조정 가능합니까?",
        "전산팀입니다. 회의 시간을 1시간 뒤로 이동하려 합니다. 가능 여부 지금 확인해 주세요.",
        "전산팀입니다. 회의 조정 건입니다. 5시로 재조정 문제없습니까?",
    ),
}


@dataclass(frozen=True)
class CallPolicy:
    direction: Literal["incoming", "outgoing"]
    delay_options_ms: tuple[int, ...]
    openings: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.delay_options_ms or any(delay < 0 for delay in self.delay_options_ms):
            raise ValueError("call policy delay options must be non-negative")
        if not self.openings or any(not opening.strip() for opening in self.openings):
            raise ValueError("call policy openings must not be empty")


@dataclass(frozen=True)
class CallPlan:
    direction: Literal["incoming", "outgoing"]
    delay_ms: int
    opening: str


def _build_call_policy_registry() -> Mapping[str, CallPolicy]:
    unknown_incoming_keys = set(COMPANY_INCOMING_OPENINGS) - set(FLOW_REGISTRY)
    if unknown_incoming_keys:
        raise RuntimeError(
            f"incoming call policies are not registered scenarios: {sorted(unknown_incoming_keys)}"
        )

    policies: dict[str, CallPolicy] = {}
    for scenario_key in FLOW_REGISTRY:
        incoming_openings = COMPANY_INCOMING_OPENINGS.get(scenario_key)
        policies[scenario_key] = (
            CallPolicy(
                direction="incoming",
                delay_options_ms=(0,),
                openings=incoming_openings,
            )
            if incoming_openings is not None
            else CallPolicy(
                direction="outgoing",
                delay_options_ms=(1_000, 2_000, 3_000),
                openings=NEUTRAL_OUTGOING_OPENINGS,
            )
        )
    return MappingProxyType(policies)


CALL_POLICY_REGISTRY = _build_call_policy_registry()


def create_call_plan(scenario_key: str) -> CallPlan:
    try:
        policy = CALL_POLICY_REGISTRY[scenario_key]
    except KeyError as exc:
        raise ValueError("call scenario must be registered") from exc
    return CallPlan(
        direction=policy.direction,
        delay_ms=random.choice(policy.delay_options_ms),
        opening=random.choice(policy.openings),
    )
