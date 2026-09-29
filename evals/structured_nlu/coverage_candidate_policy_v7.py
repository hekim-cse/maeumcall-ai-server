from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS
from evals.structured_nlu.semantics import DifficultyTag

ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV7:
    slug: str
    scenario_key: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: str | None
    fields: tuple[tuple[str, tuple[str, ...] | None], ...]
    tags: tuple[DifficultyTag, ...]
    target_obligations: tuple[ObligationSpec, ...]
    projected_obligations: tuple[ObligationSpec, ...]


# Each row declares the output fields exercised by one action.  With the sole
# exception of assignment ask_follow_up, the live contracts allow only one of
# the remaining action-field pairs per action, establishing the 27-case bound.
_ROWS = (
    (
        "support-plan-consent-scope",
        "고객센터:요금/약정 상담",
        "collecting_plan_contract",
        {"consent_scope": "authenticated_lookup"},
        "change_detail",
        "consent_scope",
        {"consent_scope": "general_guidance"},
        "개인정보 조회 동의를 취소하고 일반 안내만 받겠습니다.",
        "plan_contract_consultation",
    ),
    (
        "delivery-change-unavailable-preference",
        "배달:주문 변경",
        "collecting_order_change",
        {"unavailable_preference": "check_cancellation"},
        "change_detail",
        "unavailable_preference",
        {"unavailable_preference": "keep_order"},
        "변경이 안 되면 취소 여부를 확인하지 말고 기존 주문을 유지해 주세요.",
        "delivery_order_change",
    ),
    (
        "city-waste-quantity",
        "시청:대형폐기물 배출",
        "collecting_bulky_waste",
        {"quantity": "1개"},
        "change_detail",
        "quantity",
        {"quantity": "2개"},
        "수량을 한 개가 아니라 두 개로 정정합니다.",
        "bulky_waste_guidance",
    ),
    (
        "city-certificate-channel",
        "시청:주민등록 등본 문의",
        "collecting_certificate_inquiry",
        {"issuance_channel": "government24"},
        "change_detail",
        "issuance_channel",
        {"issuance_channel": "kiosk"},
        "정부24 발급 대신 무인발급기 이용으로 바꿀게요.",
        "resident_certificate_guidance",
    ),
    (
        "professor-absence-date",
        "교수님:결석 사유 전달",
        "confirming_absence_info",
        {},
        "change_absence_date",
        None,
        {"absence_date": "내일"},
        "결석 날짜는 오늘이 아니라 내일입니다.",
        "absence_notice",
    ),
    (
        "professor-absence-reason",
        "교수님:결석 사유 전달",
        "confirming_absence_info",
        {},
        "change_absence_reason",
        None,
        {"absence_reason": "병원 진료"},
        "결석 사유를 예비군이 아니라 병원 진료로 수정하겠습니다.",
        "absence_notice",
    ),
    (
        "professor-absence-class",
        "교수님:결석 사유 전달",
        "confirming_absence_info",
        {},
        "change_class_name",
        None,
        {"class_name": "자료구조"},
        "수업명은 인공지능이 아니라 자료구조입니다.",
        "absence_notice",
    ),
    (
        "professor-absence-name",
        "교수님:결석 사유 전달",
        "confirming_absence_info",
        {},
        "change_user_name",
        None,
        {"user_name": "김민수"},
        "학생 이름을 홍길동이 아니라 김민수로 정정합니다.",
        "absence_notice",
    ),
    (
        "professor-appointment-date",
        "교수님:면담 예약",
        "confirming_info",
        {},
        "change_date",
        None,
        {"date": "다음 주 월요일"},
        "면담 날짜를 내일이 아니라 다음 주 월요일로 바꾸고 싶습니다.",
        "appointment_booking",
    ),
    (
        "professor-appointment-purpose",
        "교수님:면담 예약",
        "confirming_info",
        {},
        "change_purpose",
        None,
        {"appointment_purpose": "진로 상담"},
        "면담 목적은 과제 문의가 아니라 진로 상담입니다.",
        "appointment_booking",
    ),
    (
        "professor-appointment-time",
        "교수님:면담 예약",
        "confirming_info",
        {},
        "change_time",
        None,
        {"time": "오후 4시"},
        "면담 시간을 오후 3시에서 4시로 변경해 주세요.",
        "appointment_booking",
    ),
    (
        "professor-appointment-name",
        "교수님:면담 예약",
        "confirming_info",
        {},
        "change_user_name",
        None,
        {"user_name": "이서연"},
        "학생 이름은 홍길동이 아니라 이서연입니다.",
        "appointment_booking",
    ),
    (
        "professor-assignment-follow-up",
        "교수님:과제 문의",
        "answering_assignment_question",
        {},
        "ask_follow_up",
        None,
        {"assignment_topic": "팀 프로젝트", "question": "제출 형식이 PDF인지"},
        "팀 프로젝트 과제인데 제출 형식이 PDF인지도 알려 주실 수 있나요?",
        "assignment_inquiry",
    ),
    (
        "reservation-hair-designer",
        "예약:미용실 예약",
        "confirming_info",
        {},
        "change_designer",
        None,
        {"designer": "김아름"},
        "디자이너를 박지수 선생님에서 김아름 선생님으로 바꿔 주세요.",
        "reservation",
    ),
    (
        "reservation-hair-service",
        "예약:미용실 예약",
        "confirming_info",
        {},
        "change_service_type",
        None,
        {"service_type": "염색"},
        "시술을 커트가 아니라 염색으로 변경할게요.",
        "reservation",
    ),
    (
        "reservation-hair-time",
        "예약:미용실 예약",
        "confirming_info",
        {},
        "change_time",
        None,
        {"time": "오후 5시"},
        "예약 시간을 오후 2시에서 5시로 바꾸고 싶어요.",
        "reservation",
    ),
    (
        "reservation-hair-name",
        "예약:미용실 예약",
        "confirming_info",
        {},
        "change_user_name",
        None,
        {"user_name": "최유진"},
        "예약자 이름은 김민지가 아니라 최유진입니다.",
        "reservation",
    ),
    (
        "reservation-hospital-department",
        "예약:병원 예약",
        "confirming_info",
        {},
        "change_department",
        None,
        {"department": "정형외과"},
        "진료과를 내과에서 정형외과로 변경해 주세요.",
        "reservation",
    ),
    (
        "reservation-hospital-time",
        "예약:병원 예약",
        "confirming_info",
        {},
        "change_time",
        None,
        {"time": "오전 11시"},
        "진료 시간을 오전 10시가 아니라 11시로 바꿀게요.",
        "reservation",
    ),
    (
        "reservation-hospital-name",
        "예약:병원 예약",
        "confirming_info",
        {},
        "change_user_name",
        None,
        {"user_name": "박서준"},
        "예약자 이름을 홍길동에서 박서준으로 정정합니다.",
        "reservation",
    ),
    (
        "reservation-study-duration",
        "예약:스터디룸 예약",
        "confirming_info",
        {},
        "change_duration",
        None,
        {"duration": "3시간"},
        "이용 시간을 두 시간에서 세 시간으로 변경해 주세요.",
        "reservation",
    ),
    (
        "reservation-study-party",
        "예약:스터디룸 예약",
        "confirming_info",
        {},
        "change_party_size",
        None,
        {"party_size": "4명"},
        "이용 인원을 세 명이 아니라 네 명으로 바꿀게요.",
        "reservation",
    ),
    (
        "reservation-study-start",
        "예약:스터디룸 예약",
        "confirming_info",
        {},
        "change_start_time",
        None,
        {"start_time": "오후 6시"},
        "시작 시간을 오후 5시에서 6시로 변경하고 싶습니다.",
        "reservation",
    ),
    (
        "reservation-study-name",
        "예약:스터디룸 예약",
        "confirming_info",
        {},
        "change_user_name",
        None,
        {"user_name": "정하늘"},
        "예약자 이름은 김민수 대신 정하늘로 해 주세요.",
        "reservation",
    ),
    (
        "reservation-restaurant-party",
        "예약:식당 예약",
        "confirming_info",
        {},
        "change_party_size",
        None,
        {"party_size": "6명"},
        "예약 인원을 다섯 명에서 여섯 명으로 바꿔 주세요.",
        "reservation",
    ),
    (
        "reservation-restaurant-time",
        "예약:식당 예약",
        "confirming_info",
        {},
        "change_time",
        None,
        {"time": "오후 7시"},
        "예약 시간을 오후 6시가 아니라 7시로 변경할게요.",
        "reservation",
    ),
    (
        "reservation-restaurant-name",
        "예약:식당 예약",
        "confirming_info",
        {},
        "change_user_name",
        None,
        {"user_name": "윤지호"},
        "예약자 이름을 홍길동에서 윤지호로 수정해 주세요.",
        "reservation",
    ),
)

_WORKFLOW_SCENARIOS = frozenset(
    {
        "고객센터:요금/약정 상담",
        "배달:주문 변경",
        "시청:대형폐기물 배출",
        "시청:주민등록 등본 문의",
    }
)
_NEW_TAG_SCENARIOS = frozenset({"교수님:결석 사유 전달", "교수님:면담 예약"})


def _make(row, first_for_state_action: bool, first_for_scenario: bool) -> CoverageCandidateSpecV7:
    slug, scenario, state, current, action, change_field, output, message, intent = row
    contract = EVALUATION_CONTRACTS[scenario]
    targets = tuple(
        sorted(
            ((CoverageDimension.ACTION_FIELD_PRESENT, f"{action}->{field}") for field in output),
            key=lambda item: item[1],
        )
    )
    projected = list(targets)
    if scenario in _WORKFLOW_SCENARIOS:
        projected.append(
            (
                CoverageDimension.CURRENT_DELTA_RELATION,
                f"{change_field}->existing_value_replaced",
            )
        )
    else:
        if first_for_state_action:
            projected.append((CoverageDimension.STATE_ACTION, f"{state}->{action}"))
        if first_for_scenario and scenario in _NEW_TAG_SCENARIOS:
            projected.extend(
                (
                    (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "correction"),
                    (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "single_field"),
                )
            )
    tags = (
        (DifficultyTag.SINGLE_FIELD, DifficultyTag.CORRECTION)
        if len(output) == 1
        else (DifficultyTag.MULTI_FIELD,)
    )
    return CoverageCandidateSpecV7(
        slug=slug,
        scenario_key=scenario,
        conversation_state=state,
        current_fields=(
            tuple((name, current.get(name)) for name in contract.field_names)
            if contract.uses_current_fields
            else ()
        ),
        offered_alternative_times=(),
        user_message=message,
        intent=intent,
        user_action=action,
        change_field=change_field,
        fields=tuple(
            (name, None if output.get(name) is None else (output[name],))
            for name in contract.field_names
        ),
        tags=tags,
        target_obligations=targets,
        projected_obligations=tuple(sorted(projected, key=lambda item: (item[0].value, item[1]))),
    )


_seen_actions: set[tuple[str, str, str]] = set()
_seen_scenarios: set[str] = set()
_specs = []
for _row in _ROWS:
    _action_key = (_row[1], _row[2], _row[4])
    _scenario = _row[1]
    _specs.append(
        _make(
            _row,
            _action_key not in _seen_actions,
            _scenario not in _seen_scenarios,
        )
    )
    _seen_actions.add(_action_key)
    _seen_scenarios.add(_scenario)

COVERAGE_CANDIDATE_SPECS_V7 = MappingProxyType({spec.slug: spec for spec in _specs})
if len(COVERAGE_CANDIDATE_SPECS_V7) != 27:
    raise RuntimeError("coverage candidate V7 policy must contain exactly 27 specs")
