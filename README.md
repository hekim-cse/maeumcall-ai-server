<div align="center">

# 마음콜 AI Server

### FastAPI 기반 LLM 통화 시뮬레이션 서버

통화가 어려운 사용자가 실제 전화 상황을 연습할 수 있도록  
사용자 발화를 분석하고, 시나리오 상태를 관리하며,  
AI 응답과 추천 답변을 생성하는 서버입니다.

<br/>

<img src="https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
<img src="https://img.shields.io/badge/LangGraph-143D60?style=for-the-badge"/>
<img src="https://img.shields.io/badge/Kanana_1.5-FFD21E?style=for-the-badge&logo=huggingface&logoColor=black"/>
<img src="https://img.shields.io/badge/Pytest-165_passed-2EA44F?style=for-the-badge&logo=pytest&logoColor=white"/>

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
7. [LangGraph 적용 구조](#7-langgraph-적용-구조)
8. [테스트 및 검증](#8-테스트-및-검증)
9. [프로젝트 구조](#9-프로젝트-구조)
10. [실행 방법](#10-실행-방법)
11. [문서](#11-문서)
12. [구현 결과 요약](#12-구현-결과-요약)

---

## 1. 프로젝트 소개

마음콜 AI Server는 통화 공포 완화 앱의 AI 서버입니다.

사용자가 통화 상황에서 말한 내용을 서버로 전달하면, 서버는 현재 시나리오 상태를 판단하고 다음 AI 응답을 생성합니다.

단순히 LLM에게 답변 생성을 맡기는 구조가 아니라, 시나리오별로 필요한 정보를 추출하고 상태를 전이하며, 응답 검증과 fallback 처리를 통해 안정적인 통화 연습 흐름을 제공합니다.

<p align="center">
  <img src="docs/assets/service_flow.png" width="75%" alt="Service Flow" />
</p>

<table>
  <tr>
    <td>
      <strong>🎯 핵심 목표</strong><br/>
      마음콜 AI Server는 사용자가 실제 전화 상황을 단계적으로 연습할 수 있도록
      <strong>사용자 발화 분석 → 상태 판단 → LLM 응답 생성 → 추천 답변 제공</strong>까지 이어지는
      대화형 통화 시뮬레이션 서버를 목표로 합니다.
    </td>
  </tr>
</table>

---

## 2. 핵심 기능

| 기능 | 설명 |
|---|---|
| 🧠 AI 응답 생성 | Kanana 1.5 Hugging Face 모델을 이용해 현재 대화 맥락에 맞는 응답 생성 |
| 🔁 LangGraph 상태 전이 | 시나리오별 대화 흐름을 상태 기반으로 관리 |
| 🧾 정보 추출 | 사용자 발화에서 시나리오 진행에 필요한 정보 추출 |
| 🗣 사용자 행동 분류 | 사용자 발화를 confirm, change_time, ask_other_time 등 user_action으로 변환 |
| 🛡 응답 검증 | 현재 상태와 맞지 않는 LLM 응답 차단 |
| 🧱 Fallback 처리 | 검증 실패 시 안전한 template 응답 사용 |
| 💬 추천 답변 생성 | 현재 상태에 맞는 recommendedReplies 반환 |
| 📦 상태 유지 | scenarioState로 다음 요청에 필요한 상태 저장 |
| 📞 통화 종료 제어 | shouldEndCall 값으로 종료 흐름 관리 |

---

## 3. 기술 스택

| 영역 | 기술 |
|---|---|
| 🖥 Server Framework | FastAPI |
| 🐍 Language | Python 3.9+ |
| 🔁 State Flow | LangGraph |
| 🧠 LLM | Kanana 1.5 Hugging Face |
| 🧪 Test | Pytest |
| 📱 Client | Flutter |
| 📦 Response Format | JSON |

---

## 4. 서버 구조

마음콜 AI Server는 사용자 발화를 입력받아 시나리오별 처리 흐름으로 분기하고, 현재 상태에 맞는 AI 응답을 생성하는 구조입니다.

이 섹션에서는 실제 요청 처리 순서보다, 서버 내부의 주요 구성 요소와 역할을 중심으로 설명합니다.

| 영역 | 역할 |
|---|---|
| 📱 Flutter App | 사용자 발화 입력, AI 응답과 추천 답변 표시 |
| 🔌 FastAPI `/chat` | 클라이언트 요청 수신 및 응답 반환 |
| 🚦 Scenario Router | category/title 기준으로 시나리오 처리 흐름 분기 |
| 🔁 LangGraph Flow | 시나리오별 conversationState 관리 |
| 🧾 Extractor | 사용자 발화에서 필요한 정보 추출 |
| 🗣 Action Parser | 사용자 발화를 user_action으로 분류 |
| 🧠 AI Message Generator | 현재 상태 기반 LLM 응답 생성 |
| 🛡 Validator / Fallback | 상태에 맞지 않는 응답 검증 및 안전 응답 보정 |
| 💬 Recommended Replies | 현재 상태에 맞는 추천 답변 생성 |

<table>
  <tr>
    <td>
      <strong>💡 구조 핵심</strong><br/>
      서버는 <strong>요청 수신</strong>, <strong>시나리오 분기</strong>, <strong>상태 처리</strong>, 
      <strong>LLM 응답 생성</strong>, <strong>응답 검증</strong> 계층으로 나뉩니다.
      메인 서버는 공통 API 흐름을 담당하고, 세부 상태 전이는 각 시나리오별 LangGraph에서 관리합니다.
    </td>
  </tr>
</table>

---

## 5. API 흐름

`/chat` API는 사용자 발화와 현재 시나리오 상태를 입력받고, 다음 AI 응답과 갱신된 상태를 반환합니다.

아래 이미지는 클라이언트 요청부터 서버 내부 처리, 최종 응답 반환까지의 전체 흐름을 나타냅니다.

<p align="center">
  <img src="docs/assets/api_flow.png" width="82%" alt="API Flow" />
</p>

### 흐름에서 중요한 점

| 항목 | 설명 |
|---|---|
| 요청 기준 | Flutter는 `category`, `title`, `userMessage`, `conversationState`, `scenarioState`를 서버로 전달 |
| 분기 기준 | 서버는 `category/title`을 기준으로 LangGraph 적용 시나리오와 일반 LLM 흐름을 구분 |
| 상태 유지 | 서버는 다음 대화를 이어가기 위해 `conversationState`와 `scenarioState`를 함께 반환 |
| 추천 답변 | 현재 상태에서 사용자가 말하기 쉬운 문장을 `recommendedReplies`로 제공 |
| 종료 제어 | 통화가 끝나는 흐름에서는 `shouldEndCall` 값으로 프론트의 종료 처리를 제어 |

<table>
  <tr>
    <td>
      <strong>📌 API 흐름 핵심</strong><br/>
      `/chat` API는 단순히 응답 문장만 반환하지 않습니다.
      다음 발화에서 이어서 사용할 <strong>상태값</strong>과 <strong>추천 답변</strong>까지 함께 반환하여,
      사용자가 하나의 전화 상황을 자연스럽게 이어갈 수 있도록 합니다.
    </td>
  </tr>
</table>

---

## 6. Main API

### POST `/chat`

사용자 발화와 현재 시나리오 상태를 서버로 보내면, 서버는 다음 AI 응답과 갱신된 상태를 반환합니다.

요청 예시:

    {
      "category": "예약",
      "title": "식당 예약",
      "description": "식당 예약 전화 상황",
      "userMessage": "오늘 저녁 7시에 두 명 예약할 수 있나요?",
      "conversationState": "greeting",
      "scenarioState": {},
      "history": []
    }

응답 예시:

    {
      "response": "오늘 저녁 7시 두 분 예약으로 확인했습니다. 예약자 성함은 어떻게 남겨드릴까요?",
      "etiquetteTip": null,
      "recommendedReplies": [
        "김개굴 이름으로 예약해주세요.",
        "예약자는 김개굴입니다.",
        "다른 시간도 가능할까요?"
      ],
      "conversationState": "collecting_reservation_info",
      "shouldEndCall": false,
      "scenarioState": {
        "intent": "reservation",
        "date": "오늘",
        "time": "저녁 7시",
        "party_size": "2명",
        "user_name": null,
        "conversation_state": "collecting_reservation_info"
      }
    }

자세한 API 계약은 [api-contract.md](docs/api-contract.md)를 참고합니다.

---

## 7. LangGraph 적용 구조

마음콜 AI Server는 모든 시나리오를 단일 프롬프트로 처리하지 않고, 상태 전이가 필요한 시나리오부터 LangGraph 기반 구조로 확장합니다.

메인 README에서는 전체 적용 현황만 간단히 정리하고, 각 카테고리별 상세 설계는 별도 README에서 관리합니다.

| 카테고리 | LangGraph 적용 상태 | 상세 문서 |
|---|---|---|
| 📞 예약 | ✅ 적용 | [Reservation README](services/flow/reservation/README.md) |
| 🎓 교수님 | 예정 | 준비 중 |
| 🏢 회사 | 예정 | 준비 중 |
| 👪 가족 | 예정 | 준비 중 |
| 🧑‍🤝‍🧑 친구 | 예정 | 준비 중 |
| 💑 연인 | 예정 | 준비 중 |
| 🎧 고객센터 | 예정 | 준비 중 |
| 🛵 배달 | 예정 | 준비 중 |
| 🏛 시청 | 예정 | 준비 중 |

<table>
  <tr>
    <td>
      <strong>💡 문서화 원칙</strong><br/>
      메인 README는 프로젝트 전체 구조와 적용 현황만 요약합니다.
      시나리오별 상태 설계, 노드 구성, 테스트 결과, 트러블슈팅은
      각 카테고리 README에서 관리합니다.
    </td>
  </tr>
</table>

---

## 8. 테스트 및 검증

현재는 예약 카테고리 LangGraph를 중심으로 단위 테스트와 통합 테스트를 구성했습니다.

| 테스트 구분 | 검증 내용 |
|---|---|
| 🧩 Action Parser Test | 사용자 발화를 user_action으로 올바르게 분류하는지 검증 |
| 🧾 Extractor Test | 시나리오 진행에 필요한 정보 추출 검증 |
| 🔁 Graph Flow Test | 상태 전이, 확정/종료 흐름 검증 |
| 🚦 Routing Test | category/title 기준으로 올바른 graph에 연결되는지 검증 |
| 🛡 Response Validation | 현재 상태와 맞지 않는 LLM 응답을 fallback으로 보정하는지 검증 |

| 구분 | 결과 |
|---|---|
| 예약 관련 테스트 | ✅ 165 passed |
| 실패 테스트 | 없음 |
| 경고 | LangGraph serializer 관련 warning 1건 |

테스트 실행 예시:

    python -m pytest \
      tests/test_hair_salon_reservation_action_parser.py \
      tests/test_hair_salon_reservation_extractor.py \
      tests/test_hair_salon_reservation_graph_flow.py \
      tests/test_hair_salon_reservation_graph_routing.py \
      tests/test_study_room_reservation_action_parser.py \
      tests/test_study_room_reservation_extractor.py \
      tests/test_study_room_reservation_graph_flow.py \
      tests/test_study_room_reservation_graph_routing.py \
      tests/test_restaurant_reservation_action_parser.py \
      tests/test_restaurant_reservation_extractor.py \
      tests/test_restaurant_reservation_graph_flow.py \
      tests/test_restaurant_reservation_graph_routing.py \
      tests/test_reservation_graph_router.py \
      tests/test_hospital_reservation_action_parser.py \
      tests/test_hospital_reservation_graph_flow.py \
      -v

---

## 9. 프로젝트 구조

    maeum-call-ai-server/
    ├── data/
    │   ├── prompts/
    │   └── scenario/
    ├── docs/
    │   └── assets/
    ├── llm/
    ├── routes/
    ├── schemas/
    ├── services/
    │   └── flow/
    │       ├── reservation/
    │       └── ...
    ├── tests/
    ├── main.py
    └── README.md

### 주요 디렉터리

| 경로 | 설명 |
|---|---|
| `routes/` | FastAPI 라우터 및 `/chat` 엔드포인트 |
| `schemas/` | 요청/응답 데이터 모델 |
| `services/chat_service.py` | 기본 LLM 응답 생성 흐름 |
| `services/flow/` | 시나리오별 LangGraph 구현 영역 |
| `llm/` | LLM provider, prompt builder, postprocessor |
| `data/scenario/` | 시나리오 샘플 데이터 |
| `data/prompts/` | 시나리오별 프롬프트 데이터 |
| `tests/` | 단위 테스트 및 통합 테스트 |

---

## 10. 실행 방법

### 10-1. 가상환경 활성화

```bash
source .venv/bin/activate
```

### 10-2. 의존성 설치

```bash
python -m pip install -r requirements.txt
```

### 10-3. 서버 실행

```bash
python -m uvicorn main:app --reload
```

### 10-4. 접속 주소

기본 실행 주소:

```text
http://127.0.0.1:8000
```

API 문서:

```text
http://127.0.0.1:8000/docs
```

---


## 11. 문서

| 문서 | 설명 |
|---|---|
| 📡 [api-contract.md](docs/api-contract.md) | Flutter 연동용 `/chat` API 요청/응답 계약 |
| 📞 [Reservation LangGraph README](services/flow/reservation/README.md) | 예약 카테고리 LangGraph 통합 설계 및 구현 요약 |

---

## 12. 구현 결과 요약

| 구분 | 결과 |
|---|---|
| 서버 구조 | FastAPI 기반 `/chat` API 구성 |
| LLM 연동 | Kanana 1.5 Hugging Face 기반 응답 생성 |
| 상태 관리 | LangGraph 기반 conversationState 관리 구조 도입 |
| 적용 시나리오 | 예약 카테고리 우선 적용 |
| 응답 안정성 | validator와 template fallback으로 상태 의미 보정 |
| 추천 답변 | 현재 상태에 맞는 recommendedReplies 생성 |
| 클라이언트 상태 유지 | scenarioState로 다음 요청에 필요한 상태 반환 |
| 테스트 검증 | 예약 관련 테스트 165개 통과 |

<table>
  <tr>
    <td>
      <strong>✅ 구현 성과</strong><br/>
      마음콜 AI Server는 단순 LLM 응답 서버가 아니라,
      사용자의 발화를 기반으로 현재 상태를 판단하고 시나리오 흐름을 이어가는
      <strong>상태 기반 통화 시뮬레이션 서버</strong>로 확장되고 있습니다.
      현재는 예약 카테고리를 기준으로 LangGraph, validator, fallback 구조를 검증했으며,
      이후 다른 전화 상황에도 동일한 구조를 확장할 수 있도록 문서와 폴더 구조를 분리했습니다.
    </td>
  </tr>
</table>

---

<div align="center">

### 마음콜 AI Server

실제 전화처럼 이어지는 통화 연습 환경을 만들기 위해 개발 중입니다.

</div>
