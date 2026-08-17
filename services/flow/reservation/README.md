# Reservation LangGraph

병원, 식당, 미용실, 스터디룸 예약을 도메인별 상태 그래프로 처리합니다.

## 공통 처리 방식

```text
사용자 발화
  → Kanana 구조화 출력
  → 예약 JSON 계약 검증
  → 필수 정보 수집
  → 버전 지정 훈련 일정 조회
  → 예약 상태 전이
  → 도메인 응답 정책
```

모델은 날짜, 시간, 인원, 서비스 종류와 `user_action`을 구조화합니다. 서버는 검증된 값만 상태에 병합합니다. 예약 가능 여부는 `data/reservation_availability_catalog.json`의 명시된 요청 시간과 슬롯만 사용하며, 목록에 없는 시간을 예약 가능으로 추측하지 않습니다.

## 시나리오

| 시나리오 | 주요 필드 |
|---|---|
| 병원 | 진료과, 날짜, 시간 |
| 식당 | 날짜, 시간, 인원, 예약자 이름 |
| 미용실 | 날짜, 시간, 시술, 디자이너, 예약자 이름 |
| 스터디룸 | 날짜, 시작 시간, 이용 시간, 인원, 예약자 이름 |

## 대표 상태 흐름

```text
collecting_reservation_info
  → confirming_info
  → checking_availability
  ├─ reservation_available
  └─ reservation_unavailable
       → suggest_alternative
  → reservation_confirmed
  → closing
  → END
```

병원 그래프는 누락 필드에 따라 `asking_department`, `asking_date`, `asking_time`을 별도로 사용합니다.

## 책임 경계

- LLM: 사용자 발화를 명시된 JSON 스키마로 변환
- LangGraph: 현재 상태에서 허용된 action과 다음 상태 결정
- availability provider: 버전 지정 일정표에서 예약 가능 시간과 대안 시간 조회
- response policy: 서버가 확정한 사실을 사용자 문장으로 표현
- response adapter: 모바일이 이어서 보낼 `scenarioState` 구성

예약 불가 상태에서 대안 시간이 없으면 다른 날짜나 시간을 요청하는 승인 문장을 사용합니다. 존재하지 않는 대안 시간이나 예약 결과를 모델이 생성할 수 없습니다.

클라이언트가 보낸 `scenarioState`에는 가용성 공급자 원본 결과를 포함하지 않습니다. 모바일은 서버가 확정해 반환한 상태만 보관하며, 일정표 경로는 `RESERVATION_AVAILABILITY_CATALOG_PATH`로 운영 환경에서 교체할 수 있습니다. 일정표가 없거나 스키마가 올바르지 않으면 성공 결과를 만들지 않고 `AVAILABILITY_PROVIDER_CONFIGURATION_ERROR`로 실패합니다.

## 테스트 기준

- 필수 정보 수집 순서와 부분 상태 보존
- 확인 단계의 날짜·시간·인원·이름 변경
- 예약 가능/불가와 대안 시간 선택
- 허용 목록 밖의 대안 시간 거부
- 최종 시간 선택 우선순위
- 구조화 출력의 재시도와 명시적 실패
- 이모지가 포함된 모바일 제목 라우팅
