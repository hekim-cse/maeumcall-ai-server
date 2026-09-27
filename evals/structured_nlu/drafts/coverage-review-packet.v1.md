# 구조화 NLU 커버리지 후보 검토 작업지 V1

> 이 문서의 발화와 정답은 AI가 작성한 미검수 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에서 판단을 기록합니다.
> 작업용 사본의 체크는 비공식 검토 메모이며 별도 승인 원장이나 adjudication이 아닙니다.

- 작업지 버전: `1`
- 후보 묶음: `structured-nlu-coverage-candidates-v1`
- 기준 source: `evals/structured_nlu/data/source`
- 기준 split 원장: `evals/structured_nlu/data/manifests/split-assignments.v1.json`
- 기준 case 수: `36`
- 기준 corpus 지문: `246e22b0d0b83b5ee0619f6ade5629c52fecb07e3b450f477efd2317da5e5ca7`
- 기준 충족 의무: `349`
- 투영 추가 충족 의무: `233`
- 투영 충족 의무: `582`
- 전체 의무: `1562`
- 자동 승격 허용: `false`

## 01. 시청:대형폐기물 배출 / quantity

- 후보 ID: `ai-coverage-v1-city-bulky-waste-quantity`
- 기준 의무: `field_present` / `quantity`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “소파 한 개입니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_bulky_waste",
  "current_fields": {
    "item_name": "소파",
    "quantity": null,
    "region": "인천 독산동",
    "request_topic": "application"
  },
  "fields": {
    "item_name": null,
    "quantity": {
      "accepted_values": [
        "1개"
      ]
    },
    "region": null,
    "request_topic": null
  },
  "intent": "bulky_waste_guidance",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 02. 시청:주민등록 등본 문의 / issuance_channel

- 후보 ID: `ai-coverage-v1-city-certificate-issuance-channel`
- 기준 의무: `field_present` / `issuance_channel`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “정부24로 발급받고 싶어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_certificate_inquiry",
  "current_fields": {
    "applicant_relation": "self",
    "document_type": "individual_extract",
    "inquiry_topic": "delivery",
    "issuance_channel": null
  },
  "fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": {
      "accepted_values": [
        "government24"
      ]
    }
  },
  "intent": "resident_certificate_guidance",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 03. 시청:여권 발급 문의 / applicant_type

- 후보 ID: `ai-coverage-v1-city-passport-applicant-type`
- 기준 의무: `field_present` / `applicant_type`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “성인 본인이 신청하려고 합니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_passport_inquiry",
  "current_fields": {
    "applicant_type": null,
    "application_channel": "overseas_mission",
    "application_type": "emergency",
    "inquiry_topic": "documents"
  },
  "fields": {
    "applicant_type": {
      "accepted_values": [
        "adult_self"
      ]
    },
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "intent": "passport_guidance",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 04. 시청:여권 발급 문의 / application_channel

- 후보 ID: `ai-coverage-v1-city-passport-application-channel`
- 기준 의무: `field_present` / `application_channel`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “정부24로 신청하고 싶습니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_passport_inquiry",
  "current_fields": {
    "applicant_type": "adult_self",
    "application_channel": null,
    "application_type": "first_issue",
    "inquiry_topic": "online_eligibility"
  },
  "fields": {
    "applicant_type": null,
    "application_channel": {
      "accepted_values": [
        "government24"
      ]
    },
    "application_type": null,
    "inquiry_topic": null
  },
  "intent": "passport_guidance",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 05. 시청:여권 발급 문의 / application_type

- 후보 ID: `ai-coverage-v1-city-passport-application-type`
- 기준 의무: `field_present` / `application_type`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “긴급여권을 신청하려고 합니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_passport_inquiry",
  "current_fields": {
    "applicant_type": "legal_representative",
    "application_channel": "in_person",
    "application_type": null,
    "inquiry_topic": "fee"
  },
  "fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": {
      "accepted_values": [
        "emergency"
      ]
    },
    "inquiry_topic": null
  },
  "intent": "passport_guidance",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 06. 배달:주문 변경 / unavailable_preference

- 후보 ID: `ai-coverage-v1-delivery-change-unavailable-preference`
- 기준 의무: `field_present` / `unavailable_preference`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “변경이 어렵다면 상담원에게 연결해 주세요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_order_change",
  "current_fields": {
    "change_type": "contact",
    "order_number": "별빛아파트 301호",
    "requested_change": "연락처를 010-1234-5678로 변경",
    "unavailable_preference": null
  },
  "fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": {
      "accepted_values": [
        "agent_handoff"
      ]
    }
  },
  "intent": "delivery_order_change",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 07. 배달:배달 지연 문의 / delay_detail

- 후보 ID: `ai-coverage-v1-delivery-delay-delay-detail`
- 기준 의무: `field_present` / `delay_detail`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “주문한 지 한 시간이 지났어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_delay_inquiry",
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": "agent_handoff",
    "inquiry_goal": "delay_reason",
    "order_number": "별빛아파트 302호"
  },
  "fields": {
    "delay_detail": {
      "accepted_values": [
        "1시간 지연"
      ]
    },
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": null
  },
  "intent": "delivery_delay_inquiry",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 08. 배달:배달 지연 문의 / delay_resolution

- 후보 ID: `ai-coverage-v1-delivery-delay-delay-resolution`
- 기준 의무: `field_present` / `delay_resolution`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “계속 늦어지면 상담원에게 연결해 주세요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_delay_inquiry",
  "current_fields": {
    "delay_detail": "40분 지연",
    "delay_resolution": null,
    "inquiry_goal": "delivery_location",
    "order_number": "별빛아파트 302호"
  },
  "fields": {
    "delay_detail": null,
    "delay_resolution": {
      "accepted_values": [
        "agent_handoff"
      ]
    },
    "inquiry_goal": null,
    "order_number": null
  },
  "intent": "delivery_delay_inquiry",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 09. 배달:환불/재배달 문의 / evidence_status

- 후보 ID: `ai-coverage-v1-delivery-refund-evidence-status`
- 기준 의무: `field_present` / `evidence_status`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “사진을 찍어 두었습니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_refund_redelivery",
  "current_fields": {
    "evidence_status": null,
    "issue_detail": "포장 파손",
    "issue_type": "damaged_or_quality",
    "order_number": "20260927-301",
    "resolution_preference": "agent_review"
  },
  "fields": {
    "evidence_status": {
      "accepted_values": [
        "available"
      ]
    },
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "intent": "delivery_refund_redelivery",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 10. 배달:환불/재배달 문의 / order_number

- 후보 ID: `ai-coverage-v1-delivery-refund-order-number`
- 기준 의무: `field_present` / `order_number`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “주문번호는 20260927-301입니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_refund_redelivery",
  "current_fields": {
    "evidence_status": "unavailable",
    "issue_detail": "사이드 메뉴 누락",
    "issue_type": "missing_item",
    "order_number": null,
    "resolution_preference": "redelivery"
  },
  "fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": {
      "accepted_values": [
        "20260927-301"
      ]
    },
    "resolution_preference": null
  },
  "intent": "delivery_refund_redelivery",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 11. 배달:환불/재배달 문의 / resolution_preference

- 후보 ID: `ai-coverage-v1-delivery-refund-resolution-preference`
- 기준 의무: `field_present` / `resolution_preference`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “상담원이 확인해 주셨으면 합니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_refund_redelivery",
  "current_fields": {
    "evidence_status": "available",
    "issue_detail": "배달 완료 표시지만 받지 못함",
    "issue_type": "not_received",
    "order_number": "20260927-301",
    "resolution_preference": null
  },
  "fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": {
      "accepted_values": [
        "agent_review"
      ]
    }
  },
  "intent": "delivery_refund_redelivery",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 12. 예약:미용실 예약 / selected_time

- 후보 ID: `ai-coverage-v1-reservation-hair-salon-selected-time`
- 기준 의무: `field_present` / `selected_time`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “가능하다고 하신 시간 중 오후 3시로 예약해 주세요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "reservation_unavailable",
  "current_fields": {},
  "fields": {
    "date": null,
    "designer": null,
    "selected_time": {
      "accepted_values": [
        "오후 3시"
      ]
    },
    "service_type": null,
    "time": null,
    "user_name": null
  },
  "intent": "reservation",
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "tags": [
    "single_field"
  ],
  "user_action": "select_alternative_time"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 13. 예약:병원 예약 / selected_time

- 후보 ID: `ai-coverage-v1-reservation-hospital-selected-time`
- 기준 의무: `field_present` / `selected_time`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “안내해 주신 진료 시간 중 오후 3시로 예약할게요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "reservation_unavailable",
  "current_fields": {},
  "fields": {
    "date": null,
    "department": null,
    "selected_time": {
      "accepted_values": [
        "오후 3시"
      ]
    },
    "time": null,
    "user_name": null
  },
  "intent": "reservation",
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "tags": [
    "single_field"
  ],
  "user_action": "select_alternative_time"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 14. 예약:식당 예약 / selected_time

- 후보 ID: `ai-coverage-v1-reservation-restaurant-selected-time`
- 기준 의무: `field_present` / `selected_time`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “제시해 주신 자리 시간 중 오후 3시로 할게요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "reservation_unavailable",
  "current_fields": {},
  "fields": {
    "date": null,
    "party_size": null,
    "selected_time": {
      "accepted_values": [
        "오후 3시"
      ]
    },
    "time": null,
    "user_name": null
  },
  "intent": "reservation",
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "tags": [
    "single_field"
  ],
  "user_action": "select_alternative_time"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 15. 예약:스터디룸 예약 / selected_time

- 후보 ID: `ai-coverage-v1-reservation-study-room-selected-time`
- 기준 의무: `field_present` / `selected_time`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “안내된 시간 중 오후 3시를 선택하겠습니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "reservation_unavailable",
  "current_fields": {},
  "fields": {
    "date": null,
    "duration": null,
    "party_size": null,
    "selected_time": {
      "accepted_values": [
        "오후 3시"
      ]
    },
    "start_time": null,
    "user_name": null
  },
  "intent": "reservation",
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "tags": [
    "single_field"
  ],
  "user_action": "select_alternative_time"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 16. 고객센터:인터넷/통화 문제 문의 / occurred_at

- 후보 ID: `ai-coverage-v1-support-network-occurred-at`
- 기준 의무: `field_present` / `occurred_at`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “오늘 아침부터 발생했어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_network_issue",
  "current_fields": {
    "next_action": "agent_handoff",
    "occurred_at": null,
    "scope": "all_locations",
    "service_type": "mobile_data",
    "symptom": "연결 끊김",
    "troubleshooting_done": "공유기 재부팅"
  },
  "fields": {
    "next_action": null,
    "occurred_at": {
      "accepted_values": [
        "오늘 아침"
      ]
    },
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "intent": "network_call_issue",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 17. 고객센터:인터넷/통화 문제 문의 / scope

- 후보 ID: `ai-coverage-v1-support-network-scope`
- 기준 의무: `field_present` / `scope`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “장소를 가리지 않고 어디서나 그래요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_network_issue",
  "current_fields": {
    "next_action": "guided_diagnosis",
    "occurred_at": "어제",
    "scope": null,
    "service_type": "voice_call",
    "symptom": "연결 끊김",
    "troubleshooting_done": "공유기 재부팅"
  },
  "fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": {
      "accepted_values": [
        "all_locations"
      ]
    },
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "intent": "network_call_issue",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 18. 고객센터:인터넷/통화 문제 문의 / service_type

- 후보 ID: `ai-coverage-v1-support-network-service-type`
- 기준 의무: `field_present` / `service_type`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “모바일 데이터 문제예요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_network_issue",
  "current_fields": {
    "next_action": "remote_check",
    "occurred_at": "어제",
    "scope": "single_device",
    "service_type": null,
    "symptom": "연결 끊김",
    "troubleshooting_done": "공유기 재부팅"
  },
  "fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": {
      "accepted_values": [
        "mobile_data"
      ]
    },
    "symptom": null,
    "troubleshooting_done": null
  },
  "intent": "network_call_issue",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 19. 고객센터:인터넷/통화 문제 문의 / troubleshooting_done

- 후보 ID: `ai-coverage-v1-support-network-troubleshooting-done`
- 기준 의무: `field_present` / `troubleshooting_done`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “휴대폰을 재부팅해 봤어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_network_issue",
  "current_fields": {
    "next_action": "service_request",
    "occurred_at": "어제",
    "scope": "specific_location",
    "service_type": "wired_internet",
    "symptom": "연결 끊김",
    "troubleshooting_done": null
  },
  "fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": {
      "accepted_values": [
        "휴대폰 재부팅"
      ]
    }
  },
  "intent": "network_call_issue",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 20. 고객센터:요금/약정 상담 / consent_scope

- 후보 ID: `ai-coverage-v1-support-plan-consent-scope`
- 기준 의무: `field_present` / `consent_scope`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “본인 인증 후 가입 정보 조회에 동의합니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_plan_contract",
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": "청구 내역 확인",
    "current_service": "0청년 요금제",
    "inquiry_type": "billing"
  },
  "fields": {
    "consent_scope": {
      "accepted_values": [
        "authenticated_lookup"
      ]
    },
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "intent": "plan_contract_consultation",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 21. 고객센터:a/s 접수 / model_name

- 후보 ID: `ai-coverage-v1-support-service-model-name`
- 기준 의무: `field_present` / `model_name`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “모델명은 갤럭시 S25입니다.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_service_request",
  "current_fields": {
    "model_name": null,
    "occurred_at": "어제 저녁",
    "preferred_schedule": "내일 오후 2시",
    "product_type": "휴대폰",
    "safety_status": "no_safety_issue",
    "service_channel": "agent_review",
    "symptom": "화면이 켜지지 않음"
  },
  "fields": {
    "model_name": {
      "accepted_values": [
        "갤럭시 S25"
      ]
    },
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "intent": "service_request",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 22. 고객센터:a/s 접수 / occurred_at

- 후보 ID: `ai-coverage-v1-support-service-occurred-at`
- 기준 의무: `field_present` / `occurred_at`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “오늘 아침부터 그랬어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_service_request",
  "current_fields": {
    "model_name": "갤럭시 S25",
    "occurred_at": null,
    "preferred_schedule": "내일 오후 2시",
    "product_type": "휴대폰",
    "safety_status": "no_safety_issue",
    "service_channel": "onsite",
    "symptom": "화면이 켜지지 않음"
  },
  "fields": {
    "model_name": null,
    "occurred_at": {
      "accepted_values": [
        "오늘 아침"
      ]
    },
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "intent": "service_request",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 23. 고객센터:a/s 접수 / safety_status

- 후보 ID: `ai-coverage-v1-support-service-safety-status`
- 기준 의무: `field_present` / `safety_status`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “연기나 발열 같은 안전 이상은 없어요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_service_request",
  "current_fields": {
    "model_name": "갤럭시 S25",
    "occurred_at": "어제 저녁",
    "preferred_schedule": "내일 오후 2시",
    "product_type": "휴대폰",
    "safety_status": null,
    "service_channel": "parcel",
    "symptom": "화면이 켜지지 않음"
  },
  "fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": {
      "accepted_values": [
        "no_safety_issue"
      ]
    },
    "service_channel": null,
    "symptom": null
  },
  "intent": "service_request",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 24. 고객센터:a/s 접수 / service_channel

- 후보 ID: `ai-coverage-v1-support-service-service-channel`
- 기준 의무: `field_present` / `service_channel`
- 기준 시점 미충족: `true`
- 라이브 의미 계약 통과: `true`
- AI 후보 발화: “상담원 검토로 접수해 주세요.”
- 제안 입력·정답:

```json
{
  "change_field": null,
  "conversation_state": "collecting_service_request",
  "current_fields": {
    "model_name": "갤럭시 S25",
    "occurred_at": "어제 저녁",
    "preferred_schedule": "내일 오후 2시",
    "product_type": "휴대폰",
    "safety_status": "no_safety_issue",
    "service_channel": null,
    "symptom": "화면이 켜지지 않음"
  },
  "fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": {
      "accepted_values": [
        "agent_review"
      ]
    },
    "symptom": null
  },
  "intent": "service_request",
  "offered_alternative_times": [],
  "tags": [
    "single_field"
  ],
  "user_action": "provide_details"
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}
