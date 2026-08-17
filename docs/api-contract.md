# API Contract

이 문서는 Flutter 앱과 MaeumCall AI Server 2.2 사이의 통화 상태 계약을 정의한다. 필드가 추가되거나 잘못된 타입이 전달되면 서버는 이를 무시하지 않고 `422 REQUEST_VALIDATION_FAILED`로 거부한다.

## POST `/call/setup`

모바일은 대화를 시작하기 전에 등록된 시나리오와 통화 방향을 확인한다. 요청에는 `contract_version: 1`, `category`, `title`만 보낸다. 서버는 중앙 LangGraph 레지스트리에서 조합을 한 번 조회하고 다음 값을 반환한다.

- `contract_version`: 모바일이 해석할 수 있는 통화 준비 스키마 버전
- `scenario_key`: 서버가 정규화하고 확정한 시나리오 식별 키
- `direction`: `incoming` 또는 `outgoing`
- `who_starts`: 첫 발화 주체
- `delay_ms`: 연결 연출 시간
- `opening`: 첫 에이전트 발화

미등록 시나리오는 `UNSUPPORTED_SCENARIO`, 지원하지 않는 버전은 `CALL_SETUP_VERSION_UNSUPPORTED`로 거부한다. 모바일은 누락 필드에 빈 문자열이나 0을 넣지 않고 응답 전체를 계약 오류로 처리한다.

## POST `/auth/kakao/exchange`

로그인 직후 카카오 access token을 Firebase 사용자 세션으로 교환한다. 요청 body에는 사용자 ID나 토큰을 넣지 않고 `Authorization: Bearer {Kakao access token}` 헤더만 사용한다. 서버는 카카오 공식 token info API가 반환한 `app_id`와 식별값을 검증한 뒤 가명 내부 UID의 Firebase custom token을 반환한다.

```json
{
  "firebaseCustomToken": "Firebase custom token"
}
```

모바일은 이 토큰을 `signInWithCustomToken`에 전달한다. 이후 사용자 소유 데이터 API에는 Firebase ID token을 Bearer token으로 사용하며 Kakao access token을 재사용하지 않는다.

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
| `simulation` | object | `mode: simulation`, `externalEffect: false` 고정 메타데이터 |

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
    "state_version": 2,
    "intent": "reservation",
    "department": "내과",
    "date": "내일",
    "time": "오후",
    "conversation_state": "asking_time"
  },
  "simulation": {
    "mode": "simulation",
    "externalEffect": false
  }
}
```

`simulation.externalEffect`는 항상 `false`다. 예약 확정, 환불 승인, A/S 접수 완료 같은 문장은 전화 연습 그래프 안의 모의 결과이며 실제 기관·업체 시스템에 영향을 주지 않는다. 배달·시청·고객센터 상세 그래프는 `정보 확인 → 처리 준비 → 모의 처리 완료` 순서를 지키며, 사용자가 처리 진행을 명시한 경우에만 완료 상태로 전이한다.

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
- 음성 기준선 삭제: `POST /voice/baseline/delete`
- 캘리브레이션 진행 데이터 초기화: `POST /voice/calibrate/reset`
- 운영 지표: `GET /metrics` (Prometheus text format, OpenAPI 문서에서는 숨김)

`GET /voice/baseline`, 캘리브레이션 분석·확정·초기화, 기준선 삭제는 Firebase ID token이 필수다. `POST /voice/analyze`의 일반 분석은 익명 호출도 허용하지만 기준선은 적용하지 않는다. 음성 API는 body, form, query의 `user_id`를 소유권 근거로 받지 않는다.

`/metrics`는 LangGraph 노드의 시도·재시도·실행 시간, 구조화 출력 재생성, 계약 실패를 집계한다. 사용자 ID, HMAC 키, 요청 ID, 발화 내용은 지표 라벨로 노출하지 않는다.

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
| 401 | `AUTHORIZATION_REQUIRED` | 인증이 필요한 요청에 Bearer token이 없음 |
| 401 | `AUTHORIZATION_INVALID` | Authorization 헤더가 Bearer 형식이 아님 |
| 401 | `KAKAO_TOKEN_INVALID` | 카카오 access token이 만료되었거나 유효하지 않음 |
| 401 | `KAKAO_TOKEN_AUDIENCE_MISMATCH` | 다른 카카오 앱의 토큰이 전달됨 |
| 401 | `FIREBASE_TOKEN_INVALID` | Firebase ID token 검증 실패 |
| 403 | `FIREBASE_IDENTITY_PROVIDER_FORBIDDEN` | 유효한 Firebase 세션이지만 카카오 인증 계정이 아님 |
| 502 | `AUTH_PROVIDER_RESPONSE_INVALID` | 카카오 token info 응답 계약 위반 |
| 503 | `AUTH_PROVIDER_UNAVAILABLE` | 카카오 인증 API를 사용할 수 없음 |
| 503 | `AUTH_CONFIGURATION_INVALID` | 인증 환경변수 또는 Firebase Admin 설정 미완료 |
| 503 | `AUTH_TOKEN_ISSUE_FAILED` | Firebase custom token 발급 실패 |
| 500 | `AVAILABILITY_PROVIDER_CONFIGURATION_ERROR` | 예약 훈련 일정표 누락 또는 스키마 오류 |
| 503 | `VOICE_BASELINE_SECURITY_NOT_CONFIGURED` | 음성 기준선 ID 보호 비밀값 미설정 |
| 503 | `VOICE_BASELINE_DATABASE_NOT_CONFIGURED` | PostgreSQL 연결 설정 미완료 |
| 500 | `VOICE_BASELINE_STORE_FAILED` | PostgreSQL 기준선 트랜잭션 또는 조회 실패 |

음성 API도 같은 envelope를 사용하며 `VOICE_MODE_INVALID`, `VOICE_FILE_TOO_LARGE`, `VOICE_CONVERTER_UNAVAILABLE`, `VOICE_CONVERSION_FAILED`, `VOICE_ANALYSIS_FAILED`, `VOICE_BASELINE_NOT_FOUND`, `VOICE_CALIBRATION_EMPTY`처럼 단계별 코드를 반환한다. 재캘리브레이션의 reset은 진행 중 샘플만 제거하며 마지막으로 확정된 기준선은 finalize 성공 전까지 유지한다.

모바일은 408, 429, 5xx만 제한적으로 재요청할 수 있다. 4xx 계약 오류는 같은 payload로 재시도하지 않고 사용자에게 명시적으로 알린다.
