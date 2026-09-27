from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.benchmark import CoverageDimension
from evals.structured_nlu.semantics import DifficultyTag

FieldValue = tuple[str, ...] | None
ObligationSpec = tuple[CoverageDimension, str]


@dataclass(frozen=True)
class CoverageCandidateSpecV3:
    slug: str
    scenario_key: str
    relation: str
    conversation_state: str
    current_fields: tuple[tuple[str, str | None], ...]
    offered_alternative_times: tuple[str, ...]
    user_message: str
    intent: str
    user_action: str
    change_field: None
    fields: tuple[tuple[str, FieldValue], ...]
    tags: tuple[DifficultyTag, ...]
    projected_obligations: tuple[ObligationSpec, ...]


_FIELDS = MappingProxyType(
    {
        "예약:병원 예약": ("department", "date", "time", "user_name", "selected_time"),
        "예약:식당 예약": ("date", "time", "party_size", "user_name", "selected_time"),
        "예약:미용실 예약": (
            "date",
            "time",
            "service_type",
            "designer",
            "user_name",
            "selected_time",
        ),
        "예약:스터디룸 예약": (
            "date",
            "start_time",
            "duration",
            "party_size",
            "user_name",
            "selected_time",
        ),
    }
)

_SCOPES = (
    (
        "hospital-unavailable",
        "예약:병원 예약",
        "reservation_unavailable",
        (
            (
                "그럼 가능한 다른 진료 시간이 있나요?",
                "말씀해 주신 시간 말고 다른 진료 시간도 있나요?",
            ),
            (
                "그럼 병원 예약 날짜를 내일로 바꿀게요.",
                "제시된 진료 시간 대신 예약 날짜를 모레로 바꿀게요.",
            ),
            ("병원 주차장은 어디예요?", "그 시간들은 고르지 않을게요. 병원 주차장은 어디예요?"),
        ),
        ("내일", "모레"),
    ),
    (
        "hospital-suggest",
        "예약:병원 예약",
        "suggest_alternative",
        (
            (
                "다른 진료 가능 시간도 더 알려주세요.",
                "제안하신 두 시간 외에 다른 진료 시간도 있나요?",
            ),
            (
                "병원 예약 날짜를 이번 주 금요일로 바꿀게요.",
                "제안 시간 대신 예약 날짜를 다음 주 월요일로 바꿀게요.",
            ),
            (
                "진료비 결제 방법이 궁금해요.",
                "제안 시간은 선택하지 않을게요. 진료비 결제 방법이 궁금해요.",
            ),
        ),
        ("이번 주 금요일", "다음 주 월요일"),
    ),
    (
        "restaurant-unavailable",
        "예약:식당 예약",
        "reservation_unavailable",
        (
            (
                "그럼 가능한 다른 식사 시간이 있나요?",
                "말씀해 주신 시간 말고 다른 식사 시간도 있나요?",
            ),
            (
                "식당 예약 날짜를 이번 주 토요일로 바꿀게요.",
                "제시된 시간 대신 식당 예약을 다음 주 토요일로 바꿀게요.",
            ),
            ("식당에 주차할 수 있나요?", "그 시간들은 고르지 않을게요. 식당 주차가 가능한가요?"),
        ),
        ("이번 주 토요일", "다음 주 토요일"),
    ),
    (
        "hair-salon-unavailable",
        "예약:미용실 예약",
        "reservation_unavailable",
        (
            (
                "그럼 가능한 다른 시술 시간이 있나요?",
                "말씀해 주신 시간 말고 다른 시술 시간도 있나요?",
            ),
            (
                "미용실 예약 날짜를 이번 주 목요일로 바꿀게요.",
                "제시된 시간 대신 미용실 예약을 다음 주 화요일로 바꿀게요.",
            ),
            ("주차 지원이 되나요?", "제시된 시간은 선택하지 않고 주차 지원 여부를 알고 싶어요."),
        ),
        ("이번 주 목요일", "다음 주 화요일"),
    ),
    (
        "study-room-unavailable",
        "예약:스터디룸 예약",
        "reservation_unavailable",
        (
            (
                "그럼 가능한 다른 이용 시간이 있나요?",
                "말씀해 주신 시간 말고 다른 이용 시간도 있나요?",
            ),
            (
                "스터디룸 예약 날짜를 내일로 바꿀게요.",
                "제시된 시간 대신 스터디룸 예약을 이번 주 일요일로 바꿀게요.",
            ),
            (
                "스터디룸에 화이트보드가 있나요?",
                "그 시간들은 고르지 않을게요. 화이트보드가 있나요?",
            ),
        ),
        ("내일", "이번 주 일요일"),
    ),
)

_ACTIONS = (
    ("ask-other-time", "ask_other_time", (DifficultyTag.ELLIPSIS,)),
    (
        "change-date",
        "change_date",
        (DifficultyTag.SINGLE_FIELD, DifficultyTag.CORRECTION),
    ),
    ("unknown", "unknown", (DifficultyTag.HARD_NEGATIVE,)),
)
_RELATIONS = (
    ("no-offers", "no_offers", ()),
    ("offers-unselected", "offers_unselected", ("오후 3시", "오후 4시")),
)


def _make_spec(scope, action_index: int, relation_index: int) -> CoverageCandidateSpecV3:
    scope_slug, scenario_key, state, messages, dates = scope
    action_slug, action, tags = _ACTIONS[action_index]
    relation_slug, relation, offered = _RELATIONS[relation_index]
    field_names = _FIELDS[scenario_key]
    date = dates[relation_index] if action == "change_date" else None
    fields = tuple(
        (name, (date,) if name == "date" and date is not None else None) for name in field_names
    )
    obligations: list[ObligationSpec] = [
        (CoverageDimension.ALTERNATIVE_TIME_RELATION, f"{state}->{action}->{relation}")
    ]
    if relation == "no_offers":
        obligations.append((CoverageDimension.STATE_ACTION, f"{state}->{action}"))
        if action == "change_date" and state == "reservation_unavailable":
            obligations.extend(
                (
                    (CoverageDimension.ACTION_FIELD_PRESENT, "change_date->date"),
                    (CoverageDimension.SCENARIO_DIFFICULTY_TAG, "correction"),
                )
            )
    return CoverageCandidateSpecV3(
        slug=f"{scope_slug}-{action_slug}-{relation_slug}",
        scenario_key=scenario_key,
        relation=relation,
        conversation_state=state,
        current_fields=(),
        offered_alternative_times=offered,
        user_message=messages[action_index][relation_index],
        intent="reservation",
        user_action=action,
        change_field=None,
        fields=fields,
        tags=tags,
        projected_obligations=tuple(sorted(obligations, key=lambda item: (item[0].value, item[1]))),
    )


_GENERATED_SPECS = tuple(
    _make_spec(scope, action_index, relation_index)
    for scope in _SCOPES
    for action_index in range(len(_ACTIONS))
    for relation_index in range(len(_RELATIONS))
)
_SELECT_SPEC = CoverageCandidateSpecV3(
    slug="hospital-suggest-select-alternative-time-selected-offer",
    scenario_key="예약:병원 예약",
    relation="selected_offer",
    conversation_state="suggest_alternative",
    current_fields=(),
    offered_alternative_times=("오후 3시", "오후 4시"),
    user_message="제안해 주신 진료 시간 중 오후 3시로 할게요.",
    intent="reservation",
    user_action="select_alternative_time",
    change_field=None,
    fields=(
        ("department", None),
        ("date", None),
        ("time", None),
        ("user_name", None),
        ("selected_time", ("오후 3시",)),
    ),
    tags=(DifficultyTag.SINGLE_FIELD,),
    projected_obligations=(
        (
            CoverageDimension.ALTERNATIVE_TIME_RELATION,
            "suggest_alternative->select_alternative_time->selected_offer",
        ),
        (CoverageDimension.STATE_ACTION, "suggest_alternative->select_alternative_time"),
    ),
)

COVERAGE_CANDIDATE_SPECS_V3 = MappingProxyType(
    {spec.slug: spec for spec in (*_GENERATED_SPECS, _SELECT_SPEC)}
)

if len(COVERAGE_CANDIDATE_SPECS_V3) != 31:
    raise RuntimeError("coverage candidate V3 policy must contain exactly 31 specs")
