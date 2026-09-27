# 구조화 NLU 출력 옵션 커버리지 후보 검토 작업지 V5

> 27개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에 판단을 기록합니다.

- 선행 V4 artifact SHA-256: `ee19aa48f772c0bd16d8819bf90c0c06c5e4a9426bd4b9d09f74dfe380ee7565`
- 기준 진단 case 수: `78`
- 기준 충족/미충족: `713` / `849`
- 투영 증가: `63`
- 투영 충족/미충족: `776` / `786`
- 자동 승격 허용: `false`

## 01. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v5-city-certificate-extract-representative-documents-in-person`
- AI 후보 발화: “대리인이 주민등록 초본을 방문 발급할 때 필요한 서류가 무엇인가요?”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_relation": {
        "accepted_values": [
          "representative"
        ]
      },
      "document_type": {
        "accepted_values": [
          "individual_extract"
        ]
      },
      "inquiry_topic": {
        "accepted_values": [
          "documents"
        ]
      },
      "issuance_channel": {
        "accepted_values": [
          "in_person"
        ]
      }
    },
    "intent": "resident_certificate_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "collecting_certificate_inquiry->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=representative"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type=individual_extract"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=documents"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=in_person"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=representative"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "document_type=individual_extract"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=documents"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=in_person"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 02. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v5-city-certificate-fee`
- AI 후보 발화: “주민등록 등본 발급 수수료가 얼마인가요?”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "labels": {
    "change_field": null,
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
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=fee"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=fee"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 03. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v5-city-certificate-household-kiosk-eligibility`
- AI 후보 발화: “같은 세대원의 등본을 무인발급기에서 뗄 수 있는지 궁금합니다.”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_relation": {
        "accepted_values": [
          "same_household"
        ]
      },
      "document_type": null,
      "inquiry_topic": {
        "accepted_values": [
          "eligibility"
        ]
      },
      "issuance_channel": {
        "accepted_values": [
          "kiosk"
        ]
      }
    },
    "intent": "resident_certificate_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=same_household"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=eligibility"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=kiosk"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "applicant_relation=same_household"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "inquiry_topic=eligibility"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel=kiosk"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 04. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v5-city-passport-first-legal-documents-in-person`
- AI 후보 발화: “아이의 첫 여권을 법정대리인인 제가 방문 신청할 때 필요한 서류가 무엇인가요?”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": {
        "accepted_values": [
          "legal_representative"
        ]
      },
      "application_channel": {
        "accepted_values": [
          "in_person"
        ]
      },
      "application_type": {
        "accepted_values": [
          "first_issue"
        ]
      },
      "inquiry_topic": {
        "accepted_values": [
          "documents"
        ]
      }
    },
    "intent": "passport_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "시청:여권 발급 문의",
      "value": "collecting_passport_inquiry->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=legal_representative"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=in_person"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=first_issue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=documents"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "시청:여권 발급 문의",
      "value": "multi_field"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=legal_representative"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=in_person"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=first_issue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=documents"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 05. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v5-city-passport-office`
- AI 후보 발화: “여권을 신청할 수 있는 담당 창구가 어디인가요?”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": {
        "accepted_values": [
          "office"
        ]
      }
    },
    "intent": "passport_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=office"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=office"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 06. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v5-city-passport-online-eligibility`
- AI 후보 발화: “온라인으로 여권을 신청할 수 있는 대상인지 알고 싶어요.”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": null,
      "application_channel": null,
      "application_type": null,
      "inquiry_topic": {
        "accepted_values": [
          "online_eligibility"
        ]
      }
    },
    "intent": "passport_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=online_eligibility"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=online_eligibility"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 07. 시청:여권 발급 문의

- 후보 ID: `ai-coverage-v5-city-passport-reissue-minor-fee-overseas`
- AI 후보 발화: “미성년자 여권을 해외 공관에서 재발급할 때 수수료가 궁금합니다.”

```json
{
  "current_fields": {
    "applicant_type": null,
    "application_channel": null,
    "application_type": null,
    "inquiry_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "applicant_type": {
        "accepted_values": [
          "minor"
        ]
      },
      "application_channel": {
        "accepted_values": [
          "overseas_mission"
        ]
      },
      "application_type": {
        "accepted_values": [
          "reissue"
        ]
      },
      "inquiry_topic": {
        "accepted_values": [
          "fee"
        ]
      }
    },
    "intent": "passport_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=minor"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=overseas_mission"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=reissue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=fee"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "applicant_type=minor"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_channel=overseas_mission"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "application_type=reissue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:여권 발급 문의",
      "value": "inquiry_topic=fee"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 08. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v5-city-waste-collection`
- AI 후보 발화: “신고한 소파가 수거됐는지 확인하고 싶습니다.”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": {
        "accepted_values": [
          "collection_status"
        ]
      }
    },
    "intent": "bulky_waste_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "collecting_bulky_waste->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=collection_status"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=collection_status"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 09. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v5-city-waste-fee`
- AI 후보 발화: “장롱을 버릴 때 수수료가 얼마인지 알려 주세요.”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": null
  },
  "labels": {
    "change_field": null,
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
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=fee"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=fee"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 10. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v5-city-waste-place-schedule`
- AI 후보 발화: “대형폐기물을 어디에 언제 내놓아야 하나요?”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": null,
    "region": null,
    "request_topic": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "item_name": null,
      "quantity": null,
      "region": null,
      "request_topic": {
        "accepted_values": [
          "place_and_schedule"
        ]
      }
    },
    "intent": "bulky_waste_guidance",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=place_and_schedule"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "request_topic=place_and_schedule"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 11. 배달:주문 변경

- 후보 ID: `ai-coverage-v5-delivery-change-address-keep`
- AI 후보 발화: “배달 주소를 변경해 주세요. 안 되면 주문은 그대로 둘게요.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": {
        "accepted_values": [
          "delivery_address"
        ]
      },
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": {
        "accepted_values": [
          "keep_order"
        ]
      }
    },
    "intent": "delivery_order_change",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=delivery_address"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=keep_order"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=delivery_address"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=keep_order"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 12. 배달:주문 변경

- 후보 ID: `ai-coverage-v5-delivery-change-contact-cancel`
- AI 후보 발화: “연락처를 바꾸고 싶어요. 변경이 안 되면 취소 가능한지 확인해 주세요.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": {
        "accepted_values": [
          "contact"
        ]
      },
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": {
        "accepted_values": [
          "check_cancellation"
        ]
      }
    },
    "intent": "delivery_order_change",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "배달:주문 변경",
      "value": "collecting_order_change->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=contact"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=check_cancellation"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=contact"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference=check_cancellation"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 13. 배달:주문 변경

- 후보 ID: `ai-coverage-v5-delivery-change-menu-option`
- AI 후보 발화: “주문한 메뉴의 맵기 옵션을 바꾸고 싶습니다.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "change_type": {
        "accepted_values": [
          "menu_option"
        ]
      },
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": null
    },
    "intent": "delivery_order_change",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_option"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:주문 변경",
      "value": "change_type=menu_option"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 14. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v5-delivery-delay-location-wait`
- AI 후보 발화: “현재 배달 위치를 알려 주세요. 조금 더 기다리겠습니다.”

```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "delay_detail": null,
      "delay_resolution": {
        "accepted_values": [
          "wait"
        ]
      },
      "inquiry_goal": {
        "accepted_values": [
          "delivery_location"
        ]
      },
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=wait"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=delivery_location"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=wait"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=delivery_location"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 15. 배달:배달 지연 문의

- 후보 ID: `ai-coverage-v5-delivery-delay-reason-cancel`
- AI 후보 발화: “배달이 늦는 이유를 확인해 주시고 지금 취소 가능한지도 알려 주세요.”

```json
{
  "current_fields": {
    "delay_detail": null,
    "delay_resolution": null,
    "inquiry_goal": null,
    "order_number": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "delay_detail": null,
      "delay_resolution": {
        "accepted_values": [
          "check_cancellation"
        ]
      },
      "inquiry_goal": {
        "accepted_values": [
          "delay_reason"
        ]
      },
      "order_number": null
    },
    "intent": "delivery_delay_inquiry",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "배달:배달 지연 문의",
      "value": "collecting_delay_inquiry->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=check_cancellation"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=delay_reason"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "delay_resolution=check_cancellation"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:배달 지연 문의",
      "value": "inquiry_goal=delay_reason"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 16. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v5-delivery-refund-missing-unavailable-redelivery`
- AI 후보 발화: “음료가 빠졌는데 사진은 없습니다. 빠진 음료를 다시 보내 주세요.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "evidence_status": {
        "accepted_values": [
          "unavailable"
        ]
      },
      "issue_detail": null,
      "issue_type": {
        "accepted_values": [
          "missing_item"
        ]
      },
      "order_number": null,
      "resolution_preference": {
        "accepted_values": [
          "redelivery"
        ]
      }
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "collecting_refund_redelivery->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "evidence_status=unavailable"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=missing_item"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=redelivery"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "evidence_status=unavailable"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=missing_item"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=redelivery"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 17. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v5-delivery-refund-not-received-refund`
- AI 후보 발화: “배달 완료로 뜨지만 받지 못했습니다. 환불해 주세요.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "evidence_status": null,
      "issue_detail": null,
      "issue_type": {
        "accepted_values": [
          "not_received"
        ]
      },
      "order_number": null,
      "resolution_preference": {
        "accepted_values": [
          "refund"
        ]
      }
    },
    "intent": "delivery_refund_redelivery",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=not_received"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=refund"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=not_received"
    },
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "resolution_preference=refund"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 18. 배달:환불/재배달 문의

- 후보 ID: `ai-coverage-v5-delivery-refund-wrong-item`
- AI 후보 발화: “주문한 것과 다른 메뉴가 왔어요.”

```json
{
  "current_fields": {
    "evidence_status": null,
    "issue_detail": null,
    "issue_type": null,
    "order_number": null,
    "resolution_preference": null
  },
  "labels": {
    "change_field": null,
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
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=wrong_item"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "배달:환불/재배달 문의",
      "value": "issue_type=wrong_item"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 19. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v5-support-network-voice-multiple-agent`
- AI 후보 발화: “가족 휴대폰 여러 대에서 통화가 안 됩니다. 상담원에게 연결해 주세요.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "next_action": {
        "accepted_values": [
          "agent_handoff"
        ]
      },
      "occurred_at": null,
      "scope": {
        "accepted_values": [
          "multiple_devices"
        ]
      },
      "service_type": {
        "accepted_values": [
          "voice_call"
        ]
      },
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "collecting_network_issue->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=agent_handoff"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=multiple_devices"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=voice_call"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=agent_handoff"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=multiple_devices"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=voice_call"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 20. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v5-support-network-wifi-single-remote`
- AI 후보 발화: “제 노트북 한 대만 와이파이가 끊겨요. 원격으로 확인해 주세요.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "next_action": {
        "accepted_values": [
          "remote_check"
        ]
      },
      "occurred_at": null,
      "scope": {
        "accepted_values": [
          "single_device"
        ]
      },
      "service_type": {
        "accepted_values": [
          "wifi"
        ]
      },
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=remote_check"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=single_device"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wifi"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=remote_check"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=single_device"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wifi"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 21. 고객센터:인터넷/통화 문제 문의

- 후보 ID: `ai-coverage-v5-support-network-wired-location-service`
- AI 후보 발화: “거실에서만 유선 인터넷이 안 됩니다. 수리 접수를 원합니다.”

```json
{
  "current_fields": {
    "next_action": null,
    "occurred_at": null,
    "scope": null,
    "service_type": null,
    "symptom": null,
    "troubleshooting_done": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "next_action": {
        "accepted_values": [
          "service_request"
        ]
      },
      "occurred_at": null,
      "scope": {
        "accepted_values": [
          "specific_location"
        ]
      },
      "service_type": {
        "accepted_values": [
          "wired_internet"
        ]
      },
      "symptom": null,
      "troubleshooting_done": null
    },
    "intent": "network_call_issue",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=service_request"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=specific_location"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wired_internet"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "next_action=service_request"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "scope=specific_location"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:인터넷/통화 문제 문의",
      "value": "service_type=wired_internet"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 22. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v5-support-plan-billing-authenticated`
- AI 후보 발화: “본인 인증을 하고 이번 달 청구 금액을 조회해 주세요.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "consent_scope": {
        "accepted_values": [
          "authenticated_lookup"
        ]
      },
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": {
        "accepted_values": [
          "billing"
        ]
      }
    },
    "intent": "plan_contract_consultation",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "collecting_plan_contract->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=billing"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=billing"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 23. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v5-support-plan-contract-general`
- AI 후보 발화: “약정 만료 시점은 개인정보 조회 없이 일반적인 기준만 안내해 주세요.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "consent_scope": {
        "accepted_values": [
          "general_guidance"
        ]
      },
      "consultation_goal": null,
      "current_service": null,
      "inquiry_type": {
        "accepted_values": [
          "contract_expiry"
        ]
      }
    },
    "intent": "plan_contract_consultation",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consent_scope=general_guidance"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=contract_expiry"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consent_scope=general_guidance"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=contract_expiry"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 24. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v5-support-plan-discount`
- AI 후보 발화: “지금 받을 수 있는 요금 할인 제도가 궁금합니다.”

```json
{
  "current_fields": {
    "consent_scope": null,
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "labels": {
    "change_field": null,
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
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=discount"
    }
  ],
  "tags": [
    "single_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "inquiry_type=discount"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 25. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v5-support-service-parcel`
- AI 후보 발화: “휴대폰 화면이 깨졌습니다. 택배로 수리를 맡기고 싶어요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": null,
    "fields": {
      "model_name": null,
      "occurred_at": null,
      "preferred_schedule": null,
      "product_type": {
        "accepted_values": [
          "휴대폰"
        ]
      },
      "safety_status": null,
      "service_channel": {
        "accepted_values": [
          "parcel"
        ]
      },
      "symptom": {
        "accepted_values": [
          "화면 파손"
        ]
      }
    },
    "intent": "service_request",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=parcel"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=parcel"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 26. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v5-support-service-safety-onsite`
- AI 후보 발화: “휴대폰 배터리가 부풀어 올랐어요. 기사님이 현장에 와서 점검해 주세요.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": null,
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
      "service_channel": {
        "accepted_values": [
          "onsite"
        ]
      },
      "symptom": {
        "accepted_values": [
          "배터리 부풀음"
        ]
      }
    },
    "intent": "service_request",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "current_fields_context",
      "scenario_key": "고객센터:a/s 접수",
      "value": "collecting_service_request->empty"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status=safety_issue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=onsite"
    }
  ],
  "tags": [
    "multi_field",
    "safety"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "safety_status=safety_issue"
    },
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=onsite"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 27. 고객센터:a/s 접수

- 후보 ID: `ai-coverage-v5-support-service-visit`
- AI 후보 발화: “노트북 키보드가 고장 났어요. 서비스센터에 직접 방문하겠습니다.”

```json
{
  "current_fields": {
    "model_name": null,
    "occurred_at": null,
    "preferred_schedule": null,
    "product_type": null,
    "safety_status": null,
    "service_channel": null,
    "symptom": null
  },
  "labels": {
    "change_field": null,
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
      "service_channel": {
        "accepted_values": [
          "visit"
        ]
      },
      "symptom": {
        "accepted_values": [
          "키보드 고장"
        ]
      }
    },
    "intent": "service_request",
    "user_action": "provide_details"
  },
  "projected_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=visit"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "field_option",
      "scenario_key": "고객센터:a/s 접수",
      "value": "service_channel=visit"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
