# API Contract

이 문서는 Flutter 앱과 MaeumCall AI Server 2.1 사이의 통화 상태 계약을 정의한다. 필드가 추가되거나 잘못된 타입이 전달되면 서버는 이를 무시하지 않고 `422 REQUEST_VALIDATION_FAILED`로 거부한다.

## POST `/chat`

### 요청

| 필드 | 타입 | 필수 | 규칙 |
|---|---|---:|---|
| `category` | string | 예 | 등록된 시나리오 카테고리, 1~50자 |
| `title` | string | 예 | 등록된 시나리오 제목, 1~100자 |
| `description` | string | 예 | 화면에 등록된 시나리오 설명, 최대 2,000자 |
| `userMessage` | string | 예 | 현재 사용자 발화, 1~4,000자 |
| `nickname` | string/null | 아니요 | 사용자 표시 이름, 최대 50자 |
| `turns` | array | 아니요 | 완료된 이전 턴, 최대 100개 |
| `history` | array | 아니요 | `turns`와 동일한 대체 필드 |
| `conversationState` | string | 아니요 | 직전 서버 응답의 값 |
| `scenarioState` | object | 아니요 | 직전 서버 응답의 값, 최대 64개 필드 |

`turns`와 `history`는 동시에 보낼 수 없다. 신규 클라이언트는 `turns`를 사용한다. 각 턴은 아래 두 필드만 허용한다.

```json
{
  "role": "user",
  "text": "내일 오후에 예약하고 싶습니다."
}
```

- `role`: `user` 또는 `assistant`
- `text`: 1~4,000자의 완료된 발화
- 현재 `userMessage`와 아직 응답이 완성되지 않은 UI placeholder는 `turns`에 넣지 않는다.

초기 요청은 상태를 생략하거나 `scenarioState`를 빈 객체로 보낼 수 있다.

```json
{
  "category": "예약",
  "title": "🏥 병원 예약",
  "description": "병원 진료 예약 전화 상황",
  "userMessage": "내일 오후에 내과 진료 예약 가능할까요?",
  "conversationState": "greeting",
  "scenarioState": {},
  "turns": []
}
```

### 응답

성공 응답은 다음 필드를 항상 반환한다.

| 필드 | 타입 | 의미 |
|---|---|---|
| `response` | string | 상대 역할의 다음 발화 |
| `etiquetteTip` | string/null | 현재 턴에 적용할 통화 팁 |
| `recommendedReplies` | string[] | 사용자 답변 후보, 최대 10개 |
| `conversationState` | string | 갱신된 대화 상태 |
| `shouldEndCall` | boolean | 클라이언트가 종료 절차를 시작해야 하는지 여부 |
| `scenarioState` | object | 다음 요청에 그대로 전달할 버전 지정 상태 |

```json
{
  "response": "내일 오후 내과 진료로 확인했습니다. 원하시는 시간을 말씀해 주세요.",
  "etiquetteTip": null,
  "recommendedReplies": [
    "오후 3시가 가능할까요?",
    "가능한 오후 시간을 알려주세요.",
    "가장 빠른 시간으로 부탁드립니다."
  ],
  "conversationState": "asking_time",
  "shouldEndCall": false,
  "scenarioState": {
    "scenario_key": "예약:병원 예약",
    "state_version": 1,
    "intent": "reservation",
    "department": "내과",
    "date": "내일",
    "time": "오후",
    "conversation_state": "asking_time"
  }
}
```

## 상태 소유권 규칙

1. 서버만 `conversationState`와 `scenarioState`를 생성·변경한다.
2. 모바일은 성공 응답의 두 상태를 함께 저장하고 다음 `/chat` 요청에 그대로 전달한다.
3. `scenario_key`는 상태가 현재 `category/title`에 속하는지 검증한다.
4. `state_version`은 서버가 해석할 수 있는 상태 스키마인지 검증한다.
5. 최상위 `conversationState`와 `scenarioState.conversation_state`가 다르면 요청을 거부한다.
6. `END` 상태에 새 발화를 보내면 `409 CONVERSATION_ALREADY_ENDED`를 반환한다.
7. 실패 응답은 대화 기록이나 상태에 반영하지 않는다.

## 종료 처리

`shouldEndCall`이 `true`이면 모바일은 새 대화 요청을 만들지 않고 STT 중지, 녹음 종료, 음성 분석, 결과 화면 이동 순서로 종료한다.

## 보조 API

- 추천 답변: `POST /chat/suggest`
- 대화 개선: `POST /chat/improve`
- 음성 분석: `POST /voice/analyze`
- 음성 기준선 조회: `GET /voice/baseline`
- 캘리브레이션 확정: `POST /voice/calibrate/finalize`

이전 `/suggest`, `/improve`, `/analyze` 별칭은 제공하지 않는다. 클라이언트와 서버의 경로 불일치를 404로 드러내 배포 계약 오류를 조기에 발견한다.

## 오류 응답

검증 및 서비스 오류는 같은 envelope를 사용한다.

```json
{
  "error": {
    "code": "SCENARIO_STATE_MISMATCH",
    "message": "현재 시나리오와 전달된 상태가 일치하지 않습니다. 통화를 다시 시작해 주세요."
  }
}
```

요청 스키마 오류에는 `error.details`가 추가된다.

| HTTP | code | 의미 |
|---:|---|---|
| 409 | `CONVERSATION_ALREADY_ENDED` | 종료된 통화에 새 발화를 전송함 |
| 422 | `REQUEST_VALIDATION_FAILED` | 타입, 길이, 필드 또는 턴 계약 위반 |
| 422 | `UNSUPPORTED_SCENARIO` | 등록되지 않은 `category/title` 조합 |
| 422 | `SCENARIO_STATE_MISMATCH` | 다른 시나리오의 상태 전달 |
| 422 | `SCENARIO_STATE_VERSION_UNSUPPORTED` | 지원하지 않는 상태 버전 |
| 422 | `SCENARIO_STATE_INVALID` | 허용하지 않은 상태 필드 포함 |
| 422 | `CONVERSATION_STATE_MISMATCH` | 두 상태 표현이 서로 다름 |
| 500 | `PROMPT_CONFIGURATION_ERROR` | 프롬프트 레지스트리 또는 파일 구성 오류 |
| 502 | `AI_PROVIDER_EXECUTION_FAILED` | 모델 호출 실행 실패 |
| 502 | `AI_RESPONSE_VALIDATION_FAILED` | 제한 재요청 후에도 출력 계약 위반 |
| 503 | `AI_PROVIDER_UNAVAILABLE` | 모델 제공자를 사용할 수 없음 |
| 503 | `VOICE_BASELINE_SECURITY_NOT_CONFIGURED` | 음성 기준선 ID 보호 비밀값 미설정 |
| 503 | `VOICE_BASELINE_DATABASE_NOT_CONFIGURED` | PostgreSQL 연결 설정 미완료 |
| 500 | `VOICE_BASELINE_STORE_FAILED` | PostgreSQL 기준선 트랜잭션 또는 조회 실패 |

음성 API도 같은 envelope를 사용하며 `VOICE_MODE_INVALID`, `VOICE_FILE_TOO_LARGE`, `VOICE_CONVERTER_UNAVAILABLE`, `VOICE_CONVERSION_FAILED`, `VOICE_ANALYSIS_FAILED`, `VOICE_BASELINE_NOT_FOUND`, `VOICE_CALIBRATION_EMPTY`처럼 단계별 코드를 반환한다. 재캘리브레이션의 reset은 진행 중 샘플만 제거하며 마지막으로 확정된 기준선은 finalize 성공 전까지 유지한다.

모바일은 408, 429, 5xx만 제한적으로 재요청할 수 있다. 4xx 계약 오류는 같은 payload로 재시도하지 않고 사용자에게 명시적으로 알린다.
