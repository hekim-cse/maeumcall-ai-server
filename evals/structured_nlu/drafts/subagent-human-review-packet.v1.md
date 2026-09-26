# 구조화 NLU 서브 에이전트 후보 사람 작성 작업지 V1

> 이 문서의 후보와 판단 근거도 AI가 작성했습니다.
> 그대로 복사하면 human_authored 골든 데이터가 될 수 없습니다.

- 작업지 버전: `1`
- 후보 묶음: `structured-nlu-subagent-candidates-v1`
- 평가 프로필: `maeumcall-structured-nlu-v3`
- 프로필 지문: `3b6fc800eca438fa0d5c49f9004f83c638930284dd26c8f365aae1be411bf580`
- 서브 에이전트 후보 수: `16`
- 자동 승격 허용: `false`

## 작성 규칙

1. 후보 문장과 근거는 참고만 하고 사람이 새 표현과 판단 근거를 직접 작성합니다.
2. 원래 AI seed와 서브 에이전트 후보 어느 쪽도 그대로 복사하지 않습니다.
3. 사람이 작성한 결과는 별도 AuthoringGroup source와 검수 원장에서 다시 확인합니다.
4. 이 작업지를 채웠다는 사실만으로 draft·reviewed·adjudicated 상태가 되지 않습니다.

## 01. 고객센터:a/s 접수

- 후보 ID: `ai-subagent-support-service`
- 원본 제안 ID: `ai-seed-support-service`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “근처에서 자전거를 빌릴 수 있는 곳을 알려 주세요.”
- 서브 에이전트 판단 근거: 제품 고장·접수·안전 정보가 전혀 없으므로 greeting에서 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 02. 고객센터:요금/약정 상담

- 후보 ID: `ai-subagent-support-plan`
- 원본 제안 ID: `ai-seed-support-plan`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “이번 달 보름달은 언제 뜨나요?”
- 서브 에이전트 판단 근거: 요금·약정·서비스 상담과 무관해 상담 필드를 추출하면 안 된다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 03. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-subagent-support-network`
- 원본 제안 ID: `ai-seed-support-network`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “화분에는 물을 며칠마다 줘야 하나요?”
- 서브 에이전트 판단 근거: 인터넷·통화 장애나 조치 이력이 없는 원예 질문이므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 04. 교수님:결석 사유 전달

- 후보 ID: `ai-subagent-professor-absence`
- 원본 제안 ID: `ai-seed-professor-absence`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “학생식당에 채식 메뉴도 있나요?”
- 서브 에이전트 판단 근거: 학교 맥락이지만 결석 전달과 무관하고 결석 필드가 없으므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 05. 교수님:과제 문의

- 후보 ID: `ai-subagent-professor-assignment`
- 원본 제안 ID: `ai-seed-professor-assignment`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “강의실 에어컨은 어디서 켜나요?”
- 서브 에이전트 판단 근거: 질문 형태여도 과제에 관한 질문이 아니므로 업무 필드를 채우지 않는다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 06. 교수님:면담 예약

- 후보 ID: `ai-subagent-professor-appointment`
- 원본 제안 ID: `ai-seed-professor-appointment`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “교내 체육관은 몇 시에 닫나요?”
- 서브 에이전트 판단 근거: 시간 질문이지만 교수 면담 시간이 아니므로 예약 필드를 추출하지 않는다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 07. 배달:배달 지연 문의

- 후보 ID: `ai-subagent-delivery-delay`
- 원본 제안 ID: `ai-seed-delivery-delay`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “김치찌개를 맛있게 끓이는 법을 알려 주세요.”
- 서브 에이전트 판단 근거: 주문·지연·해결 요청이 없는 조리법 질문이므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 08. 배달:주문 변경

- 후보 ID: `ai-subagent-delivery-change`
- 원본 제안 ID: `ai-seed-delivery-change`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “배달 기사 모집 공고는 어디서 보나요?”
- 서브 에이전트 판단 근거: 배달이라는 단어가 있지만 주문 변경이 아닌 구직 질문이므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 09. 배달:환불/재배달 문의

- 후보 ID: `ai-subagent-delivery-refund`
- 원본 제안 ID: `ai-seed-delivery-refund`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “종이비행기를 멀리 날리려면 어떻게 접어야 하나요?”
- 서브 에이전트 판단 근거: 주문 문제·증빙·환불 또는 재배달 요청이 없으므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 10. 시청:대형폐기물 배출

- 후보 ID: `ai-subagent-city-bulky-waste`
- 원본 제안 ID: `ai-seed-city-bulky-waste`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “도서관 회원증은 어디서 만들 수 있나요?”
- 서브 에이전트 판단 근거: 공공서비스 질문이지만 대형폐기물 배출 업무와 무관하므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 11. 시청:여권 발급 문의

- 후보 ID: `ai-subagent-city-passport`
- 원본 제안 ID: `ai-seed-city-passport`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “시립 수영장은 무슨 요일에 쉬나요?”
- 서브 에이전트 판단 근거: 시청 관련 시설 질문이지만 여권 신청·발급 정보가 없으므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 12. 시청:주민등록 등본 문의

- 후보 ID: `ai-subagent-city-certificate`
- 원본 제안 ID: `ai-seed-city-certificate`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “버스에서 잃어버린 물건은 어디에 문의하나요?”
- 서브 에이전트 판단 근거: 공공 문의처럼 보여도 등본 종류·발급 채널·신청 관계가 없으므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 13. 예약:미용실 예약

- 후보 ID: `ai-subagent-hair-salon`
- 원본 제안 ID: `ai-seed-hair-salon`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “사진을 인화하려면 어디로 가야 하나요?”
- 서브 에이전트 판단 근거: 미용 서비스·예약 일시·디자이너와 무관하므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 14. 예약:병원 예약

- 후보 ID: `ai-subagent-hospital`
- 원본 제안 ID: `ai-seed-hospital`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “근처에서 우산을 살 수 있을까요?”
- 서브 에이전트 판단 근거: 진료과·예약 일시·예약자 정보가 없는 생활 질문이므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 15. 예약:스터디룸 예약

- 후보 ID: `ai-subagent-study-room`
- 원본 제안 ID: `ai-seed-study-room`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “노트북 배터리를 오래 쓰는 방법이 궁금해요.”
- 서브 에이전트 판단 근거: 스터디룸 날짜·시작 시간·인원·이용 시간과 무관하므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.

## 16. 예약:식당 예약

- 후보 ID: `ai-subagent-restaurant`
- 원본 제안 ID: `ai-seed-restaurant`
- 기준 의무: `state_action` / `greeting->unknown`
- 현재 상태: `greeting`
- 서브 에이전트 후보 발화: “냉장고 적정 온도는 몇 도인가요?”
- 서브 에이전트 판단 근거: 식당 예약과 무관하고 예약 필드가 없으므로 unknown이다.
- 제안 정답:

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
  > {{위 후보와 다른 표현을 직접 작성}}
- 최종 정답 또는 수정 사항:
  > {{intent·action·fields·tags를 확인해 작성}}
- 사람이 작성한 판단 근거:
  > {{현재 상태와 작성 지침을 근거로 직접 작성}}
- [ ] 발화·정답·근거를 직접 작성했으며 AI 문장을 그대로 복사하지 않았습니다.
