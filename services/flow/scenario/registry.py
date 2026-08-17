from __future__ import annotations

from dataclasses import dataclass

from services.flow.common.scenario_keys import canonicalize_scenario_label


@dataclass(frozen=True)
class ScenarioConfig:
    category: str
    title: str
    response_example: str
    recommended_replies: tuple[str, str, str]

    @property
    def key(self) -> str:
        return f"{canonicalize_scenario_label(self.category)}:{canonicalize_scenario_label(self.title)}"


def _config(
    category: str,
    title: str,
    response_example: str,
    replies: tuple[str, str, str],
) -> ScenarioConfig:
    return ScenarioConfig(category, title, response_example, replies)


_SCENARIOS = (
    _config(
        "가족",
        "안부인사",
        "응, 전화 잘 받았어. 오늘은 어떻게 지냈니?",
        ("오늘은 잘 지냈어.", "조금 피곤했어.", "엄마는 오늘 어땠어?"),
    ),
    _config(
        "가족",
        "일정 조율",
        "그래, 같이 일정 맞춰보자. 어느 날이 편하니?",
        ("일요일은 괜찮아.", "토요일 오후는 어때?", "이번 주는 조금 어려워."),
    ),
    _config(
        "가족",
        "도움 부탁",
        "그래, 어떤 도움이 필요한지 말해봐.",
        ("택배를 대신 받아줄 수 있어?", "잠깐 부탁할 일이 있어.", "어려우면 괜찮아."),
    ),
    _config(
        "친구",
        "생일 축하 전화",
        "고마워! 덕분에 기분 좋다.",
        ("생일 정말 축하해!", "오늘 뭐 할 거야?", "주말에 같이 보자."),
    ),
    _config(
        "친구",
        "심심해서 거는 전화",
        "나도 마침 심심했어. 편하게 얘기하자.",
        ("지금 뭐 하고 있었어?", "오늘 있었던 일 얘기해줄게.", "잠깐 통화 괜찮아?"),
    ),
    _config(
        "친구",
        "약속 잡는 전화",
        "좋아, 언제 어디서 볼지 정해보자.",
        ("일요일 오후는 어때?", "어디에서 만날까?", "이번 주는 어려울 것 같아."),
    ),
    _config(
        "친구",
        "약속 변경/취소",
        "알겠어. 가능한 다른 날짜를 같이 찾아보자.",
        ("미안한데 약속을 바꿔도 될까?", "이번 주말은 가능해.", "다음 주는 어때?"),
    ),
    _config(
        "친구",
        "스터디 제안",
        "좋지. 어떤 과목을 언제 같이 할까?",
        ("주말에 같이 공부할래?", "자료구조를 같이 하고 싶어.", "일요일 오후는 어때?"),
    ),
    _config(
        "연인",
        "안부인사",
        "응, 목소리 들으니까 좋다. 오늘 하루는 어땠어?",
        ("오늘은 무난했어.", "조금 힘든 하루였어.", "너는 오늘 어땠어?"),
    ),
    _config(
        "연인",
        "데이트 약속 잡기",
        "좋아, 우리 둘 다 편한 시간과 장소를 정해보자.",
        ("토요일 저녁은 어때?", "영화관 앞에서 만날까?", "다른 날도 괜찮아."),
    ),
    _config(
        "연인",
        "서운함 표현",
        "그렇게 느꼈구나. 어떤 점이 서운했는지 차분히 듣고 싶어.",
        ("연락이 늦어서 서운했어.", "내 마음을 알아줬으면 해.", "앞으로는 미리 말해줘."),
    ),
    _config(
        "연인",
        "사과하기",
        "알겠어. 왜 그랬는지 솔직하게 말해줘.",
        ("정말 미안해.", "내가 예민하게 굴었어.", "다음부터는 조심할게."),
    ),
    _config(
        "회사",
        "보고서 제출",
        "현재 진행률과 정확한 제출 예정 시각을 말씀해 주세요.",
        (
            "오늘 16시까지 제출하겠습니다.",
            "현재 80% 완료했습니다.",
            "지연 사유와 대안을 보고드리겠습니다.",
        ),
    ),
    _config(
        "회사",
        "진행상황 보고",
        "현재 진행률과 남은 이슈를 구체적으로 보고해 주세요.",
        ("현재 70% 진행했습니다.", "한 가지 이슈가 있습니다.", "예정대로 완료 가능합니다."),
    ),
    _config(
        "회사",
        "회의 일정 조율",
        "가능한 회의 시간과 주요 안건을 말씀해 주세요.",
        (
            "목요일 오후 2시 가능합니다.",
            "금요일 오전은 어떠신가요?",
            "안건을 먼저 공유드리겠습니다.",
        ),
    ),
    _config(
        "회사",
        "연차/반차 신청",
        "희망 일정과 업무 인수인계 계획을 말씀해 주세요.",
        (
            "내일 오후 반차를 신청합니다.",
            "업무는 오늘 인계하겠습니다.",
            "다른 날짜로 조정 가능합니다.",
        ),
    ),
)

SCENARIOS: dict[str, ScenarioConfig] = {item.key: item for item in _SCENARIOS}


def get_scenario_config(category: str, title: str) -> ScenarioConfig | None:
    key = f"{canonicalize_scenario_label(category)}:{canonicalize_scenario_label(title)}"
    return SCENARIOS.get(key)
