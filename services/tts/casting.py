from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from types import MappingProxyType
from typing import TypeAlias

from services.flow.common.state_contract import build_scenario_key
from services.flow.registry import FLOW_REGISTRY
from services.tts.catalog import TTSVoiceId
from services.tts.errors import TTSServiceError


class TTSCastVersion(IntEnum):
    V1 = 1
    V2 = 2


class TTSProviderId(StrEnum):
    QWEN3_TTS = "qwen3-tts"
    NVIDIA_MAGPIE = "nvidia-magpie"
    BARK_SMALL = "bark-small"
    QWEN3_TTS_VOICE_CLONE = "qwen3-tts-voice-clone"


class TTSPersonaId(StrEnum):
    MOTHER = "mother"
    FATHER = "father"


class MagpieVoiceId(StrEnum):
    ARIA = "aria"
    JASON = "jason"
    LEO = "leo"
    SOFIA = "sofia"


@dataclass(frozen=True)
class ScenarioVoiceAssignment:
    provider: TTSProviderId
    voice: str
    role_id: str
    persona_id: TTSPersonaId | None = None


def _qwen(voice: TTSVoiceId, *, role_id: str) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(TTSProviderId.QWEN3_TTS, voice.value, role_id)


def _magpie(voice: MagpieVoiceId, *, role_id: str) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(TTSProviderId.NVIDIA_MAGPIE, voice.value, role_id)


def _bark(voice: str, *, role_id: str) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(TTSProviderId.BARK_SMALL, voice, role_id)


def _voice_clone(
    voice: str,
    *,
    role_id: str,
    persona_id: TTSPersonaId,
) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(
        TTSProviderId.QWEN3_TTS_VOICE_CLONE,
        voice,
        role_id,
        persona_id,
    )


def _key(category: str, title: str) -> str:
    return build_scenario_key(category, title)


_CAST_V1_ENTRIES: tuple[tuple[str, ScenarioVoiceAssignment], ...] = (
    (_key("예약", "병원 예약"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("예약", "식당 예약"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("예약", "미용실 예약"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("예약", "스터디룸 예약"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("교수님", "면담 예약"), _qwen(TTSVoiceId.ERIC, role_id="professor")),
    (_key("교수님", "과제 문의"), _qwen(TTSVoiceId.ERIC, role_id="professor")),
    (_key("교수님", "결석 사유 전달"), _qwen(TTSVoiceId.ERIC, role_id="professor")),
    (_key("배달", "주문 변경"), _magpie(MagpieVoiceId.JASON, role_id="delivery_agent")),
    (_key("배달", "배달 지연 문의"), _magpie(MagpieVoiceId.JASON, role_id="delivery_agent")),
    (_key("배달", "환불/재배달 문의"), _magpie(MagpieVoiceId.JASON, role_id="delivery_agent")),
    (_key("시청", "여권 발급 문의"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("시청", "주민등록 등본 문의"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("시청", "대형폐기물 배출"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (
        _key("고객센터", "인터넷/통화 문제 문의"),
        _magpie(MagpieVoiceId.SOFIA, role_id="service_agent"),
    ),
    (_key("고객센터", "요금/약정 상담"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("고객센터", "A/S 접수"), _magpie(MagpieVoiceId.SOFIA, role_id="service_agent")),
    (_key("가족", "안부인사"), _magpie(MagpieVoiceId.ARIA, role_id="family_mother")),
    (_key("가족", "일정 조율"), _magpie(MagpieVoiceId.ARIA, role_id="family_mother")),
    (_key("가족", "도움 부탁"), _magpie(MagpieVoiceId.ARIA, role_id="family_mother")),
    (_key("친구", "생일 축하 전화"), _qwen(TTSVoiceId.SERENA, role_id="friend")),
    (_key("친구", "심심해서 거는 전화"), _qwen(TTSVoiceId.SERENA, role_id="friend")),
    (_key("친구", "약속 잡는 전화"), _qwen(TTSVoiceId.SERENA, role_id="friend")),
    (_key("친구", "약속 변경/취소"), _qwen(TTSVoiceId.SERENA, role_id="friend")),
    (_key("친구", "스터디 제안"), _qwen(TTSVoiceId.SERENA, role_id="friend")),
    (_key("연인", "안부인사"), _qwen(TTSVoiceId.UNCLE_FU, role_id="lover")),
    (_key("연인", "데이트 약속 잡기"), _qwen(TTSVoiceId.UNCLE_FU, role_id="lover")),
    (_key("연인", "서운함 표현"), _qwen(TTSVoiceId.UNCLE_FU, role_id="lover")),
    (_key("연인", "사과하기"), _qwen(TTSVoiceId.UNCLE_FU, role_id="lover")),
    (_key("회사", "보고서 제출"), _magpie(MagpieVoiceId.LEO, role_id="company_manager")),
    (_key("회사", "진행상황 보고"), _magpie(MagpieVoiceId.LEO, role_id="company_manager")),
    (_key("회사", "회의 일정 조율"), _magpie(MagpieVoiceId.LEO, role_id="company_manager")),
    (_key("회사", "연차/반차 신청"), _magpie(MagpieVoiceId.LEO, role_id="company_manager")),
)


def _build_cast(
    entries: tuple[tuple[str, ScenarioVoiceAssignment], ...],
) -> MappingProxyType[str, ScenarioVoiceAssignment]:
    cast: dict[str, ScenarioVoiceAssignment] = {}
    for scenario_key, assignment in entries:
        if scenario_key in cast:
            raise RuntimeError(f"duplicate TTS cast assignment: {scenario_key}")
        cast[scenario_key] = assignment
    return MappingProxyType(cast)


SCENARIO_VOICE_CAST = _build_cast(_CAST_V1_ENTRIES)

CastLookupKey: TypeAlias = tuple[str, TTSPersonaId | None]


def _v2_assignment(category: str) -> ScenarioVoiceAssignment:
    if category in {"예약", "시청", "고객센터"}:
        return _qwen(TTSVoiceId.RYAN, role_id="service_agent")
    if category == "교수님":
        return _qwen(TTSVoiceId.ERIC, role_id="professor")
    if category == "배달":
        return _qwen(TTSVoiceId.VIVIAN, role_id="delivery_agent")
    if category == "친구":
        return _qwen(TTSVoiceId.SERENA, role_id="friend")
    if category == "연인":
        return _qwen(TTSVoiceId.UNCLE_FU, role_id="lover")
    if category == "회사":
        return _bark("ko_speaker_5", role_id="company_manager")
    raise RuntimeError(f"TTS cast v2 category requires a persona assignment: {category}")


def _build_cast_v2() -> MappingProxyType[CastLookupKey, ScenarioVoiceAssignment]:
    cast: dict[CastLookupKey, ScenarioVoiceAssignment] = {}
    for scenario_key, registration in FLOW_REGISTRY.items():
        if registration.category == "가족":
            assignments = (
                ScenarioVoiceAssignment(
                    TTSProviderId.QWEN3_TTS,
                    TTSVoiceId.AIDEN.value,
                    "family_father",
                    TTSPersonaId.FATHER,
                ),
                _voice_clone(
                    "reference_warm_everyday_mature_age_restrained_prosody",
                    role_id="family_mother",
                    persona_id=TTSPersonaId.MOTHER,
                ),
            )
        else:
            assignments = (_v2_assignment(registration.category),)
        for assignment in assignments:
            lookup_key = (scenario_key, assignment.persona_id)
            if lookup_key in cast:
                raise RuntimeError(f"duplicate TTS cast v2 assignment: {lookup_key}")
            cast[lookup_key] = assignment
    covered_scenarios = {scenario_key for scenario_key, _ in cast}
    if covered_scenarios != set(FLOW_REGISTRY):
        raise RuntimeError("TTS cast v2 must cover every registered scenario")
    return MappingProxyType(cast)


SCENARIO_VOICE_CAST_V2 = _build_cast_v2()
SUPPORTED_TTS_CAST_VERSIONS = frozenset(version.value for version in TTSCastVersion)
_FAMILY_SCENARIO_KEYS = frozenset(
    key for key, registration in FLOW_REGISTRY.items() if registration.category == "가족"
)


def resolve_scenario_voice_assignment(
    *,
    scenario_key: str,
    cast_version: int,
    persona_id: TTSPersonaId | None,
) -> ScenarioVoiceAssignment:
    if cast_version not in SUPPORTED_TTS_CAST_VERSIONS:
        raise TTSServiceError(
            "TTS_CAST_VERSION_UNSUPPORTED",
            "지원하지 않는 음성 배역 버전입니다.",
            status_code=409,
        )
    if scenario_key not in FLOW_REGISTRY:
        raise TTSServiceError(
            "TTS_SCENARIO_UNKNOWN",
            "등록되지 않은 통화 시나리오입니다.",
            status_code=422,
        )
    if cast_version == TTSCastVersion.V1:
        if persona_id is not None:
            raise TTSServiceError(
                "TTS_PERSONA_NOT_ALLOWED",
                "이 음성 배역 버전은 가족 역할을 구분하지 않습니다.",
                status_code=422,
            )
        return SCENARIO_VOICE_CAST[scenario_key]

    is_family = scenario_key in _FAMILY_SCENARIO_KEYS
    if is_family and persona_id is None:
        raise TTSServiceError(
            "TTS_PERSONA_REQUIRED",
            "가족 통화에는 엄마 또는 아빠 역할을 지정해야 합니다.",
            status_code=422,
        )
    if not is_family and persona_id is not None:
        raise TTSServiceError(
            "TTS_PERSONA_NOT_ALLOWED",
            "가족 이외의 시나리오에는 가족 역할을 지정할 수 없습니다.",
            status_code=422,
        )
    assignment = SCENARIO_VOICE_CAST_V2.get((scenario_key, persona_id))
    if assignment is None:
        raise TTSServiceError(
            "TTS_CAST_ASSIGNMENT_MISSING",
            "승인된 음성 배역을 찾지 못했습니다.",
            status_code=503,
        )
    return assignment


def get_scenario_voice_assignment(
    category: str,
    title: str,
) -> ScenarioVoiceAssignment | None:
    return SCENARIO_VOICE_CAST.get(_key(category, title))
