# services/prompt_registry.py
from pathlib import Path

from llm.errors import PromptConfigurationError
from services.flow.common.scenario_keys import canonicalize_scenario_label

BASE_DIR = Path(__file__).resolve().parents[1]
PROMPT_ROOT = BASE_DIR / "data" / "prompts"

# 한글 카테고리 → 폴더명
CATEGORY_DIR_MAP = {
    "가족": "family",
    "친구": "friends",
    "연인": "couple",
    "회사": "company",
    "예약": "reservation",
    "교수님": "professor",
    "고객센터": "support",
    "시청": "cityhall",
    "배달": "delivery",
}

def category_dir_path(category: str) -> Path:
    normalized = canonicalize_scenario_label(category)
    directory = CATEGORY_DIR_MAP.get(normalized)
    if directory is None:
        raise PromptConfigurationError(f"Unregistered prompt category: {category}")
    return PROMPT_ROOT / directory

def _normalize_key(category: str, title: str) -> tuple[str, str]:
    return (
        canonicalize_scenario_label(category),
        canonicalize_scenario_label(title),
    )

_SCENARIO_FILES = {
    ("가족", "안부인사"): "family/greeting.ini",
    ("가족", "일정 조율"): "family/schedule.json",
    ("가족", "도움 부탁"): "family/small_favor.ini",
    ("친구", "생일 축하 전화"): "friends/friends_birthday.json",
    ("친구", "심심해서 거는 전화"): "friends/friends_bored_call.json",
    ("친구", "약속 잡는 전화"): "friends/friends_make_plan.json",
    ("친구", "약속 변경/취소"): "friends/friends_reschedule_cancel.json",
    ("친구", "스터디 제안"): "friends/friends_study_proposal.json",
    ("연인", "안부인사"): "couple/couple_greeting.json",
    ("연인", "데이트 약속 잡기"): "couple/couple_date_plan.json",
    ("연인", "서운함 표현"): "couple/couple_express_disappointment.json",
    ("연인", "사과하기"): "couple/couple_apology.json",
    ("회사", "보고서 제출"): "company/company_report_submit.json",
    ("회사", "진행상황 보고"): "company/company_status_update.json",
    ("회사", "회의 일정 조율"): "company/company_meeting_schedule.json",
    ("회사", "연차/반차 신청"): "company/company_leave_request.json",
    ("배달", "주문 변경"): "delivery/delivery_order_change.json",
    ("배달", "배달 지연 문의"): "delivery/delivery_delay_inquiry.json",
    ("배달", "환불/재배달 문의"): "delivery/delivery_refund_redelivery.json",
    ("시청", "여권 발급 문의"): "cityhall/cityhall_passport_inquiry.json",
    ("시청", "주민등록 등본 문의"): "cityhall/cityhall_resident_certificate.json",
    ("시청", "대형폐기물 배출"): "cityhall/cityhall_bulk_waste.json",
    ("고객센터", "인터넷/통화 문제 문의"): "support/support_network_issue.json",
    ("고객센터", "요금/약정 상담"): "support/support_plan_contract.json",
    ("고객센터", "A/S 접수"): "support/support_service_request.json",
    ("교수님", "과제 문의"): "professor/professor_assignment_inquiry.json",
    ("교수님", "면담 예약"): "professor/professor_appointment_booking.json",
    ("교수님", "결석 사유 전달"): "professor/professor_absence_notice.json",
    ("예약", "식당 예약"): "reservation/reservation_restaurant.json",
    ("예약", "병원 예약"): "reservation/reservation_hospital.json",
    ("예약", "미용실 예약"): "reservation/reservation_hair_salon.json",
    ("예약", "스터디룸 예약"): "reservation/reservation_study_room.json",
}

ALIASES = {
    _normalize_key(category, title): PROMPT_ROOT / relative_path
    for (category, title), relative_path in _SCENARIO_FILES.items()
}

def get_prompt_path(category: str, title: str) -> Path:
    key = _normalize_key(category, title)
    path = ALIASES.get(key)
    if path is None:
        raise PromptConfigurationError(
            f"Unregistered prompt scenario: {category} / {title}"
        )
    return path


def is_registered_prompt(category: str, title: str) -> bool:
    return _normalize_key(category, title) in ALIASES
