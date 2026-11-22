"""Frozen-input construction for a two-case candidate-ID development probe."""

from __future__ import annotations

from functools import lru_cache

from kiwipiepy import Kiwi

from experiments.as_safety_atomic_edges_v4 import run as v4
from experiments.as_safety_atomic_edges_v5 import run as v5
from experiments.as_safety_atomic_edges_v10.candidate_contract import (
    CandidateCatalog,
    nominal_catalog,
)
from experiments.as_safety_v2.transport import RequestPolicy

CASE_ORDER = ("PC01", "NC01")
_PROMPT_BOUNDARY = "E와 연결된 주체 또는 위치 B의 짧은 원문 구절을 subject_span에 인용하세요. "


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    return Kiwi()


def cases() -> dict[str, dict]:
    """Load already reviewed, already exposed development controls."""
    return v5._load_cases(v5.DATA.read_bytes())


def catalog(case: dict) -> CandidateCatalog:
    return nominal_catalog(case["user_message"], _kiwi())


def messages(case: dict, selected: CandidateCatalog) -> list[dict[str, str]]:
    """Keep A/E context while removing the incompatible free-quote instruction."""
    event = {"event_span": case["event_span"], "occurrence": case["occurrence"]}
    original = v4.messages(case, event, "variant")
    user = original[1]["content"]
    if user.count(_PROMPT_BOUNDARY) != 1:
        raise ValueError("source context prompt changed")
    context = user.split(_PROMPT_BOUNDARY, 1)[0]
    rows = "\n".join(
        f"{item.id} | {item.clause_index}번 | {item.quote}" for item in selected.candidates
    )
    instruction = (
        "아래 후보는 원문에서 자동 생성했으며 정답 표시가 아닙니다. "
        "검수된 위험 사건 E의 실제 물리적 출처를 확인할 수 있으면 후보 ID 하나만 candidate_id로 선택하세요. "
        "event_subject_kind는 subject(명시 주체), location(발생 위치), "
        "implicit(앞선 문맥의 주체), unresolved(확인 불가) 중 하나입니다. "
        "출처를 확인할 수 없으면 candidate_id=null, event_subject_kind=unresolved로 반환하세요. "
        "후보가 있어도 사건과 연결할 수 없으면 공란으로 보류하세요. "
        "원문 구절을 출력하지 말고 candidate_id와 event_subject_kind 두 키의 JSON 객체만 반환하세요. "
        "B가 접수 제품 A에 속하는지와 최종 안전 경로는 판단하지 마세요.\n"
    )
    return [original[0], {"role": "user", "content": context + instruction + rows}]


def request_bytes(case: dict, policy: RequestPolicy) -> bytes:
    selected = catalog(case)
    return v4.request_bytes(messages(case, selected), selected.schema(), policy, "variant")
