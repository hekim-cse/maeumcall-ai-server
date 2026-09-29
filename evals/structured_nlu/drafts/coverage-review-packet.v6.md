# 구조화 NLU 변경 필드 커버리지 후보 검토 작업지 V6

> 38개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에 판단을 기록합니다.

- 선행 V5 artifact SHA-256: `4865192fcd1f662ffca533035f99f9f9b0ae6a2cb675b62278ab0358385434c5`
- 기준 진단 case 수: `105`
- 기준 충족/미충족: `776` / `786`
- 투영 증가: `124`
- 투영 충족/미충족: `900` / `662`
- 자동 승격 허용: `false`

## 01. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v6-city-certificate-document-type`
- AI 후보 발화: “등본이 아니라 주민등록 초본을 발급하려고 합니다.”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": "register_copy",
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "labels": {
    "change_field": "document_type",
    "fields": {
      "applicant_relation": null,
      "document_type": {
        "accepted_values": [
          "individual_extract"
        ]
      },
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "change_detail->document_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 02. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v6-city-certificate-relation`
- AI 후보 발화: “본인 신청이 아니라 대리인 신청입니다.”

```json
{
  "current_fields": {
    "applicant_relation": "self",
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "labels": {
    "change_field": "applicant_relation",
    "fields": {
      "applicant_relation": {
        "accepted_values": [
          "representative"
        ]
      },
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "change_detail->applicant_relation"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 03. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v6-city-certificate-topic`
- AI 후보 발화: “수령 방법이 아니라 발급 수수료가 궁금합니다.”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": "delivery",
    "issuance_channel": null
  },
  "labels": {
    "change_field": "inquiry_topic",
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": {
        "accepted_values": [
          "fee"
        ]
      },
      "issuance_channel": null
    },
    "intent": "resident_certificate_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "change_detail->inquiry_topic"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 04. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v6-city-passport-applicant-type`
- AI 후보 발화: “성인 본인 신청이 아니라 미성년자 신청 건입니다.”

```json
{
  "current_fields": {
    "applicant_type": "adult_self",
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": "applicant_type",
    "fields": {
      "applicant_type": {
        "accepted_values": [
          "minor"
        ]
      },
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": null
    },
    "intent": "passport_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:여권 발급 문의",
      "value": "change_detail->applicant_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 05. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v6-city-passport-application-type`
- AI 후보 발화: “최초 발급이 아니라 재발급 문의입니다.”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": "first_issue",
    "inquiry_topic": null
  },
  "labels": {
    "change_field": "application_type",
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": {
        "accepted_values": [
          "reissue"
        ]
      },
      "inquiry_topic": null
    },
    "intent": "passport_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:여권 발급 문의",
      "value": "change_detail->application_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type->existing_value_replaced"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "시청:여권 발급 문의",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "scenario_key": "시청:여권 발급 문의",
      "value": "collecting_passport_inquiry->change_detail"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 06. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v6-city-passport-channel`
- AI 후보 발화: “정부24 온라인 신청 대신 직접 방문 신청으로 바꾸겠습니다.”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": "government24",
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": "application_channel",
    "fields": {
      "applicant_type": null,
      "application_channel": {
        "accepted_values": [
          "in_person"
        ]
      },
      "application_type": null,
      "inquiry_topic": null
    },
    "intent": "passport_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:여권 발급 문의",
      "value": "change_detail->application_channel"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 07. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v6-city-passport-topic`
- AI 후보 발화: “처리 기간이 아니라 필요한 서류를 알고 싶어요.”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": "processing_time"
  },
  "labels": {
    "change_field": "inquiry_topic",
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": {
        "accepted_values": [
          "documents"
        ]
      }
    },
    "intent": "passport_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:여권 발급 문의",
      "value": "change_detail->inquiry_topic"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 08. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v6-city-waste-item`
- AI 후보 발화: “버릴 물건을 소파에서 장롱으로 정정할게요.”

```json
{
  "current_fields": {
    "item_name": "소파",
    "quantity": null,
    "region": null,
    "request_topic": null
  },
  "labels": {
    "change_field": "item_name",
    "fields": {
      "item_name": {
        "accepted_values": [
          "장롱"
        ]
      },
      "quantity": null,
      "region": null,
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "change_detail->item_name"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "item_name"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "item_name->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "item_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 09. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v6-city-waste-region`
- AI 후보 발화: “배출 지역은 서울 독산동이 아니라 인천 구월동입니다.”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": "서울 독산동",
    "request_topic": null
  },
  "labels": {
    "change_field": "region",
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": {
        "accepted_values": [
          "인천 구월동"
        ]
      },
      "request_topic": null
    },
    "intent": "bulky_waste_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "change_detail->region"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "region"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "region->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "region"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 10. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v6-city-waste-topic`
- AI 후보 발화: “신고 방법이 아니라 배출 수수료를 문의하려고 합니다.”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": "application"
  },
  "labels": {
    "change_field": "request_topic",
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": {
        "accepted_values": [
          "fee"
        ]
      }
    },
    "intent": "bulky_waste_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "change_detail->request_topic"
    },
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 11. 배달:주문 변경

- 후보 ID: `ai-coverage-v6-delivery-change-order-number`
- AI 후보 발화: “변경할 주문번호는 B-201이 아니라 B-202예요.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": "B-201",
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": "order_number",
    "fields": {
      "change_type": null,
      "order_number": {
        "accepted_values": [
          "B-202"
        ]
      },
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:주문 변경",
      "value": "change_detail->order_number"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "order_number"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:주문 변경",
      "value": "order_number->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "order_number"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 12. 배달:주문 변경

- 후보 ID: `ai-coverage-v6-delivery-change-request`
- AI 후보 발화: “변경 내용은 맵기 보통이 아니라 순한맛입니다.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": "맵기 보통",
    "unavailable_preference": null
  },
  "labels": {
    "change_field": "requested_change",
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": {
        "accepted_values": [
          "맵기 순한맛"
        ]
      },
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:주문 변경",
      "value": "change_detail->requested_change"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "requested_change"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:주문 변경",
      "value": "requested_change->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "requested_change"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 13. 배달:주문 변경

- 후보 ID: `ai-coverage-v6-delivery-change-type`
- AI 후보 발화: “메뉴 옵션이 아니라 배달 주소를 변경하려는 겁니다.”

```json
{
  "current_fields": {
    "change_type": "menu_option",
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": "change_type",
    "fields": {
      "change_type": {
        "accepted_values": [
          "delivery_address"
        ]
      },
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:주문 변경",
      "value": "change_detail->change_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "change_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:주문 변경",
      "value": "change_type->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:주문 변경",
      "value": "change_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 14. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v6-delivery-delay-detail`
- AI 후보 발화: “30분 늦은 게 아니라 벌써 한 시간째 지연 중입니다.”

```json
{
  "current_fields": {
    "delay_detail": "30분 지연",
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": null
  },
  "labels": {
    "change_field": "delay_detail",
    "fields": {
      "delay_detail": {
        "accepted_values": [
          "한 시간 지연"
        ]
      },
      "delay_resolution": null,
      "inquiry_goal": null,
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:배달 지연 문의",
      "value": "change_detail->delay_detail"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_detail"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_detail->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_detail"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 15. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v6-delivery-delay-goal`
- AI 후보 발화: “예상 도착 시간보다 지연 이유를 확인해 주세요.”

```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": null,
    "inquiry_goal": "estimated_arrival",
    "order_number": null
  },
  "labels": {
    "change_field": "inquiry_goal",
    "fields": {
      "delay_detail": null,
      "delay_resolution": null,
      "inquiry_goal": {
        "accepted_values": [
          "delay_reason"
        ]
      },
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:배달 지연 문의",
      "value": "change_detail->inquiry_goal"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 16. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v6-delivery-delay-order-number`
- AI 후보 발화: “주문번호는 A-101이 아니라 A-102입니다.”

```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": "A-101"
  },
  "labels": {
    "change_field": "order_number",
    "fields": {
      "delay_detail": null,
      "delay_resolution": null,
      "inquiry_goal": null,
      "order_number": {
        "accepted_values": [
          "A-102"
        ]
      }
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:배달 지연 문의",
      "value": "change_detail->order_number"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "order_number"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:배달 지연 문의",
      "value": "order_number->existing_value_replaced"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "배달:배달 지연 문의",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "scenario_key": "배달:배달 지연 문의",
      "value": "collecting_delay_inquiry->change_detail"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "order_number"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 17. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v6-delivery-delay-resolution`
- AI 후보 발화: “더 기다리지 않고 취소 가능한지 확인하고 싶습니다.”

```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": "wait",
    "inquiry_goal": null,
    "order_number": null
  },
  "labels": {
    "change_field": "delay_resolution",
    "fields": {
      "delay_detail": null,
      "delay_resolution": {
        "accepted_values": [
          "check_cancellation"
        ]
      },
      "inquiry_goal": null,
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:배달 지연 문의",
      "value": "change_detail->delay_resolution"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 18. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v6-delivery-refund-detail`
- AI 후보 발화: “상세 내용은 용기 파손이 아니라 주문과 다른 음료가 온 것입니다.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": "용기가 찌그러짐",
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": "issue_detail",
    "fields": {
      "evidence_status": null,
      "issue_detail": {
        "accepted_values": [
          "주문과 다른 음료 도착"
        ]
      },
      "issue_type": null,
      "order_number": null,
      "resolution_preference": null
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "change_detail->issue_detail"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_detail"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_detail->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_detail"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 19. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v6-delivery-refund-evidence`
- AI 후보 발화: “사진이 있다고 했는데 확인해 보니 증빙 자료가 없습니다.”

```json
{
  "current_fields": {
    "evidence_status": "available",
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": "evidence_status",
    "fields": {
      "evidence_status": {
        "accepted_values": [
          "unavailable"
        ]
      },
      "issue_detail": null,
      "issue_type": null,
      "order_number": null,
      "resolution_preference": null
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "change_detail->evidence_status"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "evidence_status"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "evidence_status->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "evidence_status"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 20. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v6-delivery-refund-issue-type`
- AI 후보 발화: “음식이 상한 문제가 아니라 다른 메뉴가 온 문제입니다.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": "damaged_or_quality",
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": "issue_type",
    "fields": {
      "evidence_status": null,
      "issue_detail": null,
      "issue_type": {
        "accepted_values": [
          "wrong_item"
        ]
      },
      "order_number": null,
      "resolution_preference": null
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "change_detail->issue_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 21. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v6-delivery-refund-order-number`
- AI 후보 발화: “문제 주문은 C-301이 아니라 C-302입니다.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": "C-301",
    "resolution_preference": null
  },
  "labels": {
    "change_field": "order_number",
    "fields": {
      "evidence_status": null,
      "issue_detail": null,
      "issue_type": null,
      "order_number": {
        "accepted_values": [
          "C-302"
        ]
      },
      "resolution_preference": null
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "change_detail->order_number"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "order_number"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "order_number->existing_value_replaced"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "collecting_refund_redelivery->change_detail"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "order_number"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 22. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v6-delivery-refund-resolution`
- AI 후보 발화: “환불 대신 같은 메뉴를 다시 배달해 주세요.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": "refund"
  },
  "labels": {
    "change_field": "resolution_preference",
    "fields": {
      "evidence_status": null,
      "issue_detail": null,
      "issue_type": null,
      "order_number": null,
      "resolution_preference": {
        "accepted_values": [
          "redelivery"
        ]
      }
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "change_detail->resolution_preference"
    },
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 23. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-next-action`
- AI 후보 발화: “안내에 따라 진단하는 대신 상담원 연결을 원합니다.”

```json
{
  "current_fields": {
    "next_action": "guided_diagnosis",
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": "next_action",
    "fields": {
      "next_action": {
        "accepted_values": [
          "agent_handoff"
        ]
      },
      "occurred_at": null,
      "scope": null,
      "service_type": null,
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->next_action"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 24. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-occurred-at`
- AI 후보 발화: “발생 시점은 어제가 아니라 오늘 오전입니다.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": "어제",
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": "occurred_at",
    "fields": {
      "next_action": null,
      "occurred_at": {
        "accepted_values": [
          "오늘 오전"
        ]
      },
      "scope": null,
      "service_type": null,
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->occurred_at"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "occurred_at"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "occurred_at->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "occurred_at"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 25. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-scope`
- AI 후보 발화: “한 대만 그런 줄 알았는데 여러 기기에서 발생합니다.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": "single_device",
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": "scope",
    "fields": {
      "next_action": null,
      "occurred_at": null,
      "scope": {
        "accepted_values": [
          "multiple_devices"
        ]
      },
      "service_type": null,
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->scope"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 26. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-service-type`
- AI 후보 발화: “모바일 데이터 문제가 아니라 와이파이 문제예요.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": "mobile_data",
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": "service_type",
    "fields": {
      "next_action": null,
      "occurred_at": null,
      "scope": null,
      "service_type": {
        "accepted_values": [
          "wifi"
        ]
      },
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->service_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type->existing_value_replaced"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "collecting_network_issue->change_detail"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 27. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-symptom`
- AI 후보 발화: “속도가 느린 게 아니라 연결이 계속 끊기는 증상입니다.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": "속도 저하",
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": "symptom",
    "fields": {
      "next_action": null,
      "occurred_at": null,
      "scope": null,
      "service_type": null,
      "symptom": {
        "accepted_values": [
          "연결 끊김"
        ]
      },
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->symptom"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "symptom"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "symptom->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "symptom"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 28. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v6-support-network-troubleshooting`
- AI 후보 발화: “시도한 조치는 공유기 재부팅이 아니라 비행기 모드 전환입니다.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": "공유기 재부팅"
  },
  "labels": {
    "change_field": "troubleshooting_done",
    "fields": {
      "next_action": null,
      "occurred_at": null,
      "scope": null,
      "service_type": null,
      "symptom": null,
      "troubleshooting_done": {
        "accepted_values": [
          "비행기 모드 전환"
        ]
      }
    },
    "intent": "network_call_issue",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "change_detail->troubleshooting_done"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "troubleshooting_done"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "troubleshooting_done->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "troubleshooting_done"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 29. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v6-support-plan-current-service`
- AI 후보 발화: “현재 요금제는 5G 프리미엄이 아니라 LTE 베이직입니다.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": "5G 프리미엄",
    "inquiry_type": null
  },
  "labels": {
    "change_field": "current_service",
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": {
        "accepted_values": [
          "LTE 베이직"
        ]
      },
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "change_detail->current_service"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "current_service"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "current_service->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "current_service"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 30. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v6-support-plan-goal`
- AI 후보 발화: “상담 목표를 요금 절감에서 데이터 제공량 확대로 바꾸겠습니다.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": "요금 절감",
    "current_service": null,
    "inquiry_type": null
  },
  "labels": {
    "change_field": "consultation_goal",
    "fields": {
      "consent_scope": null,
      "consultation_goal": {
        "accepted_values": [
          "데이터 확대"
        ]
      },
      "current_service": null,
      "inquiry_type": null
    },
    "intent": "plan_contract_consultation",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "change_detail->consultation_goal"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consultation_goal"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consultation_goal->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consultation_goal"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 31. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v6-support-plan-inquiry-type`
- AI 후보 발화: “청구 문의가 아니라 할인 상담으로 변경해 주세요.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": "billing"
  },
  "labels": {
    "change_field": "inquiry_type",
    "fields": {
      "consent_scope": null,
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": {
        "accepted_values": [
          "discount"
        ]
      }
    },
    "intent": "plan_contract_consultation",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "change_detail->inquiry_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 32. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-channel`
- AI 후보 발화: “택배 접수 대신 서비스센터 방문으로 변경해 주세요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": "parcel",
    "symptom": null
  },
  "labels": {
    "change_field": "service_channel",
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": null,
      "product_type": null,
      "safety_status": null,
      "service_channel": {
        "accepted_values": [
          "visit"
        ]
      },
      "symptom": null
    },
    "intent": "service_request",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->service_channel"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 33. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-model-name`
- AI 후보 발화: “모델명을 갤럭시 S24에서 아이폰 16으로 바꿔 주세요.”

```json
{
  "current_fields": {
    "model_name": "갤럭시 S24",
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": "model_name",
    "fields": {
      "model_name": {
        "accepted_values": [
          "아이폰 16"
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
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->model_name"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "model_name"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "model_name->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "model_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 34. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-occurred-at`
- AI 후보 발화: “고장이 난 시점은 어제가 아니라 오늘 아침이에요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": "어제",
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": "occurred_at",
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
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->occurred_at"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "occurred_at"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "occurred_at->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "occurred_at"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 35. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-product-type`
- AI 후보 발화: “제품 종류를 휴대폰이 아니라 노트북으로 정정할게요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": "휴대폰",
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": "product_type",
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": null,
      "product_type": {
        "accepted_values": [
          "노트북"
        ]
      },
      "safety_status": null,
      "service_channel": null,
      "symptom": null
    },
    "intent": "service_request",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->product_type"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "product_type"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "product_type->existing_value_replaced"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "고객센터:a/s 접수",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "scenario_key": "고객센터:a/s 접수",
      "value": "collecting_service_request->change_detail"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "product_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 36. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-safety-status`
- AI 후보 발화: “안전 문제는 없다고 했는데 배터리가 부풀어 올라 위험한 상태로 정정합니다.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": "no_safety_issue",
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": "safety_status",
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": null,
      "product_type": null,
      "safety_status": {
        "accepted_values": [
          "safety_issue"
        ]
      },
      "service_channel": null,
      "symptom": null
    },
    "intent": "service_request",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->safety_status"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction",
    "safety"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 37. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-schedule`
- AI 후보 발화: “희망 일정을 월요일 오전에서 화요일 오후로 바꿀게요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": "월요일 오전",
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": "preferred_schedule",
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": {
        "accepted_values": [
          "화요일 오후"
        ]
      },
      "product_type": null,
      "safety_status": null,
      "service_channel": null,
      "symptom": null
    },
    "intent": "service_request",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->preferred_schedule"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "preferred_schedule"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "preferred_schedule->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "preferred_schedule"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 38. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v6-support-service-symptom`
- AI 후보 발화: “증상은 화면 파손이 아니라 전원이 켜지지 않는 문제입니다.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": "화면 파손"
  },
  "labels": {
    "change_field": "symptom",
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": null,
      "product_type": null,
      "safety_status": null,
      "service_channel": null,
      "symptom": {
        "accepted_values": [
          "전원 불량"
        ]
      }
    },
    "intent": "service_request",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:a/s 접수",
      "value": "change_detail->symptom"
    },
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "symptom"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:a/s 접수",
      "value": "symptom->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "change_field",
      "scenario_key": "고객센터:a/s 접수",
      "value": "symptom"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
