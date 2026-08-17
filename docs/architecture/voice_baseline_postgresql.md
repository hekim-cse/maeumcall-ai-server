# 음성 기준선 PostgreSQL 저장 설계

## 문제

기존 구현은 확정된 기준선을 `data/baseline_db.json`에 저장하고, 확정 전 캘리브레이션 샘플은 Python 프로세스 메모리에 보관했다.

- 프로세스가 재시작되면 확정 전 샘플이 사라진다.
- 여러 서버 프로세스는 서로 다른 메모리를 사용한다.
- 파일 잠금은 현재 프로세스 내부에서만 동작해 여러 프로세스의 덮어쓰기를 막지 못한다.
- 샘플 확정 도중 장애가 나면 기준선 저장과 샘플 삭제가 하나의 작업으로 보장되지 않는다.

## 선택한 구조

PostgreSQL 18과 SQLAlchemy 2 비동기 세션, asyncpg 드라이버, Alembic 스키마 이력을 사용한다.

```mermaid
erDiagram
    VOICE_SUBJECTS ||--o| VOICE_BASELINES : owns
    VOICE_SUBJECTS ||--o{ VOICE_CALIBRATION_SAMPLES : collects

    VOICE_SUBJECTS {
        varchar user_key PK
        timestamptz created_at
    }
    VOICE_BASELINES {
        varchar user_key PK_FK
        int sample_count
        float pitch_hz
        float jitter_local
        float shimmer_local
        timestamptz updated_at
    }
    VOICE_CALIBRATION_SAMPLES {
        bigint id PK
        varchar user_key FK
        float pitch_hz
        float jitter_local
        float shimmer_local
        timestamptz created_at
    }
```

실제 계정 ID는 저장하지 않는다. 기존과 동일하게 HMAC-SHA256으로 가명화한 `user_key`만 세 테이블의 연결 키로 사용한다.

## 트랜잭션 경계

사용자별 쓰기 작업은 먼저 `voice_subjects` 행을 `SELECT ... FOR UPDATE`로 잠근다. 같은 사용자의 샘플 추가, 확정, 초기화, Welford 갱신은 순서대로 처리되며 다른 사용자의 작업은 독립적으로 진행된다.

캘리브레이션 확정은 한 트랜잭션에서 다음 순서로 실행한다.

1. 사용자 행 잠금
2. 확정 전 샘플 개수·평균·표준편차 계산
3. 확정 기준선 삽입 또는 갱신
4. 확정 전 샘플 삭제
5. 커밋

3번이나 4번에서 실패하면 전체 작업이 롤백되므로 “기준선은 바뀌었는데 샘플은 남는 상태”가 발생하지 않는다.

## 측정 실패와 파생 통계 계약

업로드 파일과 ffmpeg 변환 파일은 요청별 임시 경로에만 만들고 응답 성공 여부와 관계없이 삭제한다. Praat 분석과 ffmpeg 실행은 FastAPI 이벤트 루프를 막지 않도록 작업 스레드에서 실행한다.

목소리가 없거나 pitch·jitter·shimmer를 유한한 값으로 측정할 수 없으면 0으로 대체하지 않는다. `VOICE_NO_VOICED_AUDIO` 또는 `VOICE_MEASUREMENT_UNAVAILABLE` 오류를 반환해 사용자가 다시 녹음하도록 한다. 기준선 필드가 누락된 경우에도 기본값을 채우지 않고 기준선 계약 오류로 처리한다.

표준편차가 0이면 z-score가 정의되지 않고, 기준값이 0이면 백분율 변화가 정의되지 않는다. 이 경우 API는 각각 `z` 또는 `deltaPct` 필드를 생략한다. 0을 “변화 없음”으로 표시하지 않는다.

## 실행

`.env`에 `POSTGRES_PASSWORD`, `DATABASE_URL`, `BASELINE_ID_HMAC_SECRET`을 실제 운영 환경 값으로 설정한다. 값은 Git에 커밋하지 않는다.

```bash
docker compose up -d postgres
alembic upgrade head
python -m uvicorn main:app --host 0.0.0.0 --port 8001
```

## 기존 JSON 이관

먼저 마이그레이션을 적용한 뒤 이관 명령을 실행한다.

```bash
python -m scripts.migrate_baseline_json /secure/path/baseline_db.json
```

이 명령은 HMAC 가명 키와 필수 음성 값이 모두 유효한 항목만 받아들인다. 같은 키를 다시 실행하면 해당 기준선을 갱신하므로 이관 명령 자체는 재실행할 수 있다. 원본 JSON은 자동 삭제하지 않는다. 백업과 결과 검증 후 운영자가 보존 정책에 따라 처리한다.

## 질문과 답

### Q. 트랜잭션이 무엇인가?

여러 데이터 변경을 하나의 작업으로 묶는 데이터베이스 기능이다. 전부 성공하면 커밋하고, 하나라도 실패하면 전부 되돌린다.

### Q. 행 잠금은 무엇인가?

특정 사용자의 한 행을 수정하는 동안 같은 행을 바꾸려는 다른 요청을 기다리게 하는 장치다. 파일 전체를 잠그지 않으므로 다른 사용자의 요청은 동시에 처리할 수 있다.

### Q. ORM은 무엇인가?

데이터베이스 테이블과 Python 클래스를 연결하는 방식이다. 이 프로젝트에서는 SQLAlchemy가 연결 풀, 매개변수 바인딩, 트랜잭션 경계를 관리하고 Alembic이 테이블 변경 이력을 관리한다.

### Q. 연결 풀이 무엇인가?

요청마다 데이터베이스 연결을 새로 만드는 대신 일정 수의 연결을 재사용하는 구조다. 연결 비용을 줄이되 무제한 연결로 PostgreSQL을 압박하지 않도록 기본 크기와 초과 허용 수를 환경값으로 제한한다.

### Q. Alembic이 왜 필요한가?

코드만 바꿔서는 이미 운영 중인 데이터베이스 테이블이 자동으로 안전하게 바뀌지 않는다. Alembic revision은 어떤 테이블과 제약조건을 어떤 순서로 만들었는지 Git에 남기는 스키마 이력이다.

### Q. 왜 SQLite를 사용하지 않았나?

이 서버는 다중 프로세스와 향후 여러 인스턴스 운영을 목표로 한다. PostgreSQL은 행 잠금, 동시 트랜잭션, 연결 풀, 운영 백업 도구가 이 구조에 더 적합하다. 운영 경로에는 SQLite 대체 동작을 두지 않는다.

### Q. 테스트의 메모리 저장소는 운영 대체 기능인가?

아니다. 테스트 더블은 API 계약과 계산을 빠르게 검증하기 위한 테스트 코드에만 존재한다. 애플리케이션이 실제 요청을 처리할 때는 PostgreSQL 설정이 없으면 503 오류를 반환하고 readiness도 준비되지 않은 상태를 보고한다.

### Q. 왜 측정 실패를 0으로 저장하지 않는가?

0은 오류 표시가 아니라 실제 숫자다. 측정 실패를 0 Hz 또는 0%로 저장하면 평균과 변화율이 정상 데이터처럼 계산되어 사용자 피드백을 왜곡한다. 따라서 원시 측정 실패는 타입이 있는 오류로, 계산할 수 없는 파생 통계는 선택 필드 생략으로 표현한다.

## 검증 기준

- Python 3.11 전체 오프라인 테스트 통과
- Alembic PostgreSQL DDL 오프라인 생성 성공
- Docker Compose 구성 검사 성공
- PostgreSQL 18.6 컨테이너에서 `alembic upgrade head` 적용 성공
- 실제 테이블에서 샘플 추가·확정·조회·초기화·연쇄 삭제 통합 검증 성공
- 같은 사용자에 대한 동시 쓰기 12건의 사용자 행 잠금 직렬화 검증 성공

## 공식 참고 자료

- [SQLAlchemy 2 비동기 I/O](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Alembic 비동기 엔진 구성](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic)
- [PostgreSQL 지원 버전 정책](https://www.postgresql.org/support/versioning/)
