<div align="center">

# 마음콜 AI Server

### FastAPI 기반 LLM 통화 시뮬레이션 서버

통화가 어려운 사용자가 실제 전화 상황을 연습할 수 있도록  
사용자 발화를 분석하고, 시나리오 상태를 전이하며,  
AI 응답과 추천 답변을 생성하는 서버입니다.

<br/>

<img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/LangGraph-143D60?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Kanana_1.5-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black"/>
<img src="https://img.shields.io/badge/Pytest-48_passed-FF9149?style=for-the-badge&logo=pytest&logoColor=white"/>

<br/>
<br/>

</div>

---

## 목차

1. [프로젝트 소개](#1-프로젝트-소개)
2. [핵심 기능](#2-핵심-기능)
3. [기술 스택](#3-기술-스택)
4. [서버 구조](#4-서버-구조)
5. [API 흐름](#5-api-흐름)
6. [Main API](#6-main-api)
7. [병원 예약 시나리오](#7-병원-예약-시나리오)
8. [테스트 현황](#8-테스트-현황)
9. [프로젝트 구조](#9-프로젝트-구조)
10. [실행 방법](#10-실행-방법)
11. [문서](#11-문서)
12. [현재 개발 상태](#12-현재-개발-상태)
13. [프론트엔드 연동 계획](#13-프론트엔드-연동-계획)

---

## 1. 프로젝트 소개

마음콜 AI Server는 통화 공포 완화 앱의 AI 서버입니다.

사용자가 통화 상황에서 말한 내용을 서버로 전달하면, 서버는 현재 시나리오 상태를 판단하고 다음 AI 응답을 생성합니다.

현재는 병원 예약 시나리오를 중심으로 구현되어 있으며, 다음 흐름을 처리합니다.

<p align="center">
  <img src="docs/assets/service_flow.png" width="75%" alt="Service Flow" />
</p>

---

## 2. 핵심 기능

| 기능 | 설명 |
|---|---|
| 🧠 AI 응답 생성 | Kanana 1.5 Hugging Face 모델을 이용해 현재 대화 상태에 맞는 응답 생성 |
| 🔁 LangGraph 상태 전이 | 병원 예약 시나리오의 대화 흐름을 상태 기반으로 관리 |
| 🗣 Action Parser | 사용자 발화를 user_action으로 변환 |
| 🧾 Info Extractor | 진료과, 날짜, 시간 등 예약에 필요한 정보 추출 |
| ⏰ Availability Simulator | 예약 가능 여부와 대안 시간 시뮬레이션 |
| 🛡 Validator | 상태에 맞지 않는 LLM 응답 검증 |
| 🔄 Retry / Fallback | 응답 실패 시 재생성 또는 안전 응답으로 보정 |
| 💬 Recommended Replies | 현재 상태에 맞는 추천 답변 생성 |
| 📞 Call Ending Control | shouldEndCall 값으로 통화 종료 흐름 제어 |
| 🧪 Test Automation | action parser 단위 테스트와 graph flow 통합 테스트 구성 |

---

## 3. 기술 스택

| 영역 | 기술 |
|---|---|
| 🖥 Server Framework | FastAPI |
| 🐍 Language | Python |
| 🔁 State Flow | LangGraph |
| 🧠 LLM | Kanana 1.5 Hugging Face |
| 🧪 Test | Pytest |
| 📱 Client | Flutter |
| 📦 Response Format | JSON |

---

## 4. 서버 구조

서버는 Flutter 앱의 사용자 발화를 받아 병원 예약 시나리오 흐름을 처리하고, 갱신된 상태와 AI 응답을 JSON으로 반환합니다.

| 영역 | 역할 |
|---|---|
| 📱 Flutter App | 사용자 발화 입력, AI 응답과 추천 답변 표시 |
| 🔌 FastAPI /chat | 요청 수신, 응답 반환 |
| 🔁 LangGraph Flow | 병원 예약 상태 전이 전체 관리 |
| 🧾 Info Extractor | 사용자 발화에서 진료과, 날짜, 시간 추출 |
| 🗣 Action Parser | 사용자 발화를 user_action으로 분류 |
| 🚦 State Transition | 현재 상태와 user_action 기준으로 다음 상태 결정 |
| ⏰ Availability Simulator | 예약 가능 여부와 대안 시간 처리 |
| 🧠 AI Message Generator | Kanana 1.5 기반 응답 생성 |
| 🛡 Validator / Fallback | 응답 검증, retry, fallback 처리 |
| 💬 Recommended Replies | 현재 상태에 맞는 추천 답변 생성 |

전체 처리 흐름은 다음과 같습니다.

1. Flutter 앱이 사용자 발화를 /chat API로 전송
2. FastAPI가 요청 데이터를 LangGraph로 전달
3. LangGraph가 정보 추출, user_action 분류, 상태 전이 수행
4. 예약 가능 여부와 대안 시간 계산
5. Kanana 1.5가 현재 상태에 맞는 AI 응답 후보 생성
6. Validator가 응답을 검증하고 실패 시 retry/fallback 처리
7. 서버가 response, conversationState, scenarioState, recommendedReplies, shouldEndCall 반환

---

## 5. API 흐름

<p align="center">
  <img src="docs/assets/api_flow.png" width="82%" alt="API Flow" />
</p>

---

## 6. Main API

### POST /chat

사용자 발화와 현재 시나리오 상태를 서버로 보내면, 서버는 다음 AI 응답과 갱신된 상태를 반환합니다.

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

자세한 API 계약은 [api-contract.md](docs/api-contract.md)를 참고합니다.

---

## 7. 병원 예약 시나리오

병원 예약 시나리오는 사용자의 발화에서 예약 정보를 수집하고, 예약 가능 여부를 확인한 뒤 예약 확정 또는 대안 시간 제안으로 이어지는 구조입니다.

| 상태 | 역할 |
|---|---|
| 👋 greeting | 대화 시작 |
| 🏥 asking_department | 진료과 확인 |
| 📅 asking_date | 예약 날짜 확인 |
| ⏰ asking_time | 예약 시간 확인 |
| ✅ confirming_info | 예약 정보 확인 |
| 🔍 checking_availability | 예약 가능 여부 조회 |
| 🟢 reservation_available | 예약 가능 안내 |
| 🔴 reservation_unavailable | 예약 불가 안내 |
| 🔁 suggest_alternative | 대안 시간 제안 |
| 🎉 reservation_confirmed | 예약 확정 |
| 📞 closing | 통화 마무리 |
| 🏁 END | 통화 종료 |

상세한 상태 전이 흐름은 [hospital-reservation-flow.md](docs/hospital-reservation-flow.md)를 참고합니다.

---

## 8. 테스트 현황

| 테스트 구분 | 파일 | 결과 |
|---|---|---|
| 🧩 Action Parser Unit Test | tests/test_hospital_reservation_action_parser.py | ✅ 28 passed |
| 🔁 Graph Flow Integration Test | tests/test_hospital_reservation_graph_flow.py | ✅ 20 passed |
| ✅ Total | 병원 예약 서버 테스트 | ✅ 48 passed |

테스트 실행:

    python -m pytest tests/test_hospital_reservation_action_parser.py tests/test_hospital_reservation_graph_flow.py -v

---

## 9. 프로젝트 구조

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

## 10. 실행 방법

1. 가상환경 활성화

    source .venv/bin/activate

2. 서버 실행

    python -m uvicorn main:app --reload

기본 실행 주소:

    http://127.0.0.1:8000

---

## 11. 문서

| 문서 | 설명 |
|---|---|
| 📡 [api-contract.md](docs/api-contract.md) | Flutter 연동용 /chat API 계약 |
| 🏥 [hospital-reservation-flow.md](docs/hospital-reservation-flow.md) | 병원 예약 LangGraph 상태 흐름 |
| 🧪 [test-strategy.md](docs/test-strategy.md) | 단위 테스트 및 통합 테스트 전략 |
| 📝 [implementation-log.md](docs/implementation-log.md) | 구현 차수별 요약 기록 |

---

## 12. 현재 개발 상태

현재 서버는 병원 예약 시나리오를 중심으로 다음 기능까지 구현되어 있습니다.

- 🔁 LangGraph 기반 병원 예약 상태 흐름
- 🧠 Kanana 1.5 Hugging Face 모델 기반 응답 생성
- 🧾 history 기반 LLM 응답 검증 및 retry/fallback 처리
- ⏰ 예약 가능 여부 시뮬레이션
- 🗣 user_action 기반 상태 전이
- 🛡 상태별 응답 validator 분리
- 🔁 대안 시간 검증 로직 분리
- 🧪 action parser 단위 테스트
- 🧪 graph flow 통합 테스트
- 📅 예약 불가 상태에서 다른 날짜 요청 시 asking_date 전이 처리
- ⏰ 날짜 변경 시 기존 시간 조건 초기화 처리
- ⚡ 정형 상태에서 template-first 응답 생성 처리
- ✅ 예약 완료 상태에서 selected_time 기반 template 응답 처리
- 🕒 예약 가능 상태에서 available_time 기반 template 응답 처리

---

## 13. 프론트엔드 연동 계획

Flutter 앱에서는 /chat 응답의 다음 값을 저장하고 다음 요청에 다시 전달해야 합니다.

- conversationState
- scenarioState
- history
- recommendedReplies
- shouldEndCall

Flutter 연동은 서버의 병원 예약 시나리오 안정화 이후 진행합니다.

---

<div align="center">

### 마음콜 AI Server

실제 전화처럼 이어지는 통화 연습 환경을 만들기 위해 개발 중입니다.

</div>
