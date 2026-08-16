# Reservation LangGraph

병원, 식당, 미용실, 스터디룸 예약을 도메인별 상태 그래프로 처리합니다.

## 공통 처리 방식

```text
사용자 발화
  → Kanana 구조화 출력
  → 예약 JSON 계약 검증
  → 필수 정보 수집
  → 가능 여부 시뮬레이션
  → 예약 상태 전이
  → 도메인 응답 정책
```

모델은 날짜, 시간, 인원, 서비스 종류와 `user_action`을 구조화합니다. 서버는 검증된 값만 상태에 병합하며, 예약 가능 여부와 확정 결과는 모델이 아니라 서버 로직이 결정합니다.

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
- availability: 예약 가능 시간과 대안 시간 계산
- response policy: 서버가 확정한 사실을 사용자 문장으로 표현
- response adapter: 모바일이 이어서 보낼 `scenarioState` 구성

예약 불가 상태에서 대안 시간이 없으면 다른 날짜나 시간을 요청하는 승인 문장을 사용합니다. 존재하지 않는 대안 시간이나 예약 결과를 모델이 생성할 수 없습니다.

## 테스트 기준

- 필수 정보 수집 순서와 부분 상태 보존
- 확인 단계의 날짜·시간·인원·이름 변경
- 예약 가능/불가와 대안 시간 선택
- 허용 목록 밖의 대안 시간 거부
- 최종 시간 선택 우선순위
- 구조화 출력의 재시도와 명시적 실패
- 이모지가 포함된 모바일 제목 라우팅
