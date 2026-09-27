# 구조화 NLU 커버리지 후보 검토 작업지 V2

> 이 문서의 4개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에서 판단을 기록합니다.

- 작업지 버전: `2`
- 후보 묶음: `structured-nlu-coverage-candidates-v2`
- 선행 후보 묶음: `structured-nlu-coverage-candidates-v1`
- 기준 진단 case 수: `24`
- 기준 충족/미충족 의무: `582` / `980`
- 투영 추가 충족 의무: `31`
- 투영 충족/미충족 의무: `613` / `949`
- 자동 승격 허용: `false`

## 01. 시청:대형폐기물 배출 / quantity

- 후보 ID: `ai-coverage-v2-city-bulky-waste-quantity-clear`
- 기준 의무: `current_field_present` / `quantity`
- AI 후보 발화: “수량은 아직 정하지 않았어요.”
- 제안 입력·정답·투영 의무:

```json
{
  "conversation_state": "collecting_bulky_waste",
  "current_fields": {
    "item_name": "소파",
    "quantity": "1개",
    "region": "인천 독산동",
    "request_topic": null
  },
  "labels": {
    "change_field": "quantity",
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "change_detail"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_absent",
      "value": "change_detail->quantity"
    },
    {
      "dimension": "change_field",
      "value": "quantity"
    },
    {
      "dimension": "current_delta_relation",
      "value": "quantity->current_value_not_reemitted"
    },
    {
      "dimension": "current_delta_relation",
      "value": "quantity->existing_value_cleared"
    },
    {
      "dimension": "current_field_present",
      "value": "quantity"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "collecting_bulky_waste->change_detail"
    }
  ],
  "tags": [
    "correction"
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 02. 시청:주민등록 등본 문의 / issuance_channel

- 후보 ID: `ai-coverage-v2-city-certificate-issuance-channel-clear`
- 기준 의무: `current_field_present` / `issuance_channel`
- AI 후보 발화: “발급 방법은 아직 정하지 않을게요.”
- 제안 입력·정답·투영 의무:

```json
{
  "conversation_state": "collecting_certificate_inquiry",
  "current_fields": {
    "applicant_relation": "self",
    "document_type": "individual_extract",
    "inquiry_topic": null,
    "issuance_channel": "government24"
  },
  "labels": {
    "change_field": "issuance_channel",
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "change_detail"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_absent",
      "value": "change_detail->issuance_channel"
    },
    {
      "dimension": "change_field",
      "value": "issuance_channel"
    },
    {
      "dimension": "current_delta_relation",
      "value": "issuance_channel->current_value_not_reemitted"
    },
    {
      "dimension": "current_delta_relation",
      "value": "issuance_channel->existing_value_cleared"
    },
    {
      "dimension": "current_field_option",
      "value": "issuance_channel=government24"
    },
    {
      "dimension": "current_field_present",
      "value": "issuance_channel"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "collecting_certificate_inquiry->change_detail"
    }
  ],
  "tags": [
    "correction"
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 03. 배달:주문 변경 / unavailable_preference

- 후보 ID: `ai-coverage-v2-delivery-change-unavailable-preference-clear`
- 기준 의무: `current_field_present` / `unavailable_preference`
- AI 후보 발화: “변경이 안 될 때 상담원 연결 요청은 취소할게요.”
- 제안 입력·정답·투영 의무:

```json
{
  "conversation_state": "collecting_order_change",
  "current_fields": {
    "change_type": "contact",
    "order_number": "별빛아파트 301호",
    "requested_change": null,
    "unavailable_preference": "agent_handoff"
  },
  "labels": {
    "change_field": "unavailable_preference",
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "change_detail"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_absent",
      "value": "change_detail->unavailable_preference"
    },
    {
      "dimension": "change_field",
      "value": "unavailable_preference"
    },
    {
      "dimension": "current_delta_relation",
      "value": "unavailable_preference->current_value_not_reemitted"
    },
    {
      "dimension": "current_delta_relation",
      "value": "unavailable_preference->existing_value_cleared"
    },
    {
      "dimension": "current_field_option",
      "value": "unavailable_preference=agent_handoff"
    },
    {
      "dimension": "current_field_present",
      "value": "unavailable_preference"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "collecting_order_change->change_detail"
    }
  ],
  "tags": [
    "correction"
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 04. 고객센터:요금/약정 상담 / consent_scope

- 후보 ID: `ai-coverage-v2-support-plan-consent-scope-clear`
- 기준 의무: `current_field_present` / `consent_scope`
- AI 후보 발화: “가입 정보 조회 동의는 취소할게요.”
- 제안 입력·정답·투영 의무:

```json
{
  "conversation_state": "collecting_plan_contract",
  "current_fields": {
    "consent_scope": "authenticated_lookup",
    "consultation_goal": null,
    "current_service": "0청년 요금제",
    "inquiry_type": "billing"
  },
  "labels": {
    "change_field": "consent_scope",
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "change_detail"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_absent",
      "value": "change_detail->consent_scope"
    },
    {
      "dimension": "change_field",
      "value": "consent_scope"
    },
    {
      "dimension": "current_delta_relation",
      "value": "consent_scope->current_value_not_reemitted"
    },
    {
      "dimension": "current_delta_relation",
      "value": "consent_scope->existing_value_cleared"
    },
    {
      "dimension": "current_field_option",
      "value": "consent_scope=authenticated_lookup"
    },
    {
      "dimension": "current_field_present",
      "value": "consent_scope"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "collecting_plan_contract->change_detail"
    }
  ],
  "tags": [
    "correction"
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}
