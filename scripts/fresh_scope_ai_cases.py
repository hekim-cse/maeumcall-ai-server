"""Load fresh AI-authored scope cases without promoting draft labels to truth."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = ROOT / "docs/portfolio/nlu_scope_fresh_ai_review.md"
FIELD_DRAFT = (
    ROOT / "evals/structured_nlu/data/exploratory/fresh-scope-ai-field-draft-2026-11-05.json"
)
EXPECTED_IDS = [f"F{number:02}" for number in range(1, 33)]
ROW = re.compile(r"^\| (F\d{2}) \| ([^|]+) \| ([^|]+) \| `([a-z_]+)` \|$")
DISPLAY_NAME_BY_SCENARIO = {
    "고객센터:a/s 접수": "고객센터 A/S 접수",
    "고객센터:요금/약정 상담": "고객센터 요금·약정 상담",
    "고객센터:인터넷/통화 문제 문의": "고객센터 인터넷·통화 문제",
    "교수님:결석 사유 전달": "교수님 결석 사유 전달",
    "교수님:과제 문의": "교수님 과제 문의",
    "교수님:면담 예약": "교수님 면담 예약",
    "배달:배달 지연 문의": "배달 지연 문의",
    "배달:주문 변경": "배달 주문 변경",
    "배달:환불/재배달 문의": "배달 환불·재배달 문의",
    "시청:대형폐기물 배출": "시청 대형폐기물 배출",
    "시청:여권 발급 문의": "시청 여권 발급 문의",
    "시청:주민등록 등본 문의": "시청 주민등록 등본 문의",
    "예약:미용실 예약": "미용실 예약",
    "예약:병원 예약": "병원 예약",
    "예약:스터디룸 예약": "스터디룸 예약",
    "예약:식당 예약": "식당 예약",
}


def load_cases(
    sentences_path: Path = SENTENCES,
    fields_path: Path = FIELD_DRAFT,
) -> list[dict]:
    sentence_source = sentences_path.read_text(encoding="utf-8")
    if "사용자 탐색용 채택" not in sentence_source:
        raise ValueError("sentence draft does not record exploratory acceptance")
    rows = [
        match.groups() for line in sentence_source.splitlines() if (match := ROW.fullmatch(line))
    ]
    if [row[0] for row in rows] != EXPECTED_IDS:
        raise ValueError("sentence draft must contain exactly F01 through F32")
    if set(DISPLAY_NAME_BY_SCENARIO) != set(EVALUATION_CONTRACTS):
        raise ValueError("scenario display mapping differs from live contracts")
    messages = [row[2].strip() for row in rows]
    if any(not message for message in messages) or len(set(messages)) != len(messages):
        raise ValueError("exploratory messages must be nonempty and unique")

    source = json.loads(fields_path.read_text(encoding="utf-8"))
    if (
        source.get("kind") != "exploratory_fresh_scope_ai_field_draft_v1"
        or source.get("provenance") != "ai_assisted_unreviewed"
        or source.get("sentence_action_review") != "user_accepted_for_exploration_2026-11-05"
        or source.get("normalized_value_status") != "ai_draft_user_reviewed_for_exploration"
        or source.get("normalized_value_review")
        != "user_changed_F17_resolution_preference_and_F29_date_2026-11-05"
        or source.get("not_official_test") is not True
    ):
        raise ValueError("field source must remain AI-assisted exploratory data")
    pairs = source.get("pairs")
    if not isinstance(pairs, list) or len(pairs) != 16:
        raise ValueError("field source requires one pair per detailed scenario")
    if {pair.get("scenario_key") for pair in pairs} != set(EVALUATION_CONTRACTS):
        raise ValueError("field source must cover all 16 detailed scenarios")
    pair_by_id = {}
    for pair in pairs:
        positive_id = pair["positive_id"]
        negative_id = pair["negative_id"]
        if positive_id in pair_by_id or negative_id in pair_by_id:
            raise ValueError("case IDs must belong to exactly one pair")
        pair_by_id[positive_id] = (pair, True)
        pair_by_id[negative_id] = (pair, False)
    if set(pair_by_id) != set(EXPECTED_IDS):
        raise ValueError("field source case IDs differ from sentence draft")

    cases = []
    for case_id, display_name, message, action in rows:
        pair, positive = pair_by_id[case_id]
        if positive != (int(case_id[1:]) % 2 == 1):
            raise ValueError(f"pair polarity differs from case ID: {case_id}")
        if display_name.strip() != DISPLAY_NAME_BY_SCENARIO[pair["scenario_key"]]:
            raise ValueError(f"scenario display name differs from case assignment: {case_id}")
        contract = EVALUATION_CONTRACTS[pair["scenario_key"]]
        state = contract.workflow_spec.collecting_state if contract.workflow_spec else "greeting"
        current_fields = dict.fromkeys(contract.field_names) if contract.uses_current_fields else {}
        fields = dict.fromkeys(contract.field_names)
        supplied = pair["positive_fields"] if positive else {}
        if not isinstance(supplied, dict) or not set(supplied) <= set(fields):
            raise ValueError(f"unknown draft field in {case_id}")
        if positive and not supplied:
            raise ValueError(f"positive case requires a field draft: {case_id}")
        if any(
            value is not None and (not isinstance(value, str) or not value.strip())
            for value in supplied.values()
        ):
            raise ValueError(f"field draft values must be nonblank strings or null: {case_id}")
        fields.update(supplied)
        intent = (
            None
            if action == "unknown" and None in contract.allowed_intents
            else next(iter(contract.allowed_intents - {None}))
        )
        contract.validate_prediction(
            intent=intent,
            fields=fields,
            user_action=action,
            change_field=None,
            conversation_state=state,
            current_fields=current_fields,
        )
        cases.append(
            {
                "id": case_id,
                "scenario_key": pair["scenario_key"],
                "conversation_state": state,
                "current_fields": current_fields,
                "offered_alternative_times": [],
                "user_message": message.strip(),
                "labels": {
                    "intent": intent,
                    "user_action": action,
                    "change_field": None,
                    "fields": {
                        name: None if value is None else {"accepted_values": [value]}
                        for name, value in fields.items()
                    },
                },
            }
        )
    return cases
