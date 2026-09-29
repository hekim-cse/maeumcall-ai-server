from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.semantics import DifficultyTag

ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV6:
    slug: str
    scenario_key: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: str
    fields: tuple[tuple[str, tuple[str, ...] | None], ...]
    tags: tuple[DifficultyTag, ...]
    target_obligations: tuple[ObligationSpec, ...]
    projected_obligations: tuple[ObligationSpec, ...]


_ROWS = (
    (
        "support-service-product-type",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "product_type",
        "휴대폰",
        "노트북",
        "제품 종류를 휴대폰이 아니라 노트북으로 정정할게요.",
        "service_request",
    ),
    (
        "support-service-model-name",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "model_name",
        "갤럭시 S24",
        "아이폰 16",
        "모델명을 갤럭시 S24에서 아이폰 16으로 바꿔 주세요.",
        "service_request",
    ),
    (
        "support-service-symptom",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "symptom",
        "화면 파손",
        "전원 불량",
        "증상은 화면 파손이 아니라 전원이 켜지지 않는 문제입니다.",
        "service_request",
    ),
    (
        "support-service-occurred-at",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "occurred_at",
        "어제",
        "오늘 아침",
        "고장이 난 시점은 어제가 아니라 오늘 아침이에요.",
        "service_request",
    ),
    (
        "support-service-safety-status",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "safety_status",
        "no_safety_issue",
        "safety_issue",
        "안전 문제는 없다고 했는데 배터리가 부풀어 올라 위험한 상태로 정정합니다.",
        "service_request",
    ),
    (
        "support-service-channel",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "service_channel",
        "parcel",
        "visit",
        "택배 접수 대신 서비스센터 방문으로 변경해 주세요.",
        "service_request",
    ),
    (
        "support-service-schedule",
        "고객센터:a/s 접수",
        "collecting_service_request",
        "preferred_schedule",
        "월요일 오전",
        "화요일 오후",
        "희망 일정을 월요일 오전에서 화요일 오후로 바꿀게요.",
        "service_request",
    ),
    (
        "support-plan-inquiry-type",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        "inquiry_type",
        "billing",
        "discount",
        "청구 문의가 아니라 할인 상담으로 변경해 주세요.",
        "plan_contract_consultation",
    ),
    (
        "support-plan-current-service",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        "current_service",
        "5G 프리미엄",
        "LTE 베이직",
        "현재 요금제는 5G 프리미엄이 아니라 LTE 베이직입니다.",
        "plan_contract_consultation",
    ),
    (
        "support-plan-goal",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        "consultation_goal",
        "요금 절감",
        "데이터 확대",
        "상담 목표를 요금 절감에서 데이터 제공량 확대로 바꾸겠습니다.",
        "plan_contract_consultation",
    ),
    (
        "support-network-service-type",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "service_type",
        "mobile_data",
        "wifi",
        "모바일 데이터 문제가 아니라 와이파이 문제예요.",
        "network_call_issue",
    ),
    (
        "support-network-symptom",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "symptom",
        "속도 저하",
        "연결 끊김",
        "속도가 느린 게 아니라 연결이 계속 끊기는 증상입니다.",
        "network_call_issue",
    ),
    (
        "support-network-occurred-at",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "occurred_at",
        "어제",
        "오늘 오전",
        "발생 시점은 어제가 아니라 오늘 오전입니다.",
        "network_call_issue",
    ),
    (
        "support-network-scope",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "scope",
        "single_device",
        "multiple_devices",
        "한 대만 그런 줄 알았는데 여러 기기에서 발생합니다.",
        "network_call_issue",
    ),
    (
        "support-network-troubleshooting",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "troubleshooting_done",
        "공유기 재부팅",
        "비행기 모드 전환",
        "시도한 조치는 공유기 재부팅이 아니라 비행기 모드 전환입니다.",
        "network_call_issue",
    ),
    (
        "support-network-next-action",
        "고객센터:인터넷/통화 문제 문의",
        "collecting_network_issue",
        "next_action",
        "guided_diagnosis",
        "agent_handoff",
        "안내에 따라 진단하는 대신 상담원 연결을 원합니다.",
        "network_call_issue",
    ),
    (
        "delivery-delay-order-number",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        "order_number",
        "A-101",
        "A-102",
        "주문번호는 A-101이 아니라 A-102입니다.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-delay-detail",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        "delay_detail",
        "30분 지연",
        "한 시간 지연",
        "30분 늦은 게 아니라 벌써 한 시간째 지연 중입니다.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-delay-goal",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        "inquiry_goal",
        "estimated_arrival",
        "delay_reason",
        "예상 도착 시간보다 지연 이유를 확인해 주세요.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-delay-resolution",
        "배달:배달 지연 문의",
        "collecting_delay_inquiry",
        "delay_resolution",
        "wait",
        "check_cancellation",
        "더 기다리지 않고 취소 가능한지 확인하고 싶습니다.",
        "delivery_delay_inquiry",
    ),
    (
        "delivery-change-order-number",
        "배달:주문 변경",
        "collecting_order_change",
        "order_number",
        "B-201",
        "B-202",
        "변경할 주문번호는 B-201이 아니라 B-202예요.",
        "delivery_order_change",
    ),
    (
        "delivery-change-type",
        "배달:주문 변경",
        "collecting_order_change",
        "change_type",
        "menu_option",
        "delivery_address",
        "메뉴 옵션이 아니라 배달 주소를 변경하려는 겁니다.",
        "delivery_order_change",
    ),
    (
        "delivery-change-request",
        "배달:주문 변경",
        "collecting_order_change",
        "requested_change",
        "맵기 보통",
        "맵기 순한맛",
        "변경 내용은 맵기 보통이 아니라 순한맛입니다.",
        "delivery_order_change",
    ),
    (
        "delivery-refund-order-number",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        "order_number",
        "C-301",
        "C-302",
        "문제 주문은 C-301이 아니라 C-302입니다.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-issue-type",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        "issue_type",
        "damaged_or_quality",
        "wrong_item",
        "음식이 상한 문제가 아니라 다른 메뉴가 온 문제입니다.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-detail",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        "issue_detail",
        "용기가 찌그러짐",
        "주문과 다른 음료 도착",
        "상세 내용은 용기 파손이 아니라 주문과 다른 음료가 온 것입니다.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-evidence",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        "evidence_status",
        "available",
        "unavailable",
        "사진이 있다고 했는데 확인해 보니 증빙 자료가 없습니다.",
        "delivery_refund_redelivery",
    ),
    (
        "delivery-refund-resolution",
        "배달:환불/재배달 문의",
        "collecting_refund_redelivery",
        "resolution_preference",
        "refund",
        "redelivery",
        "환불 대신 같은 메뉴를 다시 배달해 주세요.",
        "delivery_refund_redelivery",
    ),
    (
        "city-waste-region",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        "region",
        "서울 독산동",
        "인천 구월동",
        "배출 지역은 서울 독산동이 아니라 인천 구월동입니다.",
        "bulky_waste_guidance",
    ),
    (
        "city-waste-item",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        "item_name",
        "소파",
        "장롱",
        "버릴 물건을 소파에서 장롱으로 정정할게요.",
        "bulky_waste_guidance",
    ),
    (
        "city-waste-topic",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        "request_topic",
        "application",
        "fee",
        "신고 방법이 아니라 배출 수수료를 문의하려고 합니다.",
        "bulky_waste_guidance",
    ),
    (
        "city-passport-application-type",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        "application_type",
        "first_issue",
        "reissue",
        "최초 발급이 아니라 재발급 문의입니다.",
        "passport_guidance",
    ),
    (
        "city-passport-applicant-type",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        "applicant_type",
        "adult_self",
        "minor",
        "성인 본인 신청이 아니라 미성년자 신청 건입니다.",
        "passport_guidance",
    ),
    (
        "city-passport-topic",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        "inquiry_topic",
        "processing_time",
        "documents",
        "처리 기간이 아니라 필요한 서류를 알고 싶어요.",
        "passport_guidance",
    ),
    (
        "city-passport-channel",
        "시청:여권 발급 문의",
        "collecting_passport_inquiry",
        "application_channel",
        "government24",
        "in_person",
        "정부24 온라인 신청 대신 직접 방문 신청으로 바꾸겠습니다.",
        "passport_guidance",
    ),
    (
        "city-certificate-document-type",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        "document_type",
        "register_copy",
        "individual_extract",
        "등본이 아니라 주민등록 초본을 발급하려고 합니다.",
        "resident_certificate_guidance",
    ),
    (
        "city-certificate-relation",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        "applicant_relation",
        "self",
        "representative",
        "본인 신청이 아니라 대리인 신청입니다.",
        "resident_certificate_guidance",
    ),
    (
        "city-certificate-topic",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        "inquiry_topic",
        "delivery",
        "fee",
        "수령 방법이 아니라 발급 수수료가 궁금합니다.",
        "resident_certificate_guidance",
    ),
)

_NEW_STATE_ACTION_SCENARIOS = frozenset(
    {
        "고객센터:a/s 접수",
        "고객센터:인터넷/통화 문제 문의",
        "배달:배달 지연 문의",
        "배달:환불/재배달 문의",
        "시청:여권 발급 문의",
    }
)


def _make(row, first_for_scenario: bool) -> CoverageCandidateSpecV6:
    slug, scenario, state, field, old, new, message, intent = row
    contract = EVALUATION_CONTRACTS[scenario]
    projected = [
        (CoverageDimension.CHANGE_FIELD, field),
        (CoverageDimension.ACTION_FIELD_PRESENT, f"change_detail->{field}"),
        (CoverageDimension.CURRENT_DELTA_RELATION, f"{field}->existing_value_replaced"),
    ]
    if first_for_scenario and scenario in _NEW_STATE_ACTION_SCENARIOS:
        projected.extend(
            (
                (CoverageDimension.STATE_ACTION, f"{state}->change_detail"),
                (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "correction"),
            )
        )
    tags = (DifficultyTag.SINGLE_FIELD, DifficultyTag.CORRECTION)
    if field == "safety_status" and new == "safety_issue":
        tags += (DifficultyTag.SAFETY,)
    return CoverageCandidateSpecV6(
        slug=slug,
        scenario_key=scenario,
        conversation_state=state,
        current_fields=tuple(
            (name, old if name == field else None) for name in contract.field_names
        ),
        offered_alternative_times=(),
        user_message=message,
        intent=intent,
        user_action="change_detail",
        change_field=field,
        fields=tuple((name, (new,) if name == field else None) for name in contract.field_names),
        tags=tags,
        target_obligations=((CoverageDimension.CHANGE_FIELD, field),),
        projected_obligations=tuple(sorted(projected, key=lambda item: (item[0].value, item[1]))),
    )


_seen: set[str] = set()
_specs = []
for _row in _ROWS:
    _scenario = _row[1]
    _specs.append(_make(_row, _scenario not in _seen))
    _seen.add(_scenario)

COVERAGE_CANDIDATE_SPECS_V6 = MappingProxyType({spec.slug: spec for spec in _specs})
if len(COVERAGE_CANDIDATE_SPECS_V6) != 38:
    raise RuntimeError("coverage candidate V6 policy must contain exactly 38 specs")
