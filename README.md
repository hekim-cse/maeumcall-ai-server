# maeum-call-ai-server

<p align="center">
  <b>FastAPI 기반 LLM 통화 시뮬레이션 AI 서버</b>
</p>

<p align="center">
  마음콜 프로젝트의 통화 시뮬레이션, 시나리오 상태 전이, AI 응답 생성, 추천 답변 생성을 담당하는 서버입니다.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/FastAPI-Server-009688?style=for-the-badge&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LangGraph-State_Flow-143D60?style=for-the-badge" />
  <img src="https://img.shields.io/badge/HuggingFace-Kanana_1.5-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black" />
  <img src="https://img.shields.io/badge/Pytest-38_passed-FF9149?style=for-the-badge&logo=pytest&logoColor=white" />
</p>

---

## 📌 프로젝트 개요

`maeum-call-ai-server`는 사용자의 통화 연습 상황을 처리하는 AI 서버입니다.

현재는 **병원 예약 시나리오**를 중심으로 LangGraph 기반 상태 흐름과 Kanana 1.5 Hugging Face 모델 기반 응답 생성을 구현하고 있습니다.

서버는 Flutter 앱으로부터 사용자의 발화와 현재 대화 상태를 전달받고, 다음 응답과 갱신된 상태를 JSON 형태로 반환합니다.

---

## ✨ 주요 기능

| 구분 | 기능 |
|---|---|
| 🧠 AI 응답 생성 | Kanana 1.5 Hugging Face 모델 기반 `ai_message` 생성 |
| 🔁 상태 전이 | LangGraph 기반 병원 예약 시나리오 흐름 관리 |
| 🗣️ 사용자 의도 분석 | 사용자 발화를 `user_action`으로 변환 |
| 🧾 상태 유지 | `conversationState`, `scenarioState`, `history` 기반 대화 흐름 유지 |
| ⏰ 예약 시뮬레이션 | 예약 가능/불가능 및 대안 시간 처리 |
| 🛡️ 응답 검증 | 상태별 validator, retry, fallback 처리 |
| 💬 추천 답변 | 상황별 `recommendedReplies` 생성 |
| 📞 통화 종료 제어 | `shouldEndCall` 기반 통화 종료 여부 반환 |
| 🧪 테스트 | action parser 단위 테스트 및 graph flow 통합 테스트 |

---

## 🏗️ 서버 구조

복잡한 상태 흐름은 LangGraph가 관리하고, 각 기능은 역할별 모듈로 분리되어 있습니다.

| 영역 | 역할 |
|---|---|
| Flutter App | 사용자 발화 입력, AI 응답과 추천 답변 표시 |
| FastAPI /chat | 요청 수신, 응답 반환 |
| LangGraph Flow | 병원 예약 상태 전이 전체 관리 |
| Info Extractor | 사용자 발화에서 진료과, 날짜, 시간 추출 |
| Action Parser | 사용자 발화를 `user_action`으로 분류 |
| State Transition | 현재 상태와 `user_action` 기준으로 다음 상태 결정 |
| Availability Simulator | 예약 가능 여부와 대안 시간 처리 |
| AI Message Generator | Kanana 1.5 기반 응답 생성 |
| Validator / Fallback | 응답 검증, retry, fallback 처리 |
| Recommended Replies | 현재 상태에 맞는 추천 답변 생성 |

전체 흐름은 다음과 같이 단순화할 수 있습니다.

1. Flutter 앱이 사용자 발화를 `/chat` API로 전송
2. FastAPI가 요청 데이터를 LangGraph로 전달
3. LangGraph가 정보 추출, `user_action` 분류, 상태 전이 수행
4. 필요한 경우 예약 가능 여부와 대안 시간 계산
5. Kanana 1.5가 현재 상태에 맞는 AI 응답 후보 생성
6. validator가 응답을 검증하고 실패 시 retry/fallback 처리
7. 서버가 `response`, `conversationState`, `scenarioState`, `recommendedReplies`, `shouldEndCall` 반환

---

## 🔌 `/chat` API 흐름

| 단계 | 처리 주체 | 설명 |
|---|---|---|
| 1 | Flutter App | 사용자 발화 입력 |
| 2 | Flutter App → FastAPI | `/chat` 요청 전송 |
| 3 | FastAPI | 요청 데이터 검증 |
| 4 | LangGraph | 정보 추출, action parser, 상태 전이 수행 |
| 5 | Kanana 1.5 | 현재 상태에 맞는 AI 응답 후보 생성 |
| 6 | Validator | 응답 검증, retry, fallback 처리 |
| 7 | FastAPI → Flutter App | 응답 문장과 갱신된 상태 반환 |
| 8 | Flutter App | AI 응답과 추천 답변 표시 |

---

## 📡 Main API

### POST `/chat`

사용자 발화와 현재 시나리오 상태를 서버로 보내면, 서버는 다음 AI 응답과 갱신된 상태를 반환합니다.

### Request Example

    {
      "category": "예약",
      "title": "병원 예약",
      "description": "병원 진료 예약 전화 상황",
      "userMessage": "내일 오후에 내과 진료 예약 가능할까요?",
      "conversationState": "greeting",
      "scenarioState": {},
      "history": []
    }

### Response Example

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

자세한 API 계약은 [docs/api-contract.md](docs/api-contract.md)를 참고합니다.

---

## 🏥 병원 예약 상태 흐름

병원 예약 시나리오는 다음 상태를 중심으로 동작합니다.

| 상태 | 역할 |
|---|---|
| `greeting` | 대화 시작 |
| `asking_department` | 진료과 확인 |
| `asking_date` | 예약 날짜 확인 |
| `asking_time` | 예약 시간 확인 |
| `confirming_info` | 예약 정보 확인 |
| `checking_availability` | 예약 가능 여부 조회 |
| `reservation_available` | 예약 가능 안내 |
| `reservation_unavailable` | 예약 불가 안내 |
| `suggest_alternative` | 대안 시간 제안 |
| `reservation_confirmed` | 예약 확정 |
| `closing` | 통화 마무리 |
| `END` | 통화 종료 |

상세한 상태 전이 흐름은 [docs/hospital-reservation-flow.md](docs/hospital-reservation-flow.md)를 참고합니다.

---

## 🧪 테스트 현황

| 테스트 구분 | 파일 | 결과 |
|---|---|---|
| Action Parser Unit Test | `tests/test_hospital_reservation_action_parser.py` | ✅ 28 passed |
| Graph Flow Integration Test | `tests/test_hospital_reservation_graph_flow.py` | ✅ 10 passed |
| Total | 병원 예약 서버 테스트 | ✅ 38 passed |

### 테스트 실행

    python -m pytest tests/test_hospital_reservation_action_parser.py tests/test_hospital_reservation_graph_flow.py -v

---

## 📁 프로젝트 구조

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

## 🚀 실행 방법

### 1. 가상환경 활성화

    source .venv/bin/activate

### 2. 서버 실행

    python -m uvicorn main:app --reload

기본 실행 주소:

    http://127.0.0.1:8000

---

## 📚 문서

| 문서 | 설명 |
|---|---|
| [api-contract.md](docs/api-contract.md) | Flutter 연동용 `/chat` API 계약 |
| [hospital-reservation-flow.md](docs/hospital-reservation-flow.md) | 병원 예약 LangGraph 상태 흐름 |
| [test-strategy.md](docs/test-strategy.md) | 단위 테스트 및 통합 테스트 전략 |
| [implementation-log.md](docs/implementation-log.md) | 구현 차수별 요약 기록 |

---

## ✅ 현재 개발 상태

현재 서버는 병원 예약 시나리오를 중심으로 다음 기능까지 구현되어 있습니다.

- LangGraph 기반 병원 예약 상태 흐름
- Kanana 1.5 Hugging Face 모델 기반 응답 생성
- history 기반 LLM 응답 검증 및 retry/fallback 처리
- 예약 가능 여부 시뮬레이션
- `user_action` 기반 상태 전이
- 상태별 응답 validator 분리
- 대안 시간 검증 로직 분리
- action parser 단위 테스트
- graph flow 통합 테스트
- 예약 불가 상태에서 다른 날짜 요청 시 `asking_date` 전이 처리

---

## 🔜 프론트엔드 연동 계획

Flutter 앱에서는 `/chat` 응답의 다음 값을 저장하고 다음 요청에 다시 전달해야 합니다.

- `conversationState`
- `scenarioState`
- `history`
- `recommendedReplies`
- `shouldEndCall`

Flutter 연동은 서버의 병원 예약 시나리오 안정화 이후 진행합니다.
