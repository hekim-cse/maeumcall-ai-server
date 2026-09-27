from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.semantics import DifficultyTag

ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV5:
    slug: str
    scenario_key: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: None
    fields: tuple[tuple[str, tuple[str, ...] | None], ...]
    tags: tuple[DifficultyTag, ...]
    target_obligations: tuple[ObligationSpec, ...]
    projected_obligations: tuple[ObligationSpec, ...]


# One row may carry at most one option for a field.  For each scenario, the number
# of rows therefore equals the largest number of still-missing options on any one
# field.  Summed across the nine option-bearing workflows, 27 is both a lower
# bound and the size of this construction.
_ROWS = (
    (
        "support-service-safety-onsite",
        "고객센터:a/s 접수",
        "collecting_service_request",
        {"symptom": "배터리 부풀음", "safety_status": "safety_issue", "service_channel": "onsite"},
        "휴대폰 배터리가 부풀어 올랐어요. 기사님이 현장에 와서 점검해 주세요.",
        "service_request",
    ),
    (
        "support-service-parcel",
        "고객센터:a/s 접수",
        "collecting_service_request",
        {"product_type": "휴대폰", "symptom": "화면 파손", "service_channel": "parcel"},
        "휴대폰 화면이 깨졌습니다. 택배로 수리를 맡기고 싶어요.",
        "service_request",
    ),
    (
        "support-service-visit",
        "고객센터:a/s 접수",
        "collecting_service_request",
        {"product_type": "노트북", "symptom": "키보드 고장", "service_channel": "visit"},
        "노트북 키보드가 고장 났어요. 서비스센터에 직접 방문하겠습니다.",
        "service_request",
    ),
    (
        "support-plan-billing-authenticated",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "billing", "consent_scope": "authenticated_lookup"},
        "본인 인증을 하고 이번 달 청구 금액을 조회해 주세요.",
        "plan_contract_consultation",
    ),
    (
        "support-plan-contract-general",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "contract_expiry", "consent_scope": "general_guidance"},
        "약정 만료 시점은 개인정보 조회 없이 일반적인 기준만 안내해 주세요.",
        "plan_contract_consultation",
    ),
    (
        "support-plan-discount",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"inquiry_type": "discount"},
        "지금 받을 수 있는 요금 할인 제도가 궁금합니다.",
        "plan_contract_consultation",
    ),
    (
        "support-network-voice-multiple-agent",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        {"service_type": "voice_call", "scope": "multiple_devices", "next_action": "agent_handoff"},
        "가족 휴대폰 여러 대에서 통화가 안 됩니다. 상담원에게 연결해 주세요.",
        "network_call_issue",
    ),
    (
        "support-network-wifi-single-remote",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        {"service_type": "wifi", "scope": "single_device", "next_action": "remote_check"},
        "제 노트북 한 대만 와이파이가 끊겨요. 원격으로 확인해 주세요.",
        "network_call_issue",
    ),
    (
        "support-network-wired-location-service",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        {
            "service_type": "wired_internet",
            "scope": "specific_location",
            "next_action": "service_request",
        },
        "거실에서만 유선 인터넷이 안 됩니다. 수리 접수를 원합니다.",
        "network_call_issue",
    ),
    (
        "delivery-delay-reason-cancel",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        {"inquiry_goal": "delay_reason", "delay_resolution": "check_cancellation"},
        "배달이 늦는 이유를 확인해 주시고 지금 취소 가능한지도 알려 주세요.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-delay-location-wait",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        {"inquiry_goal": "delivery_location", "delay_resolution": "wait"},
        "현재 배달 위치를 알려 주세요. 조금 더 기다리겠습니다.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-change-contact-cancel",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "contact", "unavailable_preference": "check_cancellation"},
        "연락처를 바꾸고 싶어요. 변경이 안 되면 취소 가능한지 확인해 주세요.",
        "delivery_order_change",
    ),
    (
        "delivery-change-address-keep",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "delivery_address", "unavailable_preference": "keep_order"},
        "배달 주소를 변경해 주세요. 안 되면 주문은 그대로 둘게요.",
        "delivery_order_change",
    ),
    (
        "delivery-change-menu-option",
        "배달:주문 변경",
        "collecting_order_change",
        {"change_type": "menu_option"},
        "주문한 메뉴의 맵기 옵션을 바꾸고 싶습니다.",
        "delivery_order_change",
    ),
    (
        "delivery-refund-missing-unavailable-redelivery",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        {
            "issue_type": "missing_item",
            "evidence_status": "unavailable",
            "resolution_preference": "redelivery",
        },
        "음료가 빠졌는데 사진은 없습니다. 빠진 음료를 다시 보내 주세요.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-not-received-refund",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        {"issue_type": "not_received", "resolution_preference": "refund"},
        "배달 완료로 뜨지만 받지 못했습니다. 환불해 주세요.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-wrong-item",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        {"issue_type": "wrong_item"},
        "주문한 것과 다른 메뉴가 왔어요.",
        "delivery_refund_redelivery",
    ),
    (
        "city-waste-collection",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "collection_status"},
        "신고한 소파가 수거됐는지 확인하고 싶습니다.",
        "bulky_waste_guidance",
    ),
    (
        "city-waste-fee",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "fee"},
        "장롱을 버릴 때 수수료가 얼마인지 알려 주세요.",
        "bulky_waste_guidance",
    ),
    (
        "city-waste-place-schedule",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"request_topic": "place_and_schedule"},
        "대형폐기물을 어디에 언제 내놓아야 하나요?",
        "bulky_waste_guidance",
    ),
    (
        "city-passport-first-legal-documents-in-person",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {
            "application_type": "first_issue",
            "applicant_type": "legal_representative",
            "inquiry_topic": "documents",
            "application_channel": "in_person",
        },
        "아이의 첫 여권을 법정대리인인 제가 방문 신청할 때 필요한 서류가 무엇인가요?",
        "passport_guidance",
    ),
    (
        "city-passport-reissue-minor-fee-overseas",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {
            "application_type": "reissue",
            "applicant_type": "minor",
            "inquiry_topic": "fee",
            "application_channel": "overseas_mission",
        },
        "미성년자 여권을 해외 공관에서 재발급할 때 수수료가 궁금합니다.",
        "passport_guidance",
    ),
    (
        "city-passport-office",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {"inquiry_topic": "office"},
        "여권을 신청할 수 있는 담당 창구가 어디인가요?",
        "passport_guidance",
    ),
    (
        "city-passport-online-eligibility",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        {"inquiry_topic": "online_eligibility"},
        "온라인으로 여권을 신청할 수 있는 대상인지 알고 싶어요.",
        "passport_guidance",
    ),
    (
        "city-certificate-extract-representative-documents-in-person",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {
            "document_type": "individual_extract",
            "applicant_relation": "representative",
            "issuance_channel": "in_person",
            "inquiry_topic": "documents",
        },
        "대리인이 주민등록 초본을 방문 발급할 때 필요한 서류가 무엇인가요?",
        "resident_certificate_guidance",
    ),
    (
        "city-certificate-household-kiosk-eligibility",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {
            "applicant_relation": "same_household",
            "issuance_channel": "kiosk",
            "inquiry_topic": "eligibility",
        },
        "같은 세대원의 등본을 무인발급기에서 뗄 수 있는지 궁금합니다.",
        "resident_certificate_guidance",
    ),
    (
        "city-certificate-fee",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {"inquiry_topic": "fee"},
        "주민등록 등본 발급 수수료가 얼마인가요?",
        "resident_certificate_guidance",
    ),
)

_PREVIOUSLY_COVERED_OPTIONS = frozenset(
    {("고객센터:요금/약정 상담", "consent_scope=authenticated_lookup")}
)


def _make(row, first_for_scenario: bool) -> CoverageCandidateSpecV5:
    slug, scenario, state, present, message, intent = row
    contract = EVALUATION_CONTRACTS[scenario]
    option_fields = dict(contract.field_options)
    targets = tuple(
        sorted(
            (
                (CoverageDimension.FIELD_OPTION, f"{name}={value}")
                for name, value in present.items()
                if name in option_fields
                and (scenario, f"{name}={value}") not in _PREVIOUSLY_COVERED_OPTIONS
            ),
            key=lambda item: item[1],
        )
    )
    projected = list(targets)
    if first_for_scenario:
        projected.append((CoverageDimension.CURRENT_FIELDS_CONTEXT, f"{state}->empty"))
    if scenario == "시청:여권 발급 문의" and first_for_scenario:
        projected.append((CoverageDimension.SCENARIO_DIFFICULTY_TAG, "multi_field"))
    populated = sum(value is not None for value in present.values())
    tags = (DifficultyTag.MULTI_FIELD,) if populated > 1 else (DifficultyTag.SINGLE_FIELD,)
    if present.get("safety_status") == "safety_issue":
        tags += (DifficultyTag.SAFETY,)
    return CoverageCandidateSpecV5(
        slug=slug,
        scenario_key=scenario,
        conversation_state=state,
        current_fields=tuple((name, None) for name in contract.field_names),
        offered_alternative_times=(),
        user_message=message,
        intent=intent,
        user_action="provide_details",
        change_field=None,
        fields=tuple(
            (name, None if present.get(name) is None else (present[name],))
            for name in contract.field_names
        ),
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
COVERAGE_CANDIDATE_SPECS_V5 = MappingProxyType({spec.slug: spec for spec in _specs})
if len(COVERAGE_CANDIDATE_SPECS_V5) != 27:
    raise RuntimeError("coverage candidate V5 policy must contain exactly 27 specs")
