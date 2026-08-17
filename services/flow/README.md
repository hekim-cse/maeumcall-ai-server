# LangGraph flow architecture

`services/flow`는 MaeumCall의 32개 통화 시나리오를 라우팅하고 대화 상태를 전이하는 애플리케이션 계층입니다.

## 설계 원칙

1. `category`와 `title`의 정확한 등록 키로 그래프를 선택합니다.
2. 16개 상세 시나리오의 상태 전이 데이터는 검증된 LLM JSON만 사용합니다.
3. 중앙 실행 레지스트리는 각 시나리오를 상세 또는 등록형 중 하나의 실행 유형에만 연결합니다.
4. 모델 출력이 계약을 위반하면 오류 원인을 포함해 한 번 재시도합니다.
5. 재시도 실패나 모델 미설정은 `AIServiceError`로 전달하며 추정값을 만들지 않습니다.
6. 예약 결과처럼 서버가 이미 확정한 사실은 도메인 응답 정책이 문장으로 표현합니다.
7. 등록되지 않은 시나리오는 일반 모델로 우회하지 않고 `422 UNSUPPORTED_SCENARIO`를 반환합니다.

## 요청 흐름

```text
POST /chat
  └─ central flow registry
       ├─ detailed ─ 예약 4개·교수님 3개·배달 3개·시청 3개·고객센터 3개
       └─ registered ─ 가족·친구·연인·회사 16개 등록 시나리오 공통 그래프
```

상세 그래프의 처리 경계는 다음과 같습니다.

```text
사용자 발화
  → strict JSON 생성
  → 스키마·허용 action 검증
  → LangGraph 상태 전이
  → 도메인 응답 정책
  → recommendedReplies와 scenarioState 반환
```

시나리오 그래프는 OpenAI 응답을 다음 계약으로 생성합니다.

```json
{
  "action": "continue",
  "response": "상대 역할의 다음 발화",
  "etiquette_tip": null
}
```

`action`, `response`, `etiquette_tip`을 한 객체로 검증하므로 응답 문장과 종료 상태가 서로 어긋나지 않습니다.

## 디렉터리 책임

```text
services/flow/
├── registry.py
├── common/
│   ├── scenario_keys.py
│   └── state_contract.py
├── scenario/
│   ├── registry.py
│   ├── state.py
│   ├── graph.py
│   └── response.py
├── service_workflow/
│   ├── contracts.py
│   ├── structured.py
│   ├── nodes.py
│   └── graph.py
├── delivery/
│   └── contracts.py
├── cityhall/
│   └── contracts.py
├── support/
│   └── contracts.py
├── reservation/
│   ├── hospital/
│   ├── restaurant/
│   ├── hair_salon/
│   ├── study_room/
│   └── common/
└── professor/
    ├── appointment/
    ├── assignment/
    └── absence/
```

`service_workflow`은 배달·시청·고객센터의 상태 실행 코드를 공유한다. 필드, 코드형 업무 분기, 상태 이름, 확인 문장, 외부 처리 경계는 각 카테고리의 `contracts.py`에 명시하므로 9개 시나리오는 서로 다른 독립 그래프로 컴파일된다. A/S 안전 이상은 `safety_action_required` 보호 상태로 먼저 전환되어 일반 진단과 접수를 중단한다.

상세 시나리오에서 자주 사용하는 파일의 책임은 다음과 같습니다.

| 파일 | 책임 |
|---|---|
| `registry.py` | 32개 시나리오 키와 상세·등록형 실행 계약의 단일 진입점 |
| `state.py` | 그래프 공유 상태 타입 |
| `llm_structured.py` | 엄격한 JSON 계약과 시나리오별 필드 검증 |
| `nodes.py` | 정보 병합, 필수 필드 계산, 상태 전이 |
| `graph.py` | 노드와 조건부 edge 구성 |
| `response_policy.py` | 검증된 서버 상태를 제품 문장으로 표현 |
| `replies.py` | 상태별 승인된 사용자 답변 후보 |
| `response.py` | `ChatRequest`와 `ChatResponse` 경계 변환 |
| `common/state_contract.py` | 시나리오 키·상태 버전·허용 필드 검증과 공통 응답 조립 |

## 오류 정책

| 상황 | 처리 |
|---|---|
| 모델/키 미설정 | HTTP 503, `AI_PROVIDER_UNAVAILABLE` |
| 모델 호출 실패 | HTTP 502, `AI_PROVIDER_EXECUTION_FAILED` |
| JSON 또는 필드 계약 위반 | 오류 내용을 포함해 1회 재시도 |
| 재시도 후에도 계약 위반 | HTTP 502, `AI_RESPONSE_VALIDATION_FAILED` |
| 미등록 시나리오 | HTTP 422, `UNSUPPORTED_SCENARIO` |

## 테스트 경계

기본 테스트는 모델 호출 경계를 test double로 대체해 상태 전이를 재현 가능하게 검증합니다. 실제 Kanana 호출은 `integration` marker에서만 실행합니다.

- 정상 JSON의 필드 병합
- markdown이나 설명이 섞인 출력의 재시도
- 허용되지 않은 action의 명시적 실패
- 필수 정보 재수집과 단일 필드 변경
- 업무 취소와 분기별 처리 준비 상태
- 중첩 `fields`의 키·타입·누락 목록·상태 일관성 검증
- 외부 조회 결과를 만들지 않는 처리 경계
- 예약 가능/불가/대안/확정/종료 전이
- 모바일 이모지 제목의 등록 키 정규화
- 모델 장애의 API 오류 계약

현재 상태 원본은 모바일이 보관하는 버전 지정 `scenarioState` 하나로 유지합니다. 서버 checkpointer를 동시에 두지 않는 근거와 서버 소유 영속 상태로 전환할 조건은 [상태 책임 ADR](../../docs/architecture/langgraph_call_flow_design.md)에 기록합니다. 다음 운영 단계는 노드별 latency/error 지표와 시나리오별 평가 데이터셋 구축입니다.
