# 👨‍🏫 Professor LangGraph

> 마음콜 AI Server의 교수님 카테고리 LangGraph 구현 문서이다.  
> 교수님 시나리오는 학생이 교수님께 공손하게 요청, 문의, 전달을 연습할 수 있도록  
> 상황별 상태 흐름과 LLM 응답 검증을 함께 관리한다.

<p align="center">
  <img src="https://img.shields.io/badge/Category-Professor-6D5DFB?style=flat-square" />
  <img src="https://img.shields.io/badge/Flow-LangGraph-143D60?style=flat-square" />
  <img src="https://img.shields.io/badge/LLM-Kanana_1.5-FFD21E?style=flat-square" />
  <img src="https://img.shields.io/badge/Test-전체_회귀_테스트_통과-2EA44F?style=flat-square&logo=pytest&logoColor=white" />
</p>

---

## 📌 목차

1. [개요](#1-개요)
2. [구현 목적](#2-구현-목적)
3. [설계 방향](#3-설계-방향)
4. [지원 시나리오](#4-지원-시나리오)
5. [시나리오별 구현 요약](#5-시나리오별-구현-요약)
6. [LLM 응답 정책](#6-llm-응답-정책)
7. [모듈 역할](#7-모듈-역할)
8. [테스트 및 검증 결과](#8-테스트-및-검증-결과)
9. [구현 결과 요약](#9-구현-결과-요약)

---

## 1. 개요

Professor LangGraph는 마음콜 AI Server에서 교수님과의 전화 상황을 처리하기 위한 상태 기반 대화 흐름이다.

교수님 카테고리는 단순히 LLM이 자연스러운 문장을 생성하는 것만으로는 충분하지 않다.  
학생이 교수님께 요청, 문의, 전달을 할 때는 공손한 말투, 필요한 정보 수집, 확인 후 마무리 흐름이 함께 관리되어야 한다.

현재 교수님 카테고리에서는 다음 세 가지 시나리오를 LangGraph로 처리한다.

- 면담 예약
- 과제 문의
- 결석 사유 전달

---

## 2. 구현 목적

교수님과의 통화 상황은 사용자가 부담을 느끼기 쉬운 시나리오이다.

특히 다음과 같은 요소가 중요하다.

- 공손한 말투 유지
- 요청 또는 문의 목적 명확화
- 필요한 정보 단계적 수집
- 학생 이름 확인
- 교수님 응답 톤 유지
- 너무 가벼운 표현 방지
- 정보 확인 후 마무리 흐름 제공
- 통화 종료 여부를 프론트에서 제어할 수 있도록 상태 반환

> 🎯 핵심 목표  
> Professor LangGraph는 LLM이 자연스럽게 응답하되, 교수님 상황에 맞는 공손하고 약간 딱딱한 말투와 상태 흐름을 서버에서 안정적으로 관리하기 위한 구조이다.

---

## 3. 설계 방향

| 구분 | 설계 방향 |
|---|---|
| 🧠 LLM 응답 | 모든 응답은 LLM 생성을 우선 사용 |
| 🧑‍🏫 말투 제어 | 교수님 역할에 맞게 공손하고 약간 딱딱한 톤 유지 |
| 🔁 상태 전이 | LangGraph 기반 conversation_state 관리 |
| 🧾 정보 추출 | 시나리오별 필수 정보 추출 |
| 🗣 사용자 의도 | 확인, 변경, 후속 질문, 마무리 발화를 user_action으로 분류 |
| 🛡 응답 검증 | 반말, 농담, 너무 가벼운 표현 차단 |
| 🧱 안전 응답 | 검증 실패 시 template fallback 사용 |
| 💬 추천 답변 | 현재 상태에 맞는 recommendedReplies 생성 |
| 📦 상태 저장 | scenarioState로 다음 요청에 필요한 정보 유지 |
| 📞 종료 제어 | shouldEndCall로 통화 종료 흐름 전달 |

> 💡 구조 핵심  
> LangGraph는 LLM을 대체하지 않는다.  
> LLM이 우선 응답을 생성하고, LangGraph는 현재 대화 상태와 교수님 말투 기준을 벗어나지 않도록 결과를 검증한다.

---

## 4. 지원 시나리오

| 카테고리 | 시나리오 | LangGraph 처리 여부 | 현재 상태 |
|---|---|---|---|
| 교수님 | 🙇 면담 예약 | ✅ 지원 | 구현 완료 |
| 교수님 | 🗣 과제 문의 | ✅ 지원 | 구현 완료 |
| 교수님 | ✏️ 결석 사유 전달 | ✅ 지원 | 구현 완료 |

> ⚠️ 라우팅 기준  
> 교수님 카테고리는 category/title 기준으로 정확히 라우팅한다.  
> 단순히 “교수님” 카테고리라는 이유만으로 하나의 graph에 연결하지 않고, title을 기준으로 면담 예약, 과제 문의, 결석 사유 전달 graph를 분리한다.

---

## 5. 시나리오별 구현 요약

### 5-1. 🙇 면담 예약

면담 예약 시나리오는 학생이 교수님께 면담을 요청하고, 목적과 일정을 확인한 뒤 마무리하는 흐름이다.

| 항목 | 내용 |
|---|---|
| 주요 수집 정보 | 면담 목적, 희망 날짜, 희망 시간, 학생 이름 |
| 주요 상태 | collecting_appointment_info, confirming_info, appointment_confirmed, closing, END |
| 변경 처리 | 목적, 날짜, 시간, 이름 개별 초기화 후 재수집 |
| 응답 정책 | LLM 우선, 교수님 말투 validator 검증 후 fallback |
| 구현 특징 | 면담 목적과 일정을 확인한 뒤 교수님 응답 톤으로 마무리 |

```text
collecting_appointment_info
  ↓
confirming_info
  ↓
appointment_confirmed
  ↓
closing
  ↓
END
```

---

### 5-2. 🗣 과제 문의

과제 문의 시나리오는 학생이 과제 관련 질문을 하고, 답변 이후 추가 질문 또는 마무리로 이어지는 흐름이다.

| 항목 | 내용 |
|---|---|
| 주요 수집 정보 | 과제 주제/유형, 질문 내용, 학생 이름 |
| 주요 상태 | collecting_assignment_info, answering_assignment_question, closing, END |
| 후속 질문 | 답변 이후 추가 질문 요청 시 과제 주제와 질문 내용을 다시 수집 |
| 응답 정책 | LLM 우선, 교수님 말투 validator 검증 후 fallback |
| 구현 특징 | 질문 답변 이후 추가 질문과 종료 흐름을 모두 지원 |

```text
collecting_assignment_info
  ↓
answering_assignment_question
  ├─ 추가 질문 → collecting_assignment_info
  ↓
closing
  ↓
END
```

---

### 5-3. ✏️ 결석 사유 전달

결석 사유 전달 시나리오는 학생이 결석 날짜와 사유를 전달하고, 교수님이 내용을 확인한 뒤 참고 처리 및 종료로 이어지는 흐름이다.

| 항목 | 내용 |
|---|---|
| 주요 수집 정보 | 결석 날짜, 결석 사유, 학생 이름 |
| 선택 수집 정보 | 수업명 |
| 주요 상태 | collecting_absence_info, confirming_absence_info, absence_noted, closing, END |
| 변경 처리 | 결석 날짜, 결석 사유, 이름 개별 초기화 후 재수집 |
| 응답 정책 | LLM 우선, 교수님 말투 validator 검증 후 fallback |
| 구현 특징 | 수업명은 선택값으로 두고, MVP에서는 날짜/사유/이름을 필수값으로 관리 |

```text
collecting_absence_info
  ↓
confirming_absence_info
  ↓
absence_noted
  ↓
closing
  ↓
END
```

---

## 6. LLM 응답 정책

Professor LangGraph의 응답 정책은 다음 원칙을 따른다.

### 원칙 1. LLM 응답을 먼저 사용한다

교수님 시나리오는 정형 문장만 반복하면 실제 통화 연습 느낌이 약해질 수 있다.  
따라서 현재 상태와 수집된 정보를 기반으로 LLM 응답을 먼저 생성한다.

### 원칙 2. 교수님 말투 기준을 검증한다

교수님 역할에서는 너무 가벼운 표현이나 반말이 나오면 안 된다.

validator는 다음과 같은 표현을 차단한다.

```text
ㅋㅋ
ㅎㅎ
응
그래
오케이
넵
좋아
말해줘
괜찮아
그때 보자
알아서 해
```

### 원칙 3. 상태 의미가 맞는지 검증한다

각 상태에서는 최소한 포함되어야 하는 의미가 있다.

- 정보 수집 상태에서는 필요한 정보를 요청해야 한다.
- 면담 확인 상태에서는 수집된 면담 정보를 확인해야 한다.
- 과제 문의 답변 상태에서는 과제 문의에 대한 안내 의미가 있어야 한다.
- 결석 사유 확인 상태에서는 날짜와 사유 확인 의미가 있어야 한다.
- 종료 상태에서는 마무리 의미가 있어야 한다.

### 원칙 4. 검증 실패 시 template fallback을 사용한다

LLM 응답이 교수님 말투나 상태 의미에 맞지 않으면 그대로 사용하지 않는다.  
이 경우 `templates.py`에 정의된 안전 응답을 사용한다.

### 원칙 5. 응답은 짧고 딱딱하게 유지한다

교수님 시나리오에서는 지나치게 친근한 응답보다, 짧고 공손하며 약간 딱딱한 톤이 더 적합하다.

> ⭐ LLM 활용 기준  
> Professor LangGraph에서도 LLM 응답이 우선이다.  
> LangGraph는 LLM을 대체하는 것이 아니라, LLM이 교수님 시나리오의 말투와 상태 흐름을 벗어나지 않도록 보정하는 역할을 한다.

---

## 7. 모듈 역할

Professor LangGraph는 시나리오별 폴더를 분리하고, 공통 router에서 category/title 기준으로 각 graph에 연결한다.

| 경로 | 역할 |
|---|---|
| `services/flow/professor/router.py` | 교수님 카테고리 내 지원 가능한 graph 분기 |
| `services/flow/professor/appointment/` | 면담 예약 LangGraph |
| `services/flow/professor/assignment/` | 과제 문의 LangGraph |
| `services/flow/professor/absence/` | 결석 사유 전달 LangGraph |

시나리오별 폴더 내부는 다음 역할을 기준으로 구성된다.

| 파일 | 역할 |
|---|---|
| `state.py` | LangGraph에서 공유하는 상태 타입 정의 |
| `extractor.py` | 사용자 발화에서 필요한 정보 추출 |
| `action_parser.py` | 사용자 발화를 user_action으로 분류 |
| `policy.py` | 필수 정보 누락 여부 판단 및 scenarioState 정리 |
| `nodes.py` | LangGraph 노드 함수 정의 |
| `graph.py` | LangGraph 노드 연결 및 상태 흐름 구성 |
| `generation.py` | 상태 기반 LLM 프롬프트 구성 및 응답 생성 |
| `llm_client.py` | Hugging Face LLM 호출 래퍼 |
| `validator.py` | 교수님 말투와 상태 의미 검증 |
| `templates.py` | 검증 실패 시 사용할 안전 응답 생성 |
| `replies.py` | 현재 상태에 맞는 추천 답변 생성 |
| `response.py` | ChatRequest를 LangGraph에 연결하고 ChatResponse로 변환 |

---

## 8. 테스트 및 검증 결과

### 8-1. 교수님 카테고리 테스트 범위

| 테스트 구분 | 검증 내용 |
|---|---|
| Action Parser Test | 확인, 변경, 후속 질문, 종료 발화 분류 |
| Extractor Test | 시나리오별 필수 정보 추출 |
| Graph Flow Test | 상태 전이, 재수집, 마무리, 종료 흐름 검증 |
| Routing Test | category/title 기준 graph 라우팅 검증 |
| Chat Route Test | 실제 `/chat` 함수 기준 LangGraph 연결 검증 |
| Validator Test | 부적절한 LLM 응답 fallback 검증 |

### 8-2. 시나리오별 검증 내용

| 시나리오 | 주요 검증 내용 |
|---|---|
| 면담 예약 | 정보 수집, 확인, 수정, 확정, 종료 |
| 과제 문의 | 정보 수집, 답변, 추가 질문, 종료 |
| 결석 사유 전달 | 정보 수집, 확인, 수정, 참고 처리, 종료 |

### 8-3. 전체 회귀 테스트

예약 카테고리와 교수님 카테고리 LangGraph가 서로 충돌하지 않는지 함께 검증한다.

```text
예약 + 교수님 전체 회귀 테스트 통과
```

warning은 LangGraph serializer 관련 경고이며, 기능 실패와는 관련이 없다.

---

## 9. 구현 결과 요약

| 구분 | 결과 |
|---|---|
| LangGraph 적용 범위 | 교수님 / 면담 예약, 과제 문의, 결석 사유 전달 |
| LLM 응답 정책 | LLM 우선 사용 |
| 말투 제어 | 공손하고 약간 딱딱한 교수님 말투 검증 |
| 정보 수집 | 시나리오별 필수 정보 추출 및 누락 정보 재질문 |
| 상태 전이 | 정보 수집 → 확인/답변/참고 처리 → 마무리 → 종료 |
| 수정 처리 | 날짜, 사유, 이름 등 일부 필드 개별 초기화 후 재수집 |
| 프론트 전달 상태 | scenarioState, conversationState, recommendedReplies, shouldEndCall 반환 |
| 테스트 검증 | 예약 + 교수님 전체 회귀 테스트 통과 |

> ✅ 구현 성과  
> 교수님 카테고리는 기존 일반 LLM 응답 흐름에서 벗어나, 면담 예약, 과제 문의, 결석 사유 전달을 각각 상태 기반 LangGraph 구조로 확장했다.  
> 또한 LLM 응답을 우선 사용하면서도 교수님 상황에 맞지 않는 가벼운 표현은 validator와 template fallback으로 보정하도록 구성했다.

---

<p align="center">
  <strong>Professor LangGraph</strong><br>
  공손한 요청/문의/전달 흐름과 안정적인 상태 전이를 함께 고려한 교수님 전화 시나리오 구조이다.
</p>
