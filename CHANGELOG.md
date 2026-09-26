# Changelog

이 프로젝트의 주요 변경 사항을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/ko/1.1.0/)를 따르고 버전은 Semantic Versioning을 사용합니다.

## [Unreleased]

### Added

- 16개 상세 그래프용 구조화 NLU 골든 데이터 계약과 계약 성공률·행동 분류·필드 F1·사실 생성률 평가기
- Coverage V2 도입 단계의 의미 원본 그룹용 JSON Schema, 결정론적 V2 corpus compiler, 라이브 계약 기반 865개 작성 의무 목록과 source-compiled 일치 검증
- 그룹 파일과 분리된 split 배정 원장, 작성 그룹 일대일 대조, 공식 채점 직전 split 원장 지문 재검증
- 버전 지정 구조화 NLU 정답 작성 지침과 validation·test case·지침 지문을 공식 준비·채점 직전에 대조하는 검수 원장 계약
- validation·test별 시나리오 태그, 이전 필드 문맥, 예약 대안시간 관계와 검수 지문이 연결된 명시적 대조 역할을 고정한 Coverage V3 프로필·1,562개 의무 목록
- 구조화 NLU source·split·검수·contrast·Coverage V3 조합과 입력 Git blob snapshot을 고정하는 versioned freeze record V1 기반 및 AI-origin policy까지 포함한 V2 생성·검증 경계
- AI 제안을 사람 작성 골든 source와 분리하고 16개 구조화 NLU 시나리오의 미검수 hard-negative 시작 제안을 제공하는 draft sidecar 계약
- 16개 AI 제안을 사람이 새 발화·정답·판단 근거로 다시 작성하기 위한 결정론적 검수 작업지와 계약 일치 검사
- 16개 시나리오별 서브 에이전트 대안·판단 근거 sidecar와 불변 AI-origin V1 지문 원장 기반 NFC 전역 원문 승격 차단
- 예약 4개·교수님 3개·배달 3개 시나리오의 사람이 작성한 `greeting → unknown` hard-negative development 초안과 결정론적 compiled corpus
- digest로 고정한 Python 3.11 다단계 이미지와 비루트·읽기 전용 핵심 컨테이너 실행 경계
- PostgreSQL 준비 후 Alembic 일회성 적용과 API 시작을 보장하는 Compose 서비스 의존성
- 이미지 빌드·마이그레이션·권한·HTTP 상태 계약을 실제 컨테이너에서 검증하는 `test-container` CI
- 32개 시나리오와 가족 엄마·아빠 역할을 덮는 서버 소유 `castVersion: 2` 배역 계약
- 인증된 `/tts/scenario/synthesize` API와 Qwen3-TTS·Bark Small·Qwen Voice Clone 공급자
- 승인된 엄마 Voice Clone manifest·safetensors 해시 검증과 공급자 전환 시 모델 메모리 해제
- TTS 최초 적재·동일 모델 재사용·공급자 전환을 구분하는 Prometheus 지표와 `Server-Timing` 응답 계약
- Apache-2.0 Qwen3-TTS 0.6B CustomVoice의 SHA 고정 로컬 공급자, 9개 음색 목록, 인증된 WAV 합성 API
- 동일 한국어 문장으로 9개 음색을 생성하고 파일 해시를 기록하는 청취 비교 명령
- 모든 대화의 외부 반영 없음 메타데이터와 9개 업무 상세 그래프의 사용자 확인 후 모의 처리 완료 상태
- Ruff 0.16.0 기반 저장소 전체 정적 품질·포맷 검사와 로컬 `make lint`·`make format` 명령
- 버전·등록 시나리오·정규화된 시나리오 키를 검증하는 `/call/setup` 계약
- Kiwi 0.23.2 형태소 원형·품사 기반 한국어 단어 빈도 분석과 readiness 구성 요소
- 기존 예약·교수님 7개 상세 그래프의 필드 타입·action·필수 정보·상태 조합 검증 계약
- 32개 시나리오를 상세 16개·등록형 16개 중 하나의 실행 계약에만 연결하는 중앙 LangGraph 레지스트리
- 중복 시나리오 키를 애플리케이션 초기화 단계에서 차단하는 계약 테스트
- `.python-version` 기준을 검사하는 Python 3.11 사전 검증과 개발 환경 구성 스크립트
- 배달·시청·고객센터 9개 시나리오의 필드 수집·수정·취소·확인·업무 분기 상세 그래프
- A/S 안전 이상 시 일반 접수를 중단하는 `safety_action_required` 보호 상태

### Changed

- 구조화 NLU의 수정·확인·취소·종료 태그와 Coverage V3 적용 범위를 행동명 접두사 대신 35개 라이브 행동의 명시적 의미 계약에서 파생
- 업무 workflow가 현재까지 비어 있는 필드만 새 정보로 받고, 이미 수집한 값만 실제 변경값으로 교체하도록 런타임·평가 계약 통일
- 구조화 NLU 평가 케이스가 서버가 제시한 예약 대체 시간을 명시하고 런타임과 같은 action-field·정확 후보 계약을 사용하도록 강화
- Coverage V2 도입 단계에서 구조화 NLU 데이터셋과 공식 프로필을 V2로 올리고 action-field·업무 변경·예약 대안 상태를 재현성 지문에 포함
- 예약·교수님 상세 그래프가 같은 발화에서 변경값을 받은 경우 재수집하지 않고 변경된 전체 정보를 다시 확인하도록 상태 전이 통일
- 모바일 운영 TTS 요청이 원시 음색 대신 시나리오 키·배역 버전·선택적 가족 역할을 사용하도록 경계 분리
- 한 프로세스의 TTS 합성을 공급자 전체에서 직렬화하고 활성 모델을 하나만 유지하도록 실행 구조 강화
- 로컬 NLU와 TTS가 함께 설치될 수 있도록 Transformers·Accelerate 버전을 Qwen3-TTS 공식 패키지 계약과 통일
- 배달·시청·고객센터 흐름을 처리 준비에서 종료하지 않고 명시적 진행 의사 뒤 모의 승인·안내·접수 완료까지 확장
- Python 코드를 3.11 타입 표기와 단일 Ruff 포맷 기준으로 정리
- AI 서버 GitHub Actions의 외부 액션을 검증한 릴리스 커밋 SHA로 고정
- 통화 방향·오프닝 정책을 중앙 LangGraph 레지스트리의 모든 시나리오와 일대일로 연결
- 고정 군더더기·불용어 목록과 공백 토큰화를 내용어·감탄사 품사 계약으로 교체
- `/chat` 라우팅을 카테고리별 순차 분기에서 중앙 실행 레지스트리 단일 디스패치로 변경
- 로컬 서버·Makefile 명령이 프로젝트의 Python 3.11 가상환경만 사용하도록 실행 경계 강화
- GitHub Actions를 Node.js 24 기반 공식 액션으로 갱신하고 `.python-version`을 CI 런타임 기준으로 연결
- 병원 예약의 예약자 이름과 교수님 과제·결석의 수업명을 필수 식별 필드로 강화

### Fixed

- 선택형 정답 여러 개로 coverage를 부풀리거나 동일한 모델 입력을 corpus에 중복하는 골든 데이터 우회 경로
- 16개 구조화 NLU에서 확인·완료·취소 행동과 새 필드값이 함께 들어와 재확인 없이 상태를 변경하던 교차 계약 누락
- 식당·미용실·스터디룸 대체 시간 선택이 서버 제시 후보를 검증하지 않거나 노드에서 행동을 임의 보정하던 경로
- 상세 그래프의 변경 발화에 새 값이 포함돼도 노드가 해당 값을 버리고 필드를 비우던 상태 병합 경로
- 무성·비정상 음성 측정값과 기준선 누락값을 0으로 대체하지 않고 타입이 있는 오류 또는 생략 가능한 통계로 처리
- Praat·ffmpeg 블로킹 작업을 요청 이벤트 루프 밖의 작업 스레드에서 실행

### Removed

- 한국어 단어 분석의 글자 수 필터와 분석기 장애를 숨길 수 있는 문자열 분리 경로
- 중앙 레지스트리 전환 후 운영 경로에서 사용되지 않는 예약·교수님 카테고리 라우터

## [2.2.0] - 2026-08-18

### Added

- 예약 4종이 공유하는 버전 지정 가용성 일정표와 공급자 인터페이스
- 일정표 누락·스키마 오류를 구분하는 `AVAILABILITY_PROVIDER_CONFIGURATION_ERROR`
- 일정표 로드 가능 여부를 확인하는 `/health/ready` 구성 요소
- 카카오 access token을 검증하고 Firebase custom token으로 교환하는 `POST /auth/kakao/exchange`
- Firebase ID token에서 사용자 소유권을 확정하는 음성 기준선 인증 경계
- 명시적 대상 목록, dry-run, 트랜잭션, 충돌 중단을 지원하는 Firestore 사용자 문서 이관 명령

### Changed

- 예약 가능 여부를 클라이언트 상태가 아니라 서버 소유 일정표에서만 조회
- 목록에 없는 요청 시간을 예약 가능으로 추측하지 않고 대안 슬롯과 함께 예약 불가로 처리
- 클라이언트 상태 허용 목록 변경에 맞춰 `scenarioState.state_version`을 2로 상향
- 음성 기준선 API가 클라이언트 `user_id` 대신 검증된 Firebase UID만 사용하도록 변경

### Removed

- 예약·교수님 상태 봉투에서 사용하지 않는 `simulation_result` 필드
- 예약 시간이 고정 충돌 목록에 없으면 성공으로 처리하던 기본 분기
- 음성 기준선 요청의 `user_id` 폼·쿼리 필드

### Security

- 카카오 사용자 식별값을 별도 인증 비밀값으로 HMAC-SHA256 처리해 Firebase UID로 가명화
- 다른 카카오 앱의 access token과 유효하지 않은 Firebase 세션을 명시적으로 거부
- 운영 이관 로그에는 원래 카카오 식별값 대신 비가역 audit fingerprint만 기록
- HMAC 비밀값을 환경변수 원문 대신 저장소 밖 절대 경로 파일로 주입할 수 있도록 구성 경계 강화

## [2.1.0] - 2026-08-17

### Added

- `scenario_key`, `state_version`, 필드 allowlist 기반의 클라이언트 상태 계약
- 요청별 `X-Request-ID`와 모델·음성 보안·ffmpeg를 확인하는 `/health/ready`
- 상태 변조, 종료 후 요청, 단어 빈도 입력, 정확한 수신 통화 정책 회귀 테스트
- PostgreSQL 18 개발 구성, SQLAlchemy 비동기 저장소, Alembic 초기 스키마와 JSON 이관 명령
- Prometheus 형식의 LangGraph 노드 지연·시도·재시도·계약 실패 지표와 `/metrics`

### Changed

- LangGraph를 1.2.11로 올리고 Python 3.11+ 실행 기준을 명확화
- 7개 상세 그래프의 API 응답 조립을 공통 상태 계약으로 통합
- `/chat`, `/chat/suggest`, `/chat/improve`, 음성 API의 입력 타입과 오류 envelope 강화
- Flutter가 완료된 이전 턴과 서버 상태를 보존하고 서버 종료 신호를 실행하도록 연동
- 재캘리브레이션 시작 시 확정된 음성 기준선은 유지하고 진행 중 샘플만 초기화
- 확정 기준선 JSON과 프로세스 메모리 샘플을 사용자별 행 잠금 기반 PostgreSQL 트랜잭션으로 전환
- 모든 상세·등록형 LangGraph 노드를 공통 계측 경계로 연결하고 구조화 출력 재시도를 작업별로 분리

### Removed

- 경로 불일치를 숨기던 `/suggest`, `/improve`, `/analyze` 호환 별칭
- 서버 장애를 정상 대화처럼 표시하던 모바일 고정 응답
- 역할과 시나리오 제목을 추정하는 문자열 휴리스틱
- 런타임 `baseline_db.json` 파일 저장과 프로세스 전용 캘리브레이션 캐시

### Security

- 실제 사용자 ID 대신 운영 비밀값 기반 HMAC-SHA256 식별자로 음성 기준선 저장
- 기준선 식별자 비밀값이 없으면 저장 기능을 명시적으로 중단하도록 변경
- 음성 변환 내부 오류를 노출하지 않고 타입이 있는 공개 오류로 통일

## [2.0.0] - 2026-08-17

### Added

- 모바일에 등록된 25개 시나리오를 위한 구조화 턴 생성 LangGraph와 시나리오 레지스트리
- 구조화 출력 계약 검증, 제한 재시도, 타입이 있는 AI 서비스 오류 응답
- 모바일 이모지 제목을 안전하게 처리하는 공통 라우팅 정규화
- 로컬 모델 선택 설치 파일, 환경변수 예시, 오프라인/실모델 테스트 분리
- 전체 시나리오·프롬프트·음성 업로드 안전성 회귀 테스트

### Changed

- 프로젝트 표시 이름을 `MaeumCall AI Server`로 통일
- Python 기준 런타임을 3.11로 상향하고 의존성 버전을 고정
- JSON/INI 프롬프트 로더를 통합하고 전체 모바일 시나리오 매핑을 정리
- 예약·교수님 상세 그래프를 `LLM 구조화 분석 → 상태 전이 → 도메인 응답 정책`으로 통일
- 하드코딩된 실행 스크립트를 저장소 상대 경로 기반으로 변경
- 음성 기준선 저장을 프로세스 내 원자 갱신 방식으로 보강

### Fixed

- 모바일의 이모지 포함 예약 제목이 상세 LangGraph로 라우팅되지 않던 문제
- 회사 추천 답변 프롬프트가 일반 규칙으로 덮어써지던 조건문 문제
- 초기 예약 시간이 대안 선택 시간으로 남아 잘못된 상태 전이를 만들 수 있던 문제
- 기본 `pytest` 실행이 import 경로와 실모델 네트워크 요청에 의존하던 문제

### Security

- 업로드 원본 파일명 사용 제거, UUID 기반 작업 경로·업로드 크기 제한·ffmpeg timeout 추가
- 저장소에 포함된 런타임 음성 기준선 데이터 제거 및 Git 추적 제외
- CORS wildcard 사용 시 credential 허용을 자동으로 비활성화
