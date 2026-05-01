# services/prompt_registry.py
from pathlib import Path
import re

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
    return PROMPT_ROOT / CATEGORY_DIR_MAP.get(category, category)

# 시나리오 매핑(이모지 포함 원문)
SCENARIO_PROMPTS = {
    ("교수님", "🗣️ 과제 문의"):      PROMPT_ROOT / "professor" / "assignment_inquiry.ini",
    ("교수님", "🙇‍♀️ 면담 예약"):     PROMPT_ROOT / "professor" / "appointment_booking.ini",
    ("교수님", "✏️ 결석 사유 전달"):  PROMPT_ROOT / "professor" / "absence_notice.ini",
    ("회사", "🖥️ 보고서 제출"):      PROMPT_ROOT / "company"   / "report_submit.ini",
    ("회사", "📊 진행상황 보고"):      PROMPT_ROOT / "company"   / "status_update.ini",
    ("회사", "📅 회의 일정 조율"):     PROMPT_ROOT / "company"   / "meeting_schedule.ini",
    ("회사", "🏖️ 연차/반차 신청"):     PROMPT_ROOT / "company"   / "leave_request.ini",
}

def _normalize_key(category: str, title: str) -> tuple[str, str]:
    def norm(s: str) -> str:
        s = re.sub(r"[^\w\s가-힣/+-]", " ", s)
        s = re.sub(r"\s+", " ", s).strip().lower()
        return s
    return (norm(category), norm(title))

ALIASES = {
    _normalize_key("교수님", "과제 문의"):      PROMPT_ROOT / "professor" / "assignment_inquiry.ini",
    _normalize_key("교수님", "면담 예약"):       PROMPT_ROOT / "professor" / "appointment_booking.ini",
    _normalize_key("교수님", "결석 사유 전달"):  PROMPT_ROOT / "professor" / "absence_notice.ini",
    _normalize_key("회사", "보고서 제출"):       PROMPT_ROOT / "company" / "report_submit.ini",
    _normalize_key("회사", "진행상황 보고"):     PROMPT_ROOT / "company" / "status_update.ini",
    _normalize_key("회사", "회의 일정 조율"):    PROMPT_ROOT / "company" / "meeting_schedule.ini",
    _normalize_key("회사", "연차/반차 신청"):    PROMPT_ROOT / "company" / "leave_request.ini",
}

DEFAULT_PROMPT = PROMPT_ROOT / "general" / "default.ini"

def get_prompt_path(category: str, title: str) -> Path:
    p = SCENARIO_PROMPTS.get((category, title))
    if p:
        return p
    key = _normalize_key(category, title)
    if key in ALIASES:
        return ALIASES[key]
    return DEFAULT_PROMPT