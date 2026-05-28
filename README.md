# maeum-call-ai-server

FastAPI 기반 통화 시뮬레이션 AI 서버입니다.

마음콜 프로젝트에서 사용자의 통화 연습 상황을 처리하고, 시나리오별 대화 상태 전이, AI 응답 생성, 추천 답변, 음성 분석 결과를 제공하는 서버입니다.

현재는 병원 예약 시나리오를 중심으로 LangGraph 기반 상태 흐름과 Kanana 1.5 Hugging Face 모델 기반 응답 생성을 구현하고 있습니다.

---

## 주요 기능

- FastAPI 기반 /chat API 제공
- 병원 예약 시나리오 LangGraph 상태 전이
- conversationState, scenarioState 기반 대화 흐름 유지
- 사용자 발화를 user_action으로 변환하는 action parser
- 예약 가능 여부 시뮬레이션 처리
- 대안 시간 선택 및 잘못된 시간 선택 방어
- Kanana 1.5 Hugging Face 모델 기반 ai_message 생성
- LLM 응답 검증 및 retry/fallback 처리
- 추천 답변 recommendedReplies 생성
- 통화 종료 여부 shouldEndCall 반환
- pytest 기반 단위 테스트 및 통합 테스트

---

## 프로젝트 구조

    maeum-call-ai-server/
    ├── docs/
    │   ├── api-contract.md
    │   ├── hospital-reservation-flow.md
    │   ├── test-strategy.md
    │   └── implementation-log.md
    ├── llm/
    ├── routes/
    ├── services/
    │   └── flow/
    ├── tests/
    ├── main.py
    └── README.md

---

## 실행 방법

### 1. 가상환경 활성화

    source .venv/bin/activate

### 2. 서버 실행

    python -m uvicorn main:app --reload

기본 실행 주소:

    http://127.0.0.1:8000

---

## 주요 API

현재 Flutter 앱과 연동되는 핵심 API는 /chat입니다.

### POST /chat

요청 예시:

    {
      "category": "예약",
      "title": "병원 예약",
      "description": "병원 진료 예약 전화 상황",
      "userMessage": "내일 오후에 내과 진료 예약 가능할까요?",
      "conversationState": "greeting",
      "scenarioState": {},
      "history": []
    }

응답 예시:

    {
      "response": "원하시는 진료과를 알려주시면 내일 오후의 예약 가능 여부를 확인해드리겠습니다.",
      "etiquetteTip": null,
      "recommendedReplies": [
        "내과 진료를 예약하고 싶습니다.",
        "피부과 진료를 예약하고 싶습니다.",
        "어느 과로 가야 할지 상담받고 싶습니다."
      ],
      "conversationState": "asking_department",
      "shouldEndCall": false,
      "scenarioState": {
        "intent": "reservation",
        "department": null,
        "date": "내일",
        "time": "오후",
        "conversation_state": "asking_department"
      }
    }

자세한 API 계약은 docs/api-contract.md를 참고합니다.

---

## 테스트 실행

### action parser 단위 테스트

    python -m pytest tests/test_hospital_reservation_action_parser.py -v

### 병원 예약 graph flow 통합 테스트

    python -m pytest tests/test_hospital_reservation_graph_flow.py -v

### 전체 병원 예약 테스트

    python -m pytest tests/test_hospital_reservation_action_parser.py tests/test_hospital_reservation_graph_flow.py -v

현재 기준 테스트 결과:

- action parser 단위 테스트: 28 passed
- graph flow 통합 테스트: 10 passed
- 전체 테스트: 38 passed

---

## 문서

- [docs/api-contract.md](docs/api-contract.md): Flutter 연동용 /chat API 계약
- [docs/hospital-reservation-flow.md](docs/hospital-reservation-flow.md): 병원 예약 LangGraph 상태 흐름
- [docs/test-strategy.md](docs/test-strategy.md): 단위 테스트 및 통합 테스트 전략
- [docs/implementation-log.md](docs/implementation-log.md): 구현 차수별 요약 기록

---

## 현재 개발 상태

현재 서버는 병원 예약 시나리오를 중심으로 다음 기능까지 구현되어 있습니다.

- LangGraph 기반 병원 예약 상태 흐름
- Kanana 1.5 Hugging Face 모델 기반 응답 생성
- history 기반 LLM 응답 검증 및 retry/fallback 처리
- 예약 가능 여부 시뮬레이션
- user_action 기반 상태 전이
- 상태별 응답 validator 분리
- 대안 시간 검증 로직 분리
- action parser 단위 테스트
- graph flow 통합 테스트
- 예약 불가 상태에서 다른 날짜 요청 시 asking_date 전이 처리

---

## 프론트엔드 연동 계획

Flutter 앱에서는 /chat 응답의 다음 값을 저장하고 다음 요청에 다시 전달해야 합니다.

- conversationState
- scenarioState
- history
- recommendedReplies
- shouldEndCall

Flutter 연동은 서버의 병원 예약 시나리오 안정화 이후 진행합니다.
