# ADR: LangGraph 통화 상태의 책임과 영속화 경계

- 상태: 채택
- 적용 버전: 2.1.0
- 범위: `/chat`의 32개 통화 시나리오

## 결정 배경

통화 시뮬레이션은 이전 턴의 수집 정보와 현재 단계를 알아야 다음 행동을 결정할 수 있다. 이를 프롬프트 한 개에 맡기면 모델의 자연어 출력, 상태 전이, 종료 판단이 결합되어 재현 가능한 테스트가 어렵다.

또한 현재 제품의 HTTP 계약은 모바일이 성공 응답의 상태를 보관하고 다음 요청에 전달하는 구조다. 이 상태에서 서버 체크포인터를 동시에 도입하면 클라이언트 상태와 서버 상태 중 어느 쪽이 원본인지 불명확해진다.

## 채택한 구조

```text
Flutter
  └─ 완료된 turns + 직전 versioned scenarioState
        ↓
FastAPI strict request validation
        ↓
exact scenario registry
        ↓
structured model output validation
        ↓
LangGraph state transition
        ↓
domain response policy
        ↓
versioned scenarioState + recommendedReplies + shouldEndCall
```

### 책임 분리

| 책임 | 담당 |
|---|---|
| 발화에서 도메인 필드와 action 추출 | 구조화 출력 모델 경계 |
| 허용 필드, 타입, action 검증 | Pydantic/도메인 validator |
| 다음 단계와 종료 여부 결정 | LangGraph 노드와 edge |
| 확정된 사실을 사용자 문장으로 표현 | 도메인 응답 정책 |
| 상태를 저장하고 다음 요청에 전달 | 모바일 클라이언트 |
| 상태의 시나리오·스키마 일치 검증 | FastAPI 상태 계약 경계 |

모델은 검증되지 않은 상태를 직접 확정하지 않는다. 서버도 모델 장애를 추정값이나 기본 문장으로 숨기지 않는다.

## 두 종류의 그래프

### 상세 그래프 7개

예약 4개와 교수님 3개는 수집 필드와 업무 순서가 명확하다. 각 그래프는 구조화 발화 분석, 필드 병합, 상태 전이, 도메인 응답 정책을 분리한다.

### 등록형 공통 그래프 25개

가족·친구·연인 등 자유 대화 시나리오는 등록된 설정과 구조화된 `{action, response, etiquette_tip}` 계약을 사용한다. 미등록 시나리오는 일반 채팅으로 우회하지 않고 실패한다.

## 상태 계약

모든 비어 있지 않은 `scenarioState`는 다음 메타데이터를 포함한다.

```json
{
  "scenario_key": "예약:병원 예약",
  "state_version": 2,
  "conversation_state": "asking_time"
}
```

- `scenario_key`: 다른 통화의 상태 혼입 차단
- `state_version`: 배포 전후 상태 스키마 불일치 차단
- allowlist: 시나리오가 소유하지 않는 필드 차단
- 이중 상태 일치 검사: 최상위와 내부 `conversation_state`의 충돌 차단
- 종료 상태 보호: `END` 이후 새 발화 차단

상태 변경이 하위 호환되지 않으면 기존 필드를 추정해서 읽지 않고 `state_version`을 올린다.

## 체크포인터 결정

현재 버전에는 LangGraph checkpointer를 사용하지 않는다. 이유는 기능 미완성이 아니라 **상태 원본을 클라이언트 한 곳으로 유지하기 위한 명시적 결정**이다. 프로세스 메모리 checkpointer는 재시작 시 상태가 사라져 현재의 명시적 HTTP 계약보다 신뢰성이 낮고, 클라이언트 상태와 결합하면 충돌 규칙이 추가된다.

다음 요구가 확정되면 서버 소유 영속 상태로 별도 마이그레이션한다.

- 여러 기기에서 같은 통화 재개
- 장시간 중단 후 재개
- 노드 단위 장애 복구와 replay
- 서버에서 대화 감사 기록 보관

그때는 영속 checkpointer와 인증된 `thread_id`를 사용하고, API 계약 버전을 올리며, 클라이언트가 임의의 전체 상태를 보내지 않도록 변경한다. 운영 환경에서 `InMemorySaver`를 영속 저장소처럼 사용하지 않는다.

## 실패 정책

| 상황 | 결과 |
|---|---|
| 미등록 시나리오 | `422 UNSUPPORTED_SCENARIO` |
| 다른 시나리오 상태 | `422 SCENARIO_STATE_MISMATCH` |
| 지원하지 않는 상태 버전 | `422 SCENARIO_STATE_VERSION_UNSUPPORTED` |
| 종료 후 추가 발화 | `409 CONVERSATION_ALREADY_ENDED` |
| 모델 공급자 장애 | 타입이 있는 5xx 오류 |
| 구조화 출력 위반 | 오류를 포함해 제한 재요청 후 502 |

## 검증 전략

- 32개 시나리오 등록과 정확한 라우팅
- 각 상세 그래프의 정상·수정·재수집·종료 전이
- 잘못된 상태 키, 버전, 필드, 종료 후 요청
- 모델 출력의 스키마·action 계약과 제한 재요청
- 모바일이 완료된 턴과 서버 상태만 다음 요청에 전달하는지 정적 검증
- 실제 모델 평가는 기본 회귀 테스트와 분리

이 설계의 핵심은 LangGraph 사용 자체가 아니라, 모델이 판단할 범위와 애플리케이션이 보장할 범위를 코드와 테스트에서 분리하는 것이다.
