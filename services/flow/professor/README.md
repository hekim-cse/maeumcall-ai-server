# Professor LangGraph

교수님 카테고리의 면담 예약, 과제 문의, 결석 사유 전달을 상태 기반으로 처리합니다.

## 공통 처리 방식

```text
사용자 발화
  → Kanana 구조화 출력
  → 시나리오별 JSON 계약 검증
  → LangGraph 상태 전이
  → 교수님 응답 정책
  → 추천 답변과 scenarioState 반환
```

모델은 `appointment_purpose`, `assignment_topic`, `absence_reason`, `user_action`을 추출합니다. 서버는 허용된 필드 타입과 action만 상태에 병합합니다. 계약 위반은 원인을 포함해 한 번 재요청하고, 반복 실패는 `AI_RESPONSE_VALIDATION_FAILED`로 반환합니다.

교수님 역할의 문장은 검증된 상태를 기반으로 응답 정책이 만듭니다. 따라서 모델 장애나 말투 변동이 상태 결과를 바꾸지 않습니다.

## 상태 흐름

### 면담 예약

```text
collecting_appointment_info
  → confirming_info
  → appointment_confirmed
  → closing
  → END
```

필수 필드는 면담 목적, 날짜, 시간, 학생 이름입니다. 확인 단계에서 특정 정보를 변경하면 해당 필드만 초기화하고 다시 수집합니다.

### 과제 문의

```text
collecting_assignment_info
  → answering_assignment_question
  → closing
  → END
```

필수 필드는 과제 주제, 실제 질문, 학생 이름입니다. 후속 질문을 선택하면 질문 필드만 다시 수집합니다.

### 결석 사유 전달

```text
collecting_absence_info
  → confirming_absence_info
  → absence_noted
  → closing
  → END
```

필수 필드는 결석 날짜, 사유, 학생 이름입니다. 수업명은 선택 필드입니다.

## 테스트 기준

- 전체 정보와 부분 정보의 병합
- 필수 필드 누락 시 수집 상태 유지
- 확인 후 단일 필드 변경
- 허용되지 않은 action과 잘못된 JSON의 명시적 실패
- 완료, 마무리, 종료 상태와 `shouldEndCall`
- API 응답의 `scenarioState` 보존
