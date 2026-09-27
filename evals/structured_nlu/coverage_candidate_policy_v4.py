from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.semantics import DifficultyTag

ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV4:
    slug: str
    scenario_key: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: None
    fields: tuple[tuple[str, None], ...]
    tags: tuple[DifficultyTag, ...]
    target_obligations: tuple[ObligationSpec, ...]
    projected_obligations: tuple[ObligationSpec, ...]


_FIELDS = {
    "고객센터:a/s 접수": (
        "product_type",
        "model_name",
        "symptom",
        "occurred_at",
        "safety_status",
        "service_channel",
        "preferred_schedule",
    ),
    "고객센터:요금/약정 상담": (
        "inquiry_type",
        "current_service",
        "consultation_goal",
        "consent_scope",
    ),
    "고객센터:인터넷/통화 문제 문의": (
        "service_type",
        "symptom",
        "occurred_at",
        "scope",
        "troubleshooting_done",
        "next_action",
    ),
    "배달:배달 지연 문의": ("order_number", "delay_detail", "inquiry_goal", "delay_resolution"),
    "배달:주문 변경": ("order_number", "change_type", "requested_change", "unavailable_preference"),
    "배달:환불/재배달 문의": (
        "order_number",
        "issue_type",
        "issue_detail",
        "evidence_status",
        "resolution_preference",
    ),
    "시청:대형폐기물 배출": ("region", "item_name", "quantity", "request_topic"),
    "시청:여권 발급 문의": (
        "application_type",
        "applicant_type",
        "inquiry_topic",
        "application_channel",
    ),
    "시청:주민등록 등본 문의": (
        "document_type",
        "applicant_relation",
        "issuance_channel",
        "inquiry_topic",
    ),
}

_ROWS = (
    (
        "support-service-safety-visit",
        "고객센터:a/s 접수",
        "safety_action_required",
        {"safety_status": "safety_issue", "service_channel": "visit"},
        "보호필름 할인 행사도 하나요?",
        "service_request",
        (DifficultyTag.HARD_NEGATIVE, DifficultyTag.SAFETY),
    ),
    (
        "support-plan-contract-expiry-general",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "contract_expiry", "consent_scope": "general_guidance"},
        "멤버십으로 영화 할인도 받을 수 있나요?",
        "plan_contract_consultation",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "support-plan-discount",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "discount"},
        "휴대폰 배경화면을 바꾸는 방법이 궁금해요.",
        "plan_contract_consultation",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "support-plan-plan-change",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "plan_change"},
        "가까운 대리점 주차장이 넓은가요?",
        "plan_contract_consultation",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "support-network-wifi-multiple",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        {"service_type": "wifi", "scope": "multiple_devices"},
        "새 휴대폰 케이스 색상을 추천해 주세요.",
        "network_call_issue",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-delay-cancel-estimated",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        {"delay_resolution": "check_cancellation", "inquiry_goal": "estimated_arrival"},
        "배달 앱 글자 크기를 키울 수 있나요?",
        "delivery_delay_inquiry",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-delay-wait",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        {"delay_resolution": "wait"},
        "리뷰를 작성하면 포인트를 주나요?",
        "delivery_delay_inquiry",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-change-address-cancel",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "delivery_address", "unavailable_preference": "check_cancellation"},
        "배달 기사님 평점은 어디서 보나요?",
        "delivery_order_change",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-change-menu-option-keep",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "menu_option", "unavailable_preference": "keep_order"},
        "앱 알림 소리를 끌 수 있나요?",
        "delivery_order_change",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-change-menu-quantity",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "menu_or_quantity"},
        "이번 달 쿠폰은 언제 나오나요?",
        "delivery_order_change",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "delivery-refund-wrong-refund",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        {"issue_type": "wrong_item", "resolution_preference": "refund"},
        "배달 앱 테마를 어둡게 바꾸고 싶어요.",
        "delivery_refund_redelivery",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-waste-collection",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "collection_status"},
        "시청 민원실 점심시간이 언제예요?",
        "bulky_waste_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-waste-fee",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "fee"},
        "동네 체육관 운영 시간을 알려 주세요.",
        "bulky_waste_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-waste-place",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "place_and_schedule"},
        "가로등 고장은 어디에 신고하나요?",
        "bulky_waste_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-passport-office-bundle",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {"application_type": "reissue", "applicant_type": "minor", "inquiry_topic": "office"},
        "시청 주차 요금이 궁금합니다.",
        "passport_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-passport-processing-channel",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {"application_channel": "government24", "inquiry_topic": "processing_time"},
        "근처 도서관 휴관일을 알려 주세요.",
        "passport_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-certificate-documents-bundle",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {
            "document_type": "register_copy",
            "applicant_relation": "representative",
            "inquiry_topic": "documents",
        },
        "주민센터에 자전거 보관소가 있나요?",
        "resident_certificate_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-certificate-eligibility-bundle",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {
            "applicant_relation": "same_household",
            "issuance_channel": "kiosk",
            "inquiry_topic": "eligibility",
        },
        "무인민원발급기 화면 밝기를 조절할 수 있나요?",
        "resident_certificate_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
    (
        "city-certificate-fee-in-person",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {"issuance_channel": "in_person", "inquiry_topic": "fee"},
        "주민센터 문화 강좌 일정이 궁금해요.",
        "resident_certificate_guidance",
        (DifficultyTag.HARD_NEGATIVE,),
    ),
)


def _make(row, first_for_scenario: bool) -> CoverageCandidateSpecV4:
    slug, scenario, state, present, message, intent, tags = row
    targets = tuple(
        sorted(
            (
                (CoverageDimension.CURRENT_FIELD_OPTION, f"{name}={value}")
                for name, value in present.items()
            ),
            key=lambda item: item[1],
        )
    )
    projected = list(targets)
    if first_for_scenario:
        projected.append((CoverageDimension.STATE_ACTION, f"{state}->unknown"))
    if scenario == "고객센터:a/s 접수":
        projected.extend(
            (
                (
                    CoverageDimension.CURRENT_FIELDS_CONTEXT,
                    "safety_action_required->guarded_partial",
                ),
                (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "safety"),
            )
        )
    return CoverageCandidateSpecV4(
        slug=slug,
        scenario_key=scenario,
        conversation_state=state,
        current_fields=tuple((name, present.get(name)) for name in _FIELDS[scenario]),
        offered_alternative_times=(),
        user_message=message,
        intent=intent,
        user_action="unknown",
        change_field=None,
        fields=tuple((name, None) for name in _FIELDS[scenario]),
        tags=tags,
        target_obligations=targets,
        projected_obligations=tuple(sorted(projected, key=lambda item: (item[0].value, item[1]))),
    )


_seen: set[str] = set()
_specs = []
for _row in _ROWS:
    _scenario = _row[1]
    _specs.append(_make(_row, _scenario not in _seen))
    _seen.add(_scenario)

COVERAGE_CANDIDATE_SPECS_V4 = MappingProxyType({spec.slug: spec for spec in _specs})
if len(COVERAGE_CANDIDATE_SPECS_V4) != 19:
    raise RuntimeError("coverage candidate V4 policy must contain exactly 19 specs")
