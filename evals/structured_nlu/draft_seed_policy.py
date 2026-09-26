from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS


@dataclass(frozen=True)
class AIDraftSeedSpecV1:
    slug: str
    user_message: str
    intent: str | None


AI_DRAFT_SEED_SPECS_V1 = MappingProxyType(
    {
        "예약:병원 예약": AIDraftSeedSpecV1("hospital", "오늘 날씨가 맑네요.", None),
        "예약:식당 예약": AIDraftSeedSpecV1(
            "restaurant", "주말에 볼 영화 추천해 주세요.", "reservation"
        ),
        "예약:미용실 예약": AIDraftSeedSpecV1(
            "hair-salon", "요즘 읽을 만한 책이 있나요?", "reservation"
        ),
        "예약:스터디룸 예약": AIDraftSeedSpecV1(
            "study-room", "지하철 첫차 시간이 궁금해요.", "reservation"
        ),
        "교수님:면담 예약": AIDraftSeedSpecV1(
            "professor-appointment", "학교 축제는 언제 열리나요?", "appointment_booking"
        ),
        "교수님:과제 문의": AIDraftSeedSpecV1(
            "professor-assignment", "교수님 연구실 위치가 어디예요?", "assignment_inquiry"
        ),
        "교수님:결석 사유 전달": AIDraftSeedSpecV1(
            "professor-absence", "도서관 운영 시간이 궁금합니다.", "absence_notice"
        ),
        "배달:주문 변경": AIDraftSeedSpecV1(
            "delivery-change", "배달 앱 배경색을 바꿀 수 있나요?", "delivery_order_change"
        ),
        "배달:배달 지연 문의": AIDraftSeedSpecV1(
            "delivery-delay", "오늘 야구 경기 결과를 알려 주세요.", "delivery_delay_inquiry"
        ),
        "배달:환불/재배달 문의": AIDraftSeedSpecV1(
            "delivery-refund",
            "휴대폰 배경화면을 추천해 주세요.",
            "delivery_refund_redelivery",
        ),
        "시청:여권 발급 문의": AIDraftSeedSpecV1(
            "city-passport", "근처 공원 산책로를 알려 주세요.", "passport_guidance"
        ),
        "시청:주민등록 등본 문의": AIDraftSeedSpecV1(
            "city-certificate", "오늘 미세먼지는 어떤가요?", "resident_certificate_guidance"
        ),
        "시청:대형폐기물 배출": AIDraftSeedSpecV1(
            "city-bulky-waste", "시청 근처 카페를 추천해 주세요.", "bulky_waste_guidance"
        ),
        "고객센터:인터넷/통화 문제 문의": AIDraftSeedSpecV1(
            "support-network", "이번 주말 공연 일정이 궁금해요.", "network_call_issue"
        ),
        "고객센터:요금/약정 상담": AIDraftSeedSpecV1(
            "support-plan", "새로 나온 영화가 무엇인가요?", "plan_contract_consultation"
        ),
        "고객센터:a/s 접수": AIDraftSeedSpecV1(
            "support-service", "내일 비가 오는지 알려 주세요.", "service_request"
        ),
    }
)

if set(AI_DRAFT_SEED_SPECS_V1) != set(EVALUATION_CONTRACTS):
    raise RuntimeError("AI draft seed specs must exactly match the live scenarios")
