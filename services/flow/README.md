# Flow Architecture

> 마음콜 AI Server의 시나리오별 LangGraph 구조를 정리한 문서이다.  
> 각 전화 상황은 category/title 기준으로 라우팅되며, 상태 전이가 필요한 시나리오는 LangGraph 기반으로 처리한다.

---

## 1. 개요

`services/flow`는 마음콜 AI Server에서 상태 기반 대화 흐름을 담당하는 영역이다.

기본 LLM 응답만으로 처리하기 어려운 전화 상황에 대해, 사용자 발화에서 필요한 정보를 추출하고 현재 상태를 판단한 뒤, LLM 응답과 추천 답변을 생성한다.

현재 LangGraph가 적용된 카테고리는 다음과 같다.

| 카테고리 | 적용 시나리오 |
|---|---|
| 예약 | 병원 예약, 식당 예약, 미용실 예약, 스터디룸 예약 |
| 교수님 | 면담 예약, 과제 문의, 결석 사유 전달 |

---

## 2. 라우팅 구조

메인 `/chat` API는 먼저 category/title 기준으로 LangGraph 지원 여부를 확인한다.

지원되는 시나리오이면 해당 카테고리 router를 통해 개별 graph로 연결하고, 지원되지 않는 시나리오는 기존 일반 LLM 흐름을 사용한다.

```text
/chat
  ↓
reservation router
  ├─ 병원 예약
  ├─ 식당 예약
  ├─ 미용실 예약
  └─ 스터디룸 예약

professor router
  ├─ 면담 예약
  ├─ 과제 문의
  └─ 결석 사유 전달
```

라우팅은 단순 키워드가 아니라 `category/title` 기준으로 수행한다.

이는 같은 “예약”이라는 단어가 들어가더라도 병원, 식당, 미용실, 스터디룸의 상태 흐름이 서로 다르고, 교수님 카테고리 안에서도 면담 예약, 과제 문의, 결석 사유 전달의 처리 흐름이 다르기 때문이다.

---

## 3. 카테고리별 구조

현재 `services/flow` 구조는 다음과 같다.

```text
services/flow/
├── reservation/
│   ├── hospital/
│   ├── restaurant/
│   ├── hair_salon/
│   ├── study_room/
│   ├── common/
│   └── router.py
│
└── professor/
    ├── appointment/
    ├── assignment/
    ├── absence/
    └── router.py
```

예약 카테고리는 병원, 식당, 미용실, 스터디룸 예약 시나리오를 담당한다.

교수님 카테고리는 면담 예약, 과제 문의, 결석 사유 전달 시나리오를 담당한다.

---

## 4. 시나리오 폴더 표준 구조

각 시나리오 폴더는 다음 파일 구성을 기준으로 한다.

| 파일 | 역할 |
|---|---|
| `state.py` | LangGraph에서 공유하는 상태 타입 정의 |
| `extractor.py` | 사용자 발화에서 시나리오 진행에 필요한 정보 추출 |
| `action_parser.py` | 사용자 발화를 user_action으로 분류 |
| `policy.py` | 필수 정보 누락 여부 판단 및 scenarioState 정리 |
| `availability.py` | 예약 가능 여부 또는 대안 시간 계산 |
| `nodes.py` | LangGraph 노드 함수 정의 |
| `graph.py` | LangGraph 노드 연결 및 상태 흐름 구성 |
| `generation.py` | 상태 기반 LLM 프롬프트 구성 및 응답 생성 |
| `llm_client.py` | Hugging Face LLM 호출 래퍼 |
| `validator.py` | LLM 응답이 현재 상태 의미에 맞는지 검증 |
| `templates.py` | 검증 실패 시 사용할 안전 응답 생성 |
| `replies.py` | 현재 상태에 맞는 추천 답변 생성 |
| `response.py` | ChatRequest를 LangGraph에 연결하고 ChatResponse로 변환 |

`availability.py`는 예약 카테고리처럼 가능 여부 시뮬레이션이 필요한 경우에만 사용한다.

---

## 5. 공통 처리 흐름

LangGraph 적용 시나리오는 일반적으로 다음 흐름을 따른다.

```text
사용자 발화 입력
  ↓
정보 추출
  ↓
사용자 행동 분류
  ↓
필수 정보 누락 여부 판단
  ↓
상태 전이
  ↓
LLM 응답 생성
  ↓
validator 검증
  ↓
template fallback
  ↓
recommendedReplies 생성
  ↓
ChatResponse 반환
```

이 구조를 통해 서버는 단순히 LLM 응답 문장만 반환하지 않고, 다음 대화를 이어가기 위한 `conversationState`, `scenarioState`, `recommendedReplies`, `shouldEndCall`을 함께 반환한다.

---

## 6. LLM 응답 정책

기본 원칙은 LLM 응답을 우선 사용하는 것이다.

다만 상태 안정성이 중요한 일부 정형 상태에서는 template-first 정책을 사용할 수 있다.

| 구분 | 정책 |
|---|---|
| 교수님 카테고리 | LLM 우선 생성 후 validator 검증, 실패 시 fallback |
| 예약 카테고리 | LLM 우선이 기본이나, 예약 확정/종료/가능 여부 안내 등 일부 정형 상태는 template-first 허용 |

이 구조는 자연스러운 LLM 응답과 안정적인 상태 전이를 함께 만족하기 위한 절충이다.

교수님 카테고리의 경우 실제 전화 연습 느낌을 살리기 위해 LLM 응답을 우선 사용한다.  
대신 교수님 말투에 맞지 않는 반말, 농담, 지나치게 가벼운 표현은 validator에서 차단하고 template fallback으로 보정한다.

예약 카테고리의 경우 예약 확정, 종료, 가능 여부 안내처럼 상태 의미가 강한 구간에서는 정확성이 중요하므로 일부 상태에서 template-first 방식을 허용한다.

---

## 7. 휴리스틱 코드와 현재 한계

현재 일부 로직은 정규식과 키워드 기반 휴리스틱으로 구현되어 있다.

대표적인 예시는 다음과 같다.

- 날짜, 시간, 이름 추출을 위한 정규식
- `confirm`, `change_time`, `end_call` 같은 user_action 분류 키워드
- 너무 가벼운 말투를 차단하기 위한 blocklist
- category/title 기반 router 분기

이 방식은 MVP 단계에서 다음 장점이 있다.

- 동작이 예측 가능하다.
- 테스트 작성이 쉽다.
- LLM 출력 변동에 덜 흔들린다.
- 시나리오별 상태 흐름을 명확하게 검증할 수 있다.

다만 시나리오가 늘어나면 중복 코드가 증가할 수 있다.  
특히 `action_parser.py`, `validator.py`, `extractor.py`에서 비슷한 형태의 키워드 매칭 로직이 반복될 수 있다.

---

## 8. 실무형 개선 방향

장기적으로는 다음 공통 모듈을 도입할 수 있다.

```text
services/flow/common/
├── text_matcher.py
├── tone_validator.py
├── date_time_extractor.py
├── name_extractor.py
├── response_builder.py
└── scenario_registry.py
```

개선 방향은 다음과 같다.

| 현재 구조 | 개선 방향 |
|---|---|
| 시나리오별 `_contains_any` 반복 | 공통 text matcher로 분리 |
| validator마다 말투 차단 단어 반복 | 공통 tone validator로 분리 |
| extractor마다 이름 추출 정규식 반복 | 공통 name extractor로 분리 |
| router에서 category/title 직접 비교 | scenario registry 기반 라우팅 |
| templates/replies 반복 | 시나리오 config 기반 응답 후보 관리 |

단, 현재는 테스트가 안정적으로 통과하고 있으므로 기능 제출 전에는 대규모 리팩토링보다 문서화와 개선 후보 정리를 우선한다.

---

## 9. 테스트 전략

LangGraph 적용 시나리오는 다음 테스트를 기준으로 검증한다.

| 테스트 | 목적 |
|---|---|
| action parser test | 사용자 발화가 올바른 user_action으로 분류되는지 검증 |
| extractor test | 필요한 정보가 정확히 추출되는지 검증 |
| graph flow test | 상태 전이와 재수집 흐름 검증 |
| routing test | category/title 기준 graph 연결 검증 |
| chat route test | 실제 `/chat` 함수 기준 응답 구조 검증 |

테스트는 단순 성공 여부뿐 아니라 다음 항목을 함께 검증한다.

- 잘못된 graph로 라우팅되지 않는지
- 필수 정보가 누락되면 수집 상태를 유지하는지
- 사용자가 일부 정보를 수정하면 해당 필드만 초기화되는지
- LLM 응답이 상태 의미와 맞지 않으면 fallback되는지
- 통화 종료 상태에서 shouldEndCall이 true로 반환되는지

---

## 10. 릴리즈 기준 구현 성과 요약

예약 카테고리는 v1.1.0부터 v1.4.1까지 병원, 식당, 미용실, 스터디룸 예약과 문서 정리를 단계적으로 반영했다.

교수님 카테고리는 v1.5.0부터 v1.7.1까지 면담 예약, 과제 문의, 결석 사유 전달과 문서 정리를 순차적으로 반영했다.

이를 통해 마음콜 AI Server는 단순 LLM 응답 서버가 아니라, 사용자의 발화를 분석하고 시나리오별 상태를 관리하는 상태 기반 통화 시뮬레이션 서버로 확장되었다.

핵심 구현 성과는 다음과 같다.

- category/title 기반 LangGraph 라우팅 구조 구현
- 시나리오별 상태 전이 graph 구성
- 사용자 발화 기반 정보 추출
- user_action 기반 상태 분기
- LLM 우선 응답 생성
- validator 기반 응답 의미 검증
- template fallback 기반 안전 응답 처리
- recommendedReplies 생성
- scenarioState 기반 프론트 상태 유지
- action parser, extractor, graph flow, routing, chat route 테스트 구성

---

## 11. 리팩토링 우선순위

현재 구조에서 실무형으로 개선하기 위한 리팩토링 우선순위는 다음과 같다.

| 우선순위 | 대상 | 이유 |
|---|---|---|
| 1 | 공통 말투 검증 모듈 | 교수님 validator에서 반복되는 blocklist를 안전하게 공통화 가능 |
| 2 | 공통 text matcher | `_contains_any` 반복 제거 가능 |
| 3 | 공통 이름 추출기 | 교수님/예약 extractor에 반복되는 이름 추출 정규식 공통화 가능 |
| 4 | scenario registry | router의 category/title 분기를 선언형으로 관리 가능 |
| 5 | 공통 response builder | ChatResponse 변환 로직 반복 제거 가능 |

첫 번째 리팩토링은 영향 범위가 작고 테스트로 검증하기 쉬운 `tone_validator.py` 공통화부터 진행한다.
