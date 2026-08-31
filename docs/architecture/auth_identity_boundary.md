# 사용자 인증과 데이터 소유권 경계

## 결정

마음콜은 카카오 access token을 사용자 데이터 API마다 반복해서 사용하지 않는다. 모바일은 로그인 직후 토큰을 `POST /auth/kakao/exchange`에 한 번 전달하고, AI 서버가 카카오 공식 API에서 토큰의 유효성과 `app_id`를 확인한다. 검증된 카카오 subject는 별도 비밀값으로 HMAC-SHA256 처리해 내부 UID로 바꾸며, Firebase custom token을 발급한다.

이후 모바일과 서버는 Firebase ID token만 사용한다. Firestore 문서와 음성 기준선의 소유자는 클라이언트가 보낸 `user_id`가 아니라 서버 또는 Firestore Security Rules가 검증한 `request.auth.uid`다.

```mermaid
sequenceDiagram
    participant App as Flutter 앱
    participant API as AI 서버
    participant Kakao as Kakao API
    participant Firebase as Firebase Auth
    participant Store as Firestore·음성 기준선

    App->>API: Kakao access token으로 /auth/kakao/exchange
    API->>Kakao: /v1/user/access_token_info
    Kakao-->>API: id, app_id
    API->>API: HMAC-SHA256(kakao subject)로 내부 UID 생성
    API->>Firebase: custom token 발급
    Firebase-->>App: Firebase ID token 세션
    App->>API: Authorization: Bearer Firebase ID token
    API->>Firebase: 서명·만료·프로젝트 검증
    API->>Store: 검증된 uid 범위에서만 읽기·쓰기
```

## 책임 경계

| 구성 요소 | 책임 | 신뢰하지 않는 값 |
|---|---|---|
| 모바일 | 카카오 로그인 시작, custom token으로 Firebase 로그인, ID token 전달 | 로컬에 저장된 과거 Kakao ID |
| AI 서버 | 카카오 토큰 audience 검증, 내부 UID 생성, Firebase token 검증 | 요청 body·query의 사용자 ID |
| Firebase Auth | custom token을 ID token 세션으로 교환 | 앱이 주장하는 사용자 UID |
| Firestore Rules | `request.auth.uid == userId` 소유권 강제 | 문서 경로만 맞춘 비인증 요청 |
| PostgreSQL 기준선 저장소 | 서버가 전달한 내부 UID를 다시 저장용 HMAC 키로 가명화 | 외부 공급자 식별값 |

## API 계약

- `POST /auth/kakao/exchange`만 Kakao access token을 받는다.
- 음성 기준선 조회·캘리브레이션·삭제·초기화는 Firebase ID token이 필수다.
- 일반 음성 분석은 익명으로 가능하지만, 기준선을 적용하려면 유효한 Firebase 세션이 필요하다.
- 클라이언트가 `user_id`를 보내 소유자를 선택하는 계약은 제공하지 않는다.
- 인증 설정이 빠진 서버는 readiness의 `authentication` 구성 요소와 503 오류로 배포 문제를 드러낸다.

## 레거시 Firestore 문서 이관

기존 버전은 `users/{Kakao ID}`에 데이터를 저장했다. 새 규칙을 먼저 배포하면 기존 문서에 접근할 수 없으므로 다음 순서를 지킨다.

1. 운영 자격 증명과 운영용 인증 HMAC 비밀값을 안전한 비밀 저장소에서 주입한다. 로컬·파일 마운트 환경은 `AUTH_SUBJECT_HMAC_SECRET_FILE`에 저장소 밖 절대 경로를 지정할 수 있다.
2. 실제 이관 대상만 적은 저장소 밖 manifest로 dry-run을 실행한다.
3. 모든 대상이 `READY` 또는 `ALREADY_COPIED`인지 검토한다.
4. 같은 manifest에 `--apply`를 사용해 문서별 트랜잭션을 실행한다.
5. 모바일 새 버전과 Firestore Security Rules를 배포한다.
6. Firebase Console에서 레거시 문서가 남지 않았는지 별도로 확인한다.

`DESTINATION_CONFLICT`는 자동 병합하지 않는다. 새 UID 문서에 다른 내용이 있다는 뜻이므로 어떤 데이터가 최신인지 업무 판단 후 별도 처리해야 한다. `SOURCE_NOT_FOUND`도 대상을 추측하지 않고 manifest 또는 운영 데이터를 확인한다.

### 2026-08-18 운영 이관 검증

- 대상 프로젝트: `call-phobia-app`
- 대상 컬렉션: `users`
- 이관 전: 숫자형 Kakao subject 문서 5개, 내부 UID 문서 0개
- dry-run: `READY` 5개, 누락·충돌 0개
- 트랜잭션 적용: `MIGRATED` 5개
- 이관 후: 내부 UID 문서 5개, 숫자형 레거시 문서 0개
- 데이터 보존: 이관 전후 문서 수와 필드 구조 분포 동일
- 민감정보 정리: 실제 subject를 담았던 저장소 밖 manifest는 검증 직후 삭제

이 결과는 특정 사용자 ID를 문서나 로그에 복사하지 않고 건수·상태·필드 구조만으로 검증했다. Firestore Security Rules는 새 모바일 인증 버전 배포와 함께 활성화해 구버전 클라이언트 차단 시점을 통제한다.

### 2026-08-31 이관 사후 검증과 Rules 배포 게이트

이관을 다시 실행하지 않고 Admin SDK의 읽기 전용 조회로 운영 데이터를 사후 검증했다. `users` 컬렉션에는 내부 UID 문서 5개만 남아 있었고, 숫자형 레거시 ID·그 밖의 ID 형식·빈 문서는 모두 0개였다. 문서의 실제 필드값이나 사용자 식별값은 출력하지 않았으며, 필드 이름을 정렬해 만든 구조 서명과 건수만 비교했다. 필드 구조는 2종류였고, 4개 문서는 필드 4개, 1개 문서는 필드 5개였다. 이는 데이터의 값이 틀렸다는 뜻이 아니라 사용자 문서가 현재 두 가지 구조로 존재한다는 뜻이므로, 후속 스키마 통합 시 명시적으로 다룬다.

Firebase Rules API로 운영 배포본과 모바일 저장소의 `firestore.rules`도 읽기 전용으로 비교했다. 운영에는 2025-09-12에 생성된 개발용 공개 규칙이 남아 있어 `users` 읽기·쓰기를 인증 없이 허용하고 있었고, 저장소에는 다음 조건을 모두 요구하는 강화 규칙이 준비되어 있었다.

- Firebase 인증이 완료되어 `request.auth`가 존재한다.
- Firebase 세션의 `identity_provider`가 `kakao`다.
- 세션의 UID와 접근하려는 `users/{userId}` 경로의 UID가 같다.
- `users` 외의 경로는 명시적으로 거부한다.

강화 규칙은 Firestore Emulator에서 다음 계약을 자동 검증한다. 비로그인 요청, 카카오 claim이 없는 요청, 다른 UID 접근은 실패해야 하고, 같은 UID의 카카오 세션만 조회·생성·수정·삭제할 수 있어야 한다. 이 검증은 모바일 CI의 독립 job으로 실행되어 앱 테스트와 별개로 권한 경계의 회귀를 막는다.

운영 규칙은 이번 검증에서 배포하지 않았다. 저장소의 규칙 자체가 안전하더라도, 아직 배포 가능한 모바일 Release가 없는 상태에서 먼저 적용하면 구버전 앱이 Firestore에 접근하지 못할 수 있기 때문이다. 다음 조건을 하나의 배포 단위로 충족한 뒤 적용한다.

1. 카카오 토큰을 Firebase custom token으로 교환하는 AI 서버가 운영 인증값으로 준비된다.
2. Firebase ID token으로 로그인하는 모바일 빌드를 실제 기기에서 검증한다.
3. 모바일 Release와 롤백 가능한 배포 버전을 준비한다.
4. Emulator 권한 테스트와 모바일 전체 CI가 성공한 커밋을 기준으로 Rules를 배포한다.
5. 배포 직후 본인 문서 접근 성공과 타인·비인증 접근 실패를 운영에서 다시 확인한다.

운영 배포본과 저장소 파일이 서로 다른 상태를 **Rules drift**라고 한다. 이 상태를 오래 방치하면 코드 리뷰에서는 안전해 보이지만 실제 서비스는 열려 있는 문제가 생긴다. 따라서 Rules 배포 여부와 배포본 비교를 릴리스 점검 항목으로 관리한다.

## 오류 경계

| HTTP | 오류 코드 | 의미 |
|---:|---|---|
| 401 | `AUTHORIZATION_REQUIRED` | Bearer token이 필요한 요청 |
| 401 | `AUTHORIZATION_INVALID` | Authorization 헤더 형식 오류 |
| 401 | `KAKAO_TOKEN_INVALID` | 만료되었거나 유효하지 않은 카카오 토큰 |
| 401 | `KAKAO_TOKEN_AUDIENCE_MISMATCH` | 다른 카카오 앱에서 발급된 토큰 |
| 401 | `FIREBASE_TOKEN_INVALID` | 서명·만료·프로젝트 검증에 실패한 Firebase 세션 |
| 403 | `FIREBASE_IDENTITY_PROVIDER_FORBIDDEN` | Firebase 세션은 유효하지만 카카오 identity claim이 없음 |
| 502 | `AUTH_PROVIDER_RESPONSE_INVALID` | 카카오 응답을 계약대로 해석할 수 없음 |
| 503 | `AUTH_PROVIDER_UNAVAILABLE` | 카카오 API 연결 또는 처리 실패 |
| 503 | `AUTH_CONFIGURATION_INVALID` | 서버 인증 환경변수나 Firebase Admin 초기화 오류 |
| 503 | `AUTH_TOKEN_ISSUE_FAILED` | Firebase custom token 발급 실패 |

## 기술 선택 Q&A

### Q. HMAC이 무엇인가?

HMAC은 비밀키와 원문을 함께 넣어 고정 길이 값을 만드는 방식이다. 같은 비밀키와 같은 카카오 subject는 항상 같은 내부 UID가 되지만, 비밀키가 없으면 원래 값을 알아내기 어렵다. 단순 SHA-256은 카카오 ID 후보를 반복 대입할 수 있으므로 여기서는 충분하지 않다.

### Q. HMAC을 사용하면 로그인 검증도 끝나는가?

아니다. HMAC은 식별값을 가명화할 뿐이다. 사용자가 실제로 누구인지 확인하는 인증은 카카오 token 검증과 Firebase ID token 검증이 담당한다. 가명화와 인증은 목적이 다르다.

### Q. 왜 클라이언트의 `user_id`를 받지 않는가?

클라이언트 입력은 수정할 수 있다. 공격자가 다른 사용자의 ID를 body나 query에 넣으면 서버가 그 값을 신뢰하는 순간 타인의 기준선을 조회하거나 삭제할 수 있다. 서버가 검증한 token의 UID만 사용하면 소유자를 클라이언트가 선택할 수 없다.

### Q. 왜 카카오 ID를 Firebase UID로 그대로 쓰지 않는가?

외부 공급자의 실제 식별값이 Firestore 경로, 로그, 백업, 운영 화면에 반복 노출될 수 있기 때문이다. 내부 UID는 서비스 내부 식별과 외부 공급자 식별을 분리해 유출 범위를 줄인다.

### Q. 왜 카카오 토큰을 모든 API에서 계속 검증하지 않는가?

모든 요청이 카카오 API 가용성과 지연 시간에 종속되기 때문이다. 로그인 경계에서 카카오 신원을 확인한 뒤 Firebase 세션으로 교환하면 Firestore와 AI 서버가 같은 UID·만료·서명 체계를 사용하고, 일반 API 호출은 외부 네트워크 없이 검증할 수 있다.

### Q. dry-run은 왜 필요한가?

운영 데이터 이관은 코드가 맞아도 대상 목록이나 환경이 틀릴 수 있다. dry-run은 쓰기 없이 원본 존재 여부와 목적지 충돌을 확인한다. `--apply`를 명시적으로 분리하면 검토와 실제 변경 사이에 승인 지점을 만들 수 있다.

### Q. whitespace는 무엇이며 왜 `strip()`을 사용하는가?

whitespace는 공백, 탭, 줄바꿈처럼 화면에 잘 보이지 않는 문자다. 환경변수나 식별값 앞뒤에 이런 문자가 섞이면 같은 값이 서로 다른 사용자처럼 처리될 수 있다. `strip()`은 값 양끝의 whitespace를 제거한다. 다만 중간 문자는 의미가 달라질 수 있어 임의로 삭제하지 않는다.
