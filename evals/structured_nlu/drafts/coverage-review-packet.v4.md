# 구조화 NLU 현재 옵션 커버리지 후보 검토 작업지 V4

> 19개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에 판단을 기록합니다.

- 선행 V3 artifact SHA-256: `c30d43ede76fd4db84797be270201b5382eecc7b8fa71a93c2b36d55a0ea8e03`
- 기준 충족/미충족: `668` / `894`
- 투영 증가: `45`
- 투영 충족/미충족: `713` / `849`
- 자동 승격 허용: `false`

## 01. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v4-city-certificate-documents-bundle`
- AI 후보 발화: “주민센터에 자전거 보관소가 있나요?”
```json
{
  "current_fields": {
    "applicant_relation": "representative",
    "document_type": "register_copy",
    "inquiry_topic": "documents",
    "issuance_channel": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=representative"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type=register_copy"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=documents"
    },
    {
      "dimension": "state_action",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "collecting_certificate_inquiry->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=representative"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type=register_copy"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=documents"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 02. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v4-city-certificate-eligibility-bundle`
- AI 후보 발화: “무인민원발급기 화면 밝기를 조절할 수 있나요?”
```json
{
  "current_fields": {
    "applicant_relation": "same_household",
    "document_type": null,
    "inquiry_topic": "eligibility",
    "issuance_channel": "kiosk"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=same_household"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=eligibility"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=kiosk"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=same_household"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=eligibility"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=kiosk"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 03. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v4-city-certificate-fee-in-person`
- AI 후보 발화: “주민센터 문화 강좌 일정이 궁금해요.”
```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": "fee",
    "issuance_channel": "in_person"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=fee"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=in_person"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=fee"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=in_person"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 04. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v4-city-passport-office-bundle`
- AI 후보 발화: “시청 주차 요금이 궁금합니다.”
```json
{
  "current_fields": {
    "applicant_type": "minor",
    "application_channel": null,
    "application_type": "reissue",
    "inquiry_topic": "office"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": null
    },
    "intent": "passport_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=minor"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=reissue"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=office"
    },
    {
      "dimension": "state_action",
      "scenario_key": "시청:여권 발급 문의",
      "value": "collecting_passport_inquiry->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=minor"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=reissue"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=office"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 05. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v4-city-passport-processing-channel`
- AI 후보 발화: “근처 도서관 휴관일을 알려 주세요.”
```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": "government24",
    "application_type": null,
    "inquiry_topic": "processing_time"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": null
    },
    "intent": "passport_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=government24"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=processing_time"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=government24"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=processing_time"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 06. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v4-city-waste-collection`
- AI 후보 발화: “시청 민원실 점심시간이 언제예요?”
```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": "collection_status"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=collection_status"
    },
    {
      "dimension": "state_action",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "collecting_bulky_waste->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=collection_status"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 07. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v4-city-waste-fee`
- AI 후보 발화: “동네 체육관 운영 시간을 알려 주세요.”
```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": "fee"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=fee"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=fee"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 08. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v4-city-waste-place`
- AI 후보 발화: “가로등 고장은 어디에 신고하나요?”
```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": "place_and_schedule"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=place_and_schedule"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=place_and_schedule"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 09. 배달:주문 변경

- 후보 ID: `ai-coverage-v4-delivery-change-address-cancel`
- AI 후보 발화: “배달 기사님 평점은 어디서 보나요?”
```json
{
  "current_fields": {
    "change_type": "delivery_address",
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": "check_cancellation"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=delivery_address"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=check_cancellation"
    },
    {
      "dimension": "state_action",
      "scenario_key": "배달:주문 변경",
      "value": "collecting_order_change->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=delivery_address"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=check_cancellation"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 10. 배달:주문 변경

- 후보 ID: `ai-coverage-v4-delivery-change-menu-option-keep`
- AI 후보 발화: “앱 알림 소리를 끌 수 있나요?”
```json
{
  "current_fields": {
    "change_type": "menu_option",
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": "keep_order"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_option"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=keep_order"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_option"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=keep_order"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 11. 배달:주문 변경

- 후보 ID: `ai-coverage-v4-delivery-change-menu-quantity`
- AI 후보 발화: “이번 달 쿠폰은 언제 나오나요?”
```json
{
  "current_fields": {
    "change_type": "menu_or_quantity",
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_or_quantity"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_or_quantity"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 12. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v4-delivery-delay-cancel-estimated`
- AI 후보 발화: “배달 앱 글자 크기를 키울 수 있나요?”
```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": "check_cancellation",
    "inquiry_goal": "estimated_arrival",
    "order_number": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "delay_detail": null,
      "delay_resolution": null,
      "inquiry_goal": null,
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=check_cancellation"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=estimated_arrival"
    },
    {
      "dimension": "state_action",
      "scenario_key": "배달:배달 지연 문의",
      "value": "collecting_delay_inquiry->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=check_cancellation"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=estimated_arrival"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 13. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v4-delivery-delay-wait`
- AI 후보 발화: “리뷰를 작성하면 포인트를 주나요?”
```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": "wait",
    "inquiry_goal": null,
    "order_number": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "delay_detail": null,
      "delay_resolution": null,
      "inquiry_goal": null,
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=wait"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=wait"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 14. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v4-delivery-refund-wrong-refund`
- AI 후보 발화: “배달 앱 테마를 어둡게 바꾸고 싶어요.”
```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": "wrong_item",
    "order_number": null,
    "resolution_preference": "refund"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "evidence_status": null,
      "issue_detail": null,
      "issue_type": null,
      "order_number": null,
      "resolution_preference": null
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=wrong_item"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=refund"
    },
    {
      "dimension": "state_action",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "collecting_refund_redelivery->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=wrong_item"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=refund"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 15. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v4-support-network-wifi-multiple`
- AI 후보 발화: “새 휴대폰 케이스 색상을 추천해 주세요.”
```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": "multiple_devices",
    "service_type": "wifi",
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
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
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=multiple_devices"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wifi"
    },
    {
      "dimension": "state_action",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "collecting_network_issue->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=multiple_devices"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wifi"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 16. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v4-support-plan-contract-expiry-general`
- AI 후보 발화: “멤버십으로 영화 할인도 받을 수 있나요?”
```json
{
  "current_fields": {
    "consent_scope": "general_guidance",
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": "contract_expiry"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consent_scope=general_guidance"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=contract_expiry"
    },
    {
      "dimension": "state_action",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "collecting_plan_contract->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consent_scope=general_guidance"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=contract_expiry"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 17. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v4-support-plan-discount`
- AI 후보 발화: “휴대폰 배경화면을 바꾸는 방법이 궁금해요.”
```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": "discount"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=discount"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=discount"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 18. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v4-support-plan-plan-change`
- AI 후보 발화: “가까운 대리점 주차장이 넓은가요?”
```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": "plan_change"
  },
  "labels": {
    "change_field": null,
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=plan_change"
    }
  ],
  "tags": [
    "hard_negative"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=plan_change"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 19. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v4-support-service-safety-visit`
- AI 후보 발화: “보호필름 할인 행사도 하나요?”
```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": "safety_issue",
    "service_channel": "visit",
    "symptom": null
  },
  "labels": {
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
    "user_action": "unknown"
  },
  "projected_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status=safety_issue"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=visit"
    },
    {
      "dimension": "current_fields_context",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_action_required->guarded_partial"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety"
    },
    {
      "dimension": "state_action",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_action_required->unknown"
    }
  ],
  "tags": [
    "hard_negative",
    "safety"
  ],
  "target_obligations": [
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status=safety_issue"
    },
    {
      "dimension": "current_field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=visit"
    }
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
