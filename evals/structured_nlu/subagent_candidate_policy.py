from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from evals.structured_nlu.contracts import EVALUATION_CONTRACTS


@dataclass(frozen=True)
class AISubagentCandidateSpecV1:
    """One AI-generated alternative that still requires a human rewrite."""

    slug: str
    user_message: str
    drafting_rationale: str


AI_SUBAGENT_CANDIDATE_SPECS_V1 = MappingProxyType(
    {
        "예약:병원 예약": AISubagentCandidateSpecV1(
            "hospital",
            "근처에서 우산을 살 수 있을까요?",
            "진료과·예약 일시·예약자 정보가 없는 생활 질문이므로 unknown이다.",
        ),
        "예약:식당 예약": AISubagentCandidateSpecV1(
            "restaurant",
            "냉장고 적정 온도는 몇 도인가요?",
            "식당 예약과 무관하고 예약 필드가 없으므로 unknown이다.",
        ),
        "예약:미용실 예약": AISubagentCandidateSpecV1(
            "hair-salon",
            "사진을 인화하려면 어디로 가야 하나요?",
            "미용 서비스·예약 일시·디자이너와 무관하므로 unknown이다.",
        ),
        "예약:스터디룸 예약": AISubagentCandidateSpecV1(
            "study-room",
            "노트북 배터리를 오래 쓰는 방법이 궁금해요.",
            "스터디룸 날짜·시작 시간·인원·이용 시간과 무관하므로 unknown이다.",
        ),
        "교수님:면담 예약": AISubagentCandidateSpecV1(
            "professor-appointment",
            "교내 체육관은 몇 시에 닫나요?",
            "시간 질문이지만 교수 면담 시간이 아니므로 예약 필드를 추출하지 않는다.",
        ),
        "교수님:과제 문의": AISubagentCandidateSpecV1(
            "professor-assignment",
            "강의실 에어컨은 어디서 켜나요?",
            "질문 형태여도 과제에 관한 질문이 아니므로 업무 필드를 채우지 않는다.",
        ),
        "교수님:결석 사유 전달": AISubagentCandidateSpecV1(
            "professor-absence",
            "학생식당에 채식 메뉴도 있나요?",
            "학교 맥락이지만 결석 전달과 무관하고 결석 필드가 없으므로 unknown이다.",
        ),
        "배달:주문 변경": AISubagentCandidateSpecV1(
            "delivery-change",
            "배달 기사 모집 공고는 어디서 보나요?",
            "배달이라는 단어가 있지만 주문 변경이 아닌 구직 질문이므로 unknown이다.",
        ),
        "배달:배달 지연 문의": AISubagentCandidateSpecV1(
            "delivery-delay",
            "김치찌개를 맛있게 끓이는 법을 알려 주세요.",
            "주문·지연·해결 요청이 없는 조리법 질문이므로 unknown이다.",
        ),
        "배달:환불/재배달 문의": AISubagentCandidateSpecV1(
            "delivery-refund",
            "종이비행기를 멀리 날리려면 어떻게 접어야 하나요?",
            "주문 문제·증빙·환불 또는 재배달 요청이 없으므로 unknown이다.",
        ),
        "시청:여권 발급 문의": AISubagentCandidateSpecV1(
            "city-passport",
            "시립 수영장은 무슨 요일에 쉬나요?",
            "시청 관련 시설 질문이지만 여권 신청·발급 정보가 없으므로 unknown이다.",
        ),
        "시청:주민등록 등본 문의": AISubagentCandidateSpecV1(
            "city-certificate",
            "버스에서 잃어버린 물건은 어디에 문의하나요?",
            "공공 문의처럼 보여도 등본 종류·발급 채널·신청 관계가 없으므로 unknown이다.",
        ),
        "시청:대형폐기물 배출": AISubagentCandidateSpecV1(
            "city-bulky-waste",
            "도서관 회원증은 어디서 만들 수 있나요?",
            "공공서비스 질문이지만 대형폐기물 배출 업무와 무관하므로 unknown이다.",
        ),
        "고객센터:인터넷/통화 문제 문의": AISubagentCandidateSpecV1(
            "support-network",
            "화분에는 물을 며칠마다 줘야 하나요?",
            "인터넷·통화 장애나 조치 이력이 없는 원예 질문이므로 unknown이다.",
        ),
        "고객센터:요금/약정 상담": AISubagentCandidateSpecV1(
            "support-plan",
            "이번 달 보름달은 언제 뜨나요?",
            "요금·약정·서비스 상담과 무관해 상담 필드를 추출하면 안 된다.",
        ),
        "고객센터:a/s 접수": AISubagentCandidateSpecV1(
            "support-service",
            "근처에서 자전거를 빌릴 수 있는 곳을 알려 주세요.",
            "제품 고장·접수·안전 정보가 전혀 없으므로 greeting에서 unknown이다.",
        ),
    }
)

if set(AI_SUBAGENT_CANDIDATE_SPECS_V1) != set(EVALUATION_CONTRACTS):
    raise RuntimeError("AI subagent candidate specs must exactly match the live scenarios")
