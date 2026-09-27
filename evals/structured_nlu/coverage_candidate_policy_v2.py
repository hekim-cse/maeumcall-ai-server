from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.semantics import DifficultyTag

FieldValue = tuple[str, ...] | None
ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV2:
    slug: str
    scenario_key: str
    target_field: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: str
    fields: tuple[tuple[str, FieldValue], ...]
    tags: tuple[DifficultyTag, ...]
    projected_obligations: tuple[ObligationSpec, ...]


def _obligations(state: str, field: str, option: str | None) -> tuple[ObligationSpec, ...]:
    values: list[ObligationSpec] = [
        (CoverageDimension.ACTION_FIELD_ABSENT, f"change_detail->{field}"),
        (CoverageDimension.CHANGE_FIELD, field),
        (
            CoverageDimension.CURRENT_DELTA_RELATION,
            f"{field}->current_value_not_reemitted",
        ),
        (CoverageDimension.CURRENT_DELTA_RELATION, f"{field}->existing_value_cleared"),
        (CoverageDimension.CURRENT_FIELD_PRESENT, field),
        (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "correction"),
        (CoverageDimension.STATE_ACTION, f"{state}->change_detail"),
    ]
    if option is not None:
        values.append((CoverageDimension.CURRENT_FIELD_OPTION, f"{field}={option}"))
    return tuple(sorted(values, key=lambda item: (item[0].value, item[1])))


_CORRECTION = (DifficultyTag.CORRECTION,)

COVERAGE_CANDIDATE_SPECS_V2 = MappingProxyType(
    {
        "support-plan-consent-scope-clear": CoverageCandidateSpecV2(
            slug="support-plan-consent-scope-clear",
            scenario_key="고객센터:요금/약정 상담",
            target_field="consent_scope",
            conversation_state="collecting_plan_contract",
            current_fields=(
                ("inquiry_type", "billing"),
                ("current_service", "0청년 요금제"),
                ("consultation_goal", None),
                ("consent_scope", "authenticated_lookup"),
            ),
            offered_alternative_times=(),
            user_message="가입 정보 조회 동의는 취소할게요.",
            intent="plan_contract_consultation",
            user_action="change_detail",
            change_field="consent_scope",
            fields=(
                ("inquiry_type", None),
                ("current_service", None),
                ("consultation_goal", None),
                ("consent_scope", None),
            ),
            tags=_CORRECTION,
            projected_obligations=_obligations(
                "collecting_plan_contract",
                "consent_scope",
                "authenticated_lookup",
            ),
        ),
        "delivery-change-unavailable-preference-clear": CoverageCandidateSpecV2(
            slug="delivery-change-unavailable-preference-clear",
            scenario_key="배달:주문 변경",
            target_field="unavailable_preference",
            conversation_state="collecting_order_change",
            current_fields=(
                ("order_number", "별빛아파트 301호"),
                ("change_type", "contact"),
                ("requested_change", None),
                ("unavailable_preference", "agent_handoff"),
            ),
            offered_alternative_times=(),
            user_message="변경이 안 될 때 상담원 연결 요청은 취소할게요.",
            intent="delivery_order_change",
            user_action="change_detail",
            change_field="unavailable_preference",
            fields=(
                ("order_number", None),
                ("change_type", None),
                ("requested_change", None),
                ("unavailable_preference", None),
            ),
            tags=_CORRECTION,
            projected_obligations=_obligations(
                "collecting_order_change",
                "unavailable_preference",
                "agent_handoff",
            ),
        ),
        "city-bulky-waste-quantity-clear": CoverageCandidateSpecV2(
            slug="city-bulky-waste-quantity-clear",
            scenario_key="시청:대형폐기물 배출",
            target_field="quantity",
            conversation_state="collecting_bulky_waste",
            current_fields=(
                ("region", "인천 독산동"),
                ("item_name", "소파"),
                ("quantity", "1개"),
                ("request_topic", None),
            ),
            offered_alternative_times=(),
            user_message="수량은 아직 정하지 않았어요.",
            intent="bulky_waste_guidance",
            user_action="change_detail",
            change_field="quantity",
            fields=(
                ("region", None),
                ("item_name", None),
                ("quantity", None),
                ("request_topic", None),
            ),
            tags=_CORRECTION,
            projected_obligations=_obligations(
                "collecting_bulky_waste",
                "quantity",
                None,
            ),
        ),
        "city-certificate-issuance-channel-clear": CoverageCandidateSpecV2(
            slug="city-certificate-issuance-channel-clear",
            scenario_key="시청:주민등록 등본 문의",
            target_field="issuance_channel",
            conversation_state="collecting_certificate_inquiry",
            current_fields=(
                ("document_type", "individual_extract"),
                ("applicant_relation", "self"),
                ("issuance_channel", "government24"),
                ("inquiry_topic", None),
            ),
            offered_alternative_times=(),
            user_message="발급 방법은 아직 정하지 않을게요.",
            intent="resident_certificate_guidance",
            user_action="change_detail",
            change_field="issuance_channel",
            fields=(
                ("document_type", None),
                ("applicant_relation", None),
                ("issuance_channel", None),
                ("inquiry_topic", None),
            ),
            tags=_CORRECTION,
            projected_obligations=_obligations(
                "collecting_certificate_inquiry",
                "issuance_channel",
                "government24",
            ),
        ),
    }
)
