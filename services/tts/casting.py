from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from services.flow.common.state_contract import build_scenario_key
from services.tts.catalog import TTSVoiceId


class TTSProviderId(StrEnum):
    QWEN3_TTS = "qwen3-tts"
    NVIDIA_MAGPIE = "nvidia-magpie"


class MagpieVoiceId(StrEnum):
    ARIA = "aria"
    JASON = "jason"
    LEO = "leo"
    SOFIA = "sofia"


@dataclass(frozen=True)
class ScenarioVoiceAssignment:
    provider: TTSProviderId
    voice: str


def _qwen(voice: TTSVoiceId) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(TTSProviderId.QWEN3_TTS, voice.value)


def _magpie(voice: MagpieVoiceId) -> ScenarioVoiceAssignment:
    return ScenarioVoiceAssignment(TTSProviderId.NVIDIA_MAGPIE, voice.value)


def _key(category: str, title: str) -> str:
    return build_scenario_key(category, title)


_CAST_ENTRIES: tuple[tuple[str, ScenarioVoiceAssignment], ...] = (
    (_key("예약", "병원 예약"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("예약", "식당 예약"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("예약", "미용실 예약"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("예약", "스터디룸 예약"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("교수님", "면담 예약"), _qwen(TTSVoiceId.ERIC)),
    (_key("교수님", "과제 문의"), _qwen(TTSVoiceId.ERIC)),
    (_key("교수님", "결석 사유 전달"), _qwen(TTSVoiceId.ERIC)),
    (_key("배달", "주문 변경"), _magpie(MagpieVoiceId.JASON)),
    (_key("배달", "배달 지연 문의"), _magpie(MagpieVoiceId.JASON)),
    (_key("배달", "환불/재배달 문의"), _magpie(MagpieVoiceId.JASON)),
    (_key("시청", "여권 발급 문의"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("시청", "주민등록 등본 문의"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("시청", "대형폐기물 배출"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("고객센터", "인터넷/통화 문제 문의"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("고객센터", "요금/약정 상담"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("고객센터", "A/S 접수"), _magpie(MagpieVoiceId.SOFIA)),
    (_key("가족", "안부인사"), _magpie(MagpieVoiceId.ARIA)),
    (_key("가족", "일정 조율"), _magpie(MagpieVoiceId.ARIA)),
    (_key("가족", "도움 부탁"), _magpie(MagpieVoiceId.ARIA)),
    (_key("친구", "생일 축하 전화"), _qwen(TTSVoiceId.SERENA)),
    (_key("친구", "심심해서 거는 전화"), _qwen(TTSVoiceId.SERENA)),
    (_key("친구", "약속 잡는 전화"), _qwen(TTSVoiceId.SERENA)),
    (_key("친구", "약속 변경/취소"), _qwen(TTSVoiceId.SERENA)),
    (_key("친구", "스터디 제안"), _qwen(TTSVoiceId.SERENA)),
    (_key("연인", "안부인사"), _qwen(TTSVoiceId.UNCLE_FU)),
    (_key("연인", "데이트 약속 잡기"), _qwen(TTSVoiceId.UNCLE_FU)),
    (_key("연인", "서운함 표현"), _qwen(TTSVoiceId.UNCLE_FU)),
    (_key("연인", "사과하기"), _qwen(TTSVoiceId.UNCLE_FU)),
    (_key("회사", "보고서 제출"), _magpie(MagpieVoiceId.LEO)),
    (_key("회사", "진행상황 보고"), _magpie(MagpieVoiceId.LEO)),
    (_key("회사", "회의 일정 조율"), _magpie(MagpieVoiceId.LEO)),
    (_key("회사", "연차/반차 신청"), _magpie(MagpieVoiceId.LEO)),
)


def _build_cast() -> MappingProxyType[str, ScenarioVoiceAssignment]:
    cast: dict[str, ScenarioVoiceAssignment] = {}
    for scenario_key, assignment in _CAST_ENTRIES:
        if scenario_key in cast:
            raise RuntimeError(f"duplicate TTS cast assignment: {scenario_key}")
        cast[scenario_key] = assignment
    return MappingProxyType(cast)


SCENARIO_VOICE_CAST = _build_cast()


def get_scenario_voice_assignment(
    category: str,
    title: str,
) -> ScenarioVoiceAssignment | None:
    return SCENARIO_VOICE_CAST.get(_key(category, title))
