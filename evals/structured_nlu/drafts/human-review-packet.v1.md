# 구조화 NLU AI 초안 사람 작성 작업지 V1

> 이 문서는 16개 AI 제안을 검토하기 위한 읽기·작성 양식입니다.
> 공식 골든 corpus, 검수 원장 또는 사람 승인 증거가 아닙니다.

- 작업지 버전: `1`
- 평가 프로필: `maeumcall-structured-nlu-v3`
- 프로필 지문: `3b6fc800eca438fa0d5c49f9004f83c638930284dd26c8f365aae1be411bf580`
- AI 제안 수: `16`

## 작성 규칙

1. AI 문장을 그대로 복사하지 말고 참고만 한 뒤 사람이 새 문장을 작성합니다.
2. 현재 상태·intent·user_action·필드·태그를 작성 지침과 라이브 계약에 맞춰 다시 확인합니다.
3. 채택하지 않을 제안은 `거부`로 표시하고 이유를 남깁니다.
4. 작성이 끝난 항목도 곧바로 `adjudicated`가 되지 않습니다. 별도 검수 원장을 거쳐야 합니다.
5. 이 커밋된 원본 양식은 직접 편집하지 말고 작업용 사본에 답을 작성합니다.

## 01. 고객센터:a/s 접수

- 제안 ID: `ai-seed-support-service`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “내일 비가 오는지 알려 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "intent": "service_request",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 02. 고객센터:요금/약정 상담

- 제안 ID: `ai-seed-support-plan`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “새로 나온 영화가 무엇인가요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "intent": "plan_contract_consultation",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 03. 고객센터:인터넷/통화 문제 문의

- 제안 ID: `ai-seed-support-network`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “이번 주말 공연 일정이 궁금해요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "intent": "network_call_issue",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 04. 교수님:결석 사유 전달

- 제안 ID: `ai-seed-professor-absence`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “도서관 운영 시간이 궁금합니다.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "absence_date": null,
    "absence_reason": null,
    "class_name": null,
    "user_name": null
  },
  "intent": "absence_notice",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 05. 교수님:과제 문의

- 제안 ID: `ai-seed-professor-assignment`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “교수님 연구실 위치가 어디예요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "assignment_topic": null,
    "course_name": null,
    "question": null,
    "user_name": null
  },
  "intent": "assignment_inquiry",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 06. 교수님:면담 예약

- 제안 ID: `ai-seed-professor-appointment`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “학교 축제는 언제 열리나요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "appointment_purpose": null,
    "date": null,
    "time": null,
    "user_name": null
  },
  "intent": "appointment_booking",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 07. 배달:배달 지연 문의

- 제안 ID: `ai-seed-delivery-delay`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “오늘 야구 경기 결과를 알려 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "delay_detail": null,
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": null
  },
  "intent": "delivery_delay_inquiry",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 08. 배달:주문 변경

- 제안 ID: `ai-seed-delivery-change`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “배달 앱 배경색을 바꿀 수 있나요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "intent": "delivery_order_change",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 09. 배달:환불/재배달 문의

- 제안 ID: `ai-seed-delivery-refund`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “휴대폰 배경화면을 추천해 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "intent": "delivery_refund_redelivery",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 10. 시청:대형폐기물 배출

- 제안 ID: `ai-seed-city-bulky-waste`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “시청 근처 카페를 추천해 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": null
  },
  "intent": "bulky_waste_guidance",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 11. 시청:여권 발급 문의

- 제안 ID: `ai-seed-city-passport`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “근처 공원 산책로를 알려 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "intent": "passport_guidance",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 12. 시청:주민등록 등본 문의

- 제안 ID: `ai-seed-city-certificate`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “오늘 미세먼지는 어떤가요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "intent": "resident_certificate_guidance",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 13. 예약:미용실 예약

- 제안 ID: `ai-seed-hair-salon`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “요즘 읽을 만한 책이 있나요?”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "date": null,
    "designer": null,
    "selected_time": null,
    "service_type": null,
    "time": null,
    "user_name": null
  },
  "intent": "reservation",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 14. 예약:병원 예약

- 제안 ID: `ai-seed-hospital`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “오늘 날씨가 맑네요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "date": null,
    "department": null,
    "selected_time": null,
    "time": null,
    "user_name": null
  },
  "intent": null,
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 15. 예약:스터디룸 예약

- 제안 ID: `ai-seed-study-room`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “지하철 첫차 시간이 궁금해요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "date": null,
    "duration": null,
    "party_size": null,
    "selected_time": null,
    "start_time": null,
    "user_name": null
  },
  "intent": "reservation",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.

## 16. 예약:식당 예약

- 제안 ID: `ai-seed-restaurant`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- AI 제안 발화: “주말에 볼 영화 추천해 주세요.”
- AI 제안 정답:

```json
{
  "change_field": null,
  "fields": {
    "date": null,
    "party_size": null,
    "selected_time": null,
    "time": null,
    "user_name": null
  },
  "intent": "reservation",
  "tags": [
    "hard_negative"
  ],
  "user_action": "unknown"
}
```

### 사람 작성란

- 판단: [ ] 참고 후 새로 작성  [ ] 거부
- 새 `conversation_group_id`: `{{직접 작성}}`
- 새 case ID: `{{직접 작성}}`
- 사람이 새로 작성한 발화:
  > {{AI 문장과 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 작성}}
- [ ] 최종 발화와 정답을 직접 작성했으며 AI 제안을 그대로 복사하지 않았습니다.
