# AI 서버 컨테이너 실행 경계

## 구성 결과

AI 서버의 핵심 실행 환경을 Python 3.11 기반 Docker 이미지로 고정하고, PostgreSQL 준비부터 Alembic 스키마 적용과 FastAPI 시작까지의 순서를 Docker Compose가 보장하도록 구성했다.

```text
PostgreSQL healthy
        ↓
Alembic upgrade head (성공 후 종료)
        ↓
FastAPI 시작
        ↓
/health로 프로세스 생존 확인
```

컨테이너는 세 역할로 분리한다.

| 서비스 | 맡은 일 | 정상 상태 |
|---|---|---|
| `postgres` | 음성 기준선과 캘리브레이션 샘플 영속 저장 | `pg_isready` 성공 |
| `migrate` | Alembic의 최신 스키마를 한 번 적용 | 종료 코드 0으로 완료 |
| `api` | FastAPI 요청 처리 | `/health` 200 |

`migrate`는 계속 실행되는 서버가 아니다. 데이터베이스 구조를 최신 상태로 만든 뒤 종료되는 일회성 작업이다. API는 이 작업이 성공한 경우에만 시작한다.

## 이미지 재현성

기준 이미지는 Python 버전과 이미지 digest를 함께 고정한다.

```dockerfile
ARG PYTHON_IMAGE=python:3.11.16-slim-trixie@sha256:...
```

- `3.11.16-slim-trixie`는 Python·Debian 계열과 세부 버전을 사람이 읽기 위한 이름이다.
- `sha256` digest는 실제 이미지 내용을 식별한다.
- 같은 태그가 나중에 다른 내용으로 갱신되더라도 이 저장소는 검증한 바이트 집합을 사용한다.

## 다단계 빌드

Apple Silicon용 `praat-parselmouth` 0.4.7은 Linux ARM64 사전 빌드 wheel이 없어 소스 컴파일이 필요하다. 기능을 제거하거나 다른 패키지로 대체하지 않고, 빌드 단계에만 `build-essential`과 `ninja-build`를 설치한다.

```text
core-dependencies
├─ 컴파일러와 빌드 도구
├─ Python 가상환경
└─ 고정된 핵심 패키지 설치

core-runtime
├─ 앞 단계에서 완성한 가상환경만 복사
├─ FFmpeg와 CA 인증서
└─ 애플리케이션 코드
```

최종 이미지에는 GCC와 Ninja가 남지 않는다. 이렇게 빌드 도구와 실행 도구를 나누면 이미지 크기와 불필요한 공격 수단을 줄이고, 실행 서버의 책임을 명확하게 유지할 수 있다.

## 실행 권한과 파일 시스템

API와 마이그레이션은 Linux 관리자 계정인 `root`가 아니라 UID/GID 10001의 `maeumcall` 사용자로 실행한다.

Compose에는 다음 제한을 적용한다.

- `read_only`: 이미지의 파일 시스템을 실행 중 수정하지 못하게 한다.
- `tmpfs`: `/tmp/maeumcall`만 메모리 기반 임시 쓰기 공간으로 제공한다.
- `cap_drop: ALL`: 프로세스에 추가 Linux capability를 주지 않는다.
- `no-new-privileges`: 실행 도중 더 높은 권한을 획득하지 못하게 한다.
- `pids_limit`: 컨테이너가 만들 수 있는 프로세스 수를 제한한다.
- 로그 회전: JSON 로그 파일을 10MB·3개로 제한한다.

PostgreSQL 공식 이미지는 최초 실행 중 데이터 디렉터리 소유권을 조정해야 한다. 따라서 API 설정을 그대로 복사하지 않고, 루프백 포트 바인딩·전용 볼륨·상태 점검·로그 회전을 적용한다.

## liveness와 readiness

두 상태 점검은 질문이 다르다.

| 구분 | 질문 | 이 프로젝트의 경로 |
|---|---|---|
| liveness | 서버 프로세스가 살아 있고 HTTP에 답하는가? | `/health` |
| readiness | 실제 기능에 필요한 DB·모델·보안 설정이 모두 준비됐는가? | `/health/ready` |

Docker의 `HEALTHCHECK`는 liveness를 사용한다. 아직 로컬 모델을 넣지 않은 핵심 이미지도 API 프로세스와 오류 계약을 제공할 수 있기 때문이다. 트래픽을 받을 수 있는지를 결정하는 배포 시스템은 readiness를 사용해야 한다.

현재 `core-runtime`은 로컬 Hugging Face NLU 실행 패키지와 모델 가중치를 의도적으로 포함하지 않는다. Compose도 호스트 `.env`와 관계없이 `HF_LOCAL_MODEL_ENABLED=0`, `TTS_ENABLED=0`으로 고정한다. 따라서 검증 환경에서 `/health`는 200이고 `/health/ready`는 `local_nlu`만 미준비인 503이어야 한다. 모델이 없는 상태를 준비 완료로 표시하지 않는다.

## 로컬 실행

저장소 밖 `.env`에 URL에서 사용할 수 있는 `POSTGRES_PASSWORD`와 필요한 인증·HMAC 값을 설정한다. Compose는 PostgreSQL 내부 호스트명인 `postgres`를 사용해 `DATABASE_URL`을 구성한다.

```bash
docker compose up --build --detach
docker compose ps --all
```

API는 `http://127.0.0.1:8001`에 노출된다. 스키마 상태를 다시 확인하려면 다음 명령을 사용한다.

```bash
docker compose run --rm migrate alembic check
```

작업이 끝나면 컨테이너를 중지한다. 영속 DB를 보존할 때는 `--volumes`를 사용하지 않는다.

```bash
docker compose down
```

`docker compose down --volumes`는 PostgreSQL 볼륨까지 삭제하므로, 실제 데이터가 있는 기본 프로젝트에는 사용하지 않는다. CI와 로컬 스모크 테스트는 별도 프로젝트 이름으로 만든 전용 볼륨만 삭제한다.

## 자동 검증

`test-container` GitHub Actions는 pull request와 `main`·`develop` push에서 다음 계약을 확인한다.

1. Compose 문법과 환경 변수 보간
2. 고정된 Python 3.11 핵심 이미지 빌드
3. PostgreSQL 상태 점검 후 Alembic 적용
4. `alembic check`로 모델과 DB 스키마 차이 확인
5. UID 10001 실행과 최종 이미지의 GCC·Ninja 부재
6. API metadata·liveness·core readiness 구성 요소 확인
7. 성공·실패와 관계없이 격리 컨테이너와 전용 볼륨 제거

HTTP 계약 검사는 `scripts/verify_core_container.py`가 담당한다. 단순히 503을 허용하지 않고, 서버 버전과 각 readiness 구성 요소의 명시적 참·거짓 값을 확인한다. 핵심 이미지에서 미준비인 항목은 정확히 `local_nlu` 하나여야 한다.

## 질문과 답

### Q. 이미지와 컨테이너는 무엇이 다른가?

이미지는 서버 실행에 필요한 Python·패키지·코드·기본 명령을 묶은 읽기 전용 설계도다. 컨테이너는 그 이미지로 실제 실행한 프로세스다. 같은 이미지로 여러 컨테이너를 만들 수 있으며, 컨테이너가 종료되어도 PostgreSQL의 named volume은 별도로 남길 수 있다.

### Q. Dockerfile과 Compose는 무엇이 다른가?

Dockerfile은 AI 서버 이미지 한 개를 어떻게 만들지 정의한다. Compose는 완성된 AI 서버와 PostgreSQL처럼 여러 컨테이너를 어떤 환경 변수·포트·볼륨·실행 순서로 함께 운영할지 정의한다.

### Q. Alembic을 API 시작 코드에 넣으면 왜 안 되는가?

API를 여러 개 실행하면 모든 인스턴스가 동시에 테이블 변경을 시도할 수 있다. 마이그레이션을 별도 일회성 서비스로 두면 한 작업의 성공 여부를 확인한 뒤 API를 시작할 수 있고, 실패한 스키마에서 요청을 받는 일을 막을 수 있다.

### Q. 왜 모델 가중치를 이미지에 바로 넣지 않는가?

모델 파일은 크고 실행 장치마다 배포 방식이 다르다. 코드·핵심 패키지 이미지와 승인된 모델 자산을 분리하면 작은 코드 변경마다 수GB 모델을 다시 배포하지 않아도 된다. 이후 ML 실행 이미지는 고정된 `requirements-ml.txt`와 모델 리비전, 읽기 전용 모델 볼륨을 하나의 배포 계약으로 검증해야 한다.

### Q. `restart: unless-stopped`가 모든 실패를 해결하는가?

아니다. 프로세스를 다시 시작할 뿐 잘못된 비밀값, 누락된 모델, 실패한 마이그레이션을 고치지 않는다. 그래서 API 재시작 정책과 별개로 readiness, 타입이 있는 오류, 마이그레이션 종료 코드를 확인한다.

### Q. 왜 CI 데이터베이스를 실제 개발 데이터베이스와 분리하는가?

테스트는 테이블 생성·삭제와 실패 상황을 반복한다. 별도 Compose 프로젝트 이름을 사용하면 네트워크·컨테이너·볼륨 이름이 분리되어 실제 사용자 데이터에 영향을 주지 않는다. 검증 종료 시 삭제하는 것도 이 전용 자원뿐이다.

## 공식 참고 자료

- [Docker Official Image - Python](https://hub.docker.com/_/python)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Compose startup order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Docker Engine security](https://docs.docker.com/engine/security/)
