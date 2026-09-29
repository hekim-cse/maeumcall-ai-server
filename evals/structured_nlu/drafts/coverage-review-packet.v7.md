# 구조화 NLU action-field-present 커버리지 후보 검토 작업지 V7

> 27개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.
> 커밋된 원본은 직접 체크하지 말고 작업용 사본에 판단을 기록합니다.

- 선행 V6 artifact SHA-256: `70c8e8d6c3000d58d361d03effdd66c4d7833be9a31c09ebda75886ca6834630`
- 기준 진단 case 수: `143`
- 기준 충족/미충족: `900` / `662`
- 투영 증가: `59`
- 투영 충족/미충족: `959` / `603`
- 자동 승격 허용: `false`

## 01. 시청:주민등록 등본 문의

- 후보 ID: `ai-coverage-v7-city-certificate-channel`
- AI 후보 발화: “정부24 발급 대신 무인발급기 이용으로 바꿀게요.”

```json
{
  "current_fields": {
    "applicant_relation": null,
    "document_type": null,
    "inquiry_topic": null,
    "issuance_channel": "government24"
  },
  "labels": {
    "change_field": "issuance_channel",
    "fields": {
      "applicant_relation": null,
      "document_type": null,
      "inquiry_topic": null,
      "issuance_channel": {
        "accepted_values": [
          "kiosk"
        ]
      }
    },
    "intent": "resident_certificate_guidance",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "change_detail->issuance_channel"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "issuance_channel->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:주민등록 등본 문의",
      "value": "change_detail->issuance_channel"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 02. 시청:대형폐기물 배출

- 후보 ID: `ai-coverage-v7-city-waste-quantity`
- AI 후보 발화: “수량을 한 개가 아니라 두 개로 정정합니다.”

```json
{
  "current_fields": {
    "item_name": null,
    "quantity": "1개",
    "region": null,
    "request_topic": null
  },
  "labels": {
    "change_field": "quantity",
    "fields": {
      "item_name": null,
      "quantity": {
        "accepted_values": [
          "2개"
        ]
      },
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
      "value": "change_detail->quantity"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "quantity->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "시청:대형폐기물 배출",
      "value": "change_detail->quantity"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 03. 배달:주문 변경

- 후보 ID: `ai-coverage-v7-delivery-change-unavailable-preference`
- AI 후보 발화: “변경이 안 되면 취소 여부를 확인하지 말고 기존 주문을 유지해 주세요.”

```json
{
  "current_fields": {
    "change_type": null,
    "order_number": null,
    "requested_change": null,
    "unavailable_preference": "check_cancellation"
  },
  "labels": {
    "change_field": "unavailable_preference",
    "fields": {
      "change_type": null,
      "order_number": null,
      "requested_change": null,
      "unavailable_preference": {
        "accepted_values": [
          "keep_order"
        ]
      }
    },
    "intent": "delivery_order_change",
    "user_action": "change_detail"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:주문 변경",
      "value": "change_detail->unavailable_preference"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "배달:주문 변경",
      "value": "unavailable_preference->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "배달:주문 변경",
      "value": "change_detail->unavailable_preference"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 04. 교수님:결석 사유 전달

- 후보 ID: `ai-coverage-v7-professor-absence-class`
- AI 후보 발화: “수업명은 인공지능이 아니라 자료구조입니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "absence_date": null,
      "absence_reason": null,
      "class_name": {
        "accepted_values": [
          "자료구조"
        ]
      },
      "user_name": null
    },
    "intent": "absence_notice",
    "user_action": "change_class_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_class_name->class_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "confirming_absence_info->change_class_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_class_name->class_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 05. 교수님:결석 사유 전달

- 후보 ID: `ai-coverage-v7-professor-absence-date`
- AI 후보 발화: “결석 날짜는 오늘이 아니라 내일입니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "absence_date": {
        "accepted_values": [
          "내일"
        ]
      },
      "absence_reason": null,
      "class_name": null,
      "user_name": null
    },
    "intent": "absence_notice",
    "user_action": "change_absence_date"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_absence_date->absence_date"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "correction"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "single_field"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "confirming_absence_info->change_absence_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_absence_date->absence_date"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 06. 교수님:결석 사유 전달

- 후보 ID: `ai-coverage-v7-professor-absence-name`
- AI 후보 발화: “학생 이름을 홍길동이 아니라 김민수로 정정합니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "absence_date": null,
      "absence_reason": null,
      "class_name": null,
      "user_name": {
        "accepted_values": [
          "김민수"
        ]
      }
    },
    "intent": "absence_notice",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "confirming_absence_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 07. 교수님:결석 사유 전달

- 후보 ID: `ai-coverage-v7-professor-absence-reason`
- AI 후보 발화: “결석 사유를 예비군이 아니라 병원 진료로 수정하겠습니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "absence_date": null,
      "absence_reason": {
        "accepted_values": [
          "병원 진료"
        ]
      },
      "class_name": null,
      "user_name": null
    },
    "intent": "absence_notice",
    "user_action": "change_absence_reason"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_absence_reason->absence_reason"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "confirming_absence_info->change_absence_reason"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:결석 사유 전달",
      "value": "change_absence_reason->absence_reason"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 08. 교수님:면담 예약

- 후보 ID: `ai-coverage-v7-professor-appointment-date`
- AI 후보 발화: “면담 날짜를 내일이 아니라 다음 주 월요일로 바꾸고 싶습니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "appointment_purpose": null,
      "date": {
        "accepted_values": [
          "다음 주 월요일"
        ]
      },
      "time": null,
      "user_name": null
    },
    "intent": "appointment_booking",
    "user_action": "change_date"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_date->date"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "교수님:면담 예약",
      "value": "correction"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "scenario_key": "교수님:면담 예약",
      "value": "single_field"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:면담 예약",
      "value": "confirming_info->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_date->date"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 09. 교수님:면담 예약

- 후보 ID: `ai-coverage-v7-professor-appointment-name`
- AI 후보 발화: “학생 이름은 홍길동이 아니라 이서연입니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "appointment_purpose": null,
      "date": null,
      "time": null,
      "user_name": {
        "accepted_values": [
          "이서연"
        ]
      }
    },
    "intent": "appointment_booking",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:면담 예약",
      "value": "confirming_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 10. 교수님:면담 예약

- 후보 ID: `ai-coverage-v7-professor-appointment-purpose`
- AI 후보 발화: “면담 목적은 과제 문의가 아니라 진로 상담입니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "appointment_purpose": {
        "accepted_values": [
          "진로 상담"
        ]
      },
      "date": null,
      "time": null,
      "user_name": null
    },
    "intent": "appointment_booking",
    "user_action": "change_purpose"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_purpose->appointment_purpose"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:면담 예약",
      "value": "confirming_info->change_purpose"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_purpose->appointment_purpose"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 11. 교수님:면담 예약

- 후보 ID: `ai-coverage-v7-professor-appointment-time`
- AI 후보 발화: “면담 시간을 오후 3시에서 4시로 변경해 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "appointment_purpose": null,
      "date": null,
      "time": {
        "accepted_values": [
          "오후 4시"
        ]
      },
      "user_name": null
    },
    "intent": "appointment_booking",
    "user_action": "change_time"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_time->time"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:면담 예약",
      "value": "confirming_info->change_time"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:면담 예약",
      "value": "change_time->time"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 12. 교수님:과제 문의

- 후보 ID: `ai-coverage-v7-professor-assignment-follow-up`
- AI 후보 발화: “팀 프로젝트 과제인데 제출 형식이 PDF인지도 알려 주실 수 있나요?”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "assignment_topic": {
        "accepted_values": [
          "팀 프로젝트"
        ]
      },
      "course_name": null,
      "question": {
        "accepted_values": [
          "제출 형식이 PDF인지"
        ]
      },
      "user_name": null
    },
    "intent": "assignment_inquiry",
    "user_action": "ask_follow_up"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:과제 문의",
      "value": "ask_follow_up->assignment_topic"
    },
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:과제 문의",
      "value": "ask_follow_up->question"
    },
    {
      "dimension": "state_action",
      "scenario_key": "교수님:과제 문의",
      "value": "answering_assignment_question->ask_follow_up"
    }
  ],
  "tags": [
    "multi_field"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:과제 문의",
      "value": "ask_follow_up->assignment_topic"
    },
    {
      "dimension": "action_field_present",
      "scenario_key": "교수님:과제 문의",
      "value": "ask_follow_up->question"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 13. 예약:미용실 예약

- 후보 ID: `ai-coverage-v7-reservation-hair-designer`
- AI 후보 발화: “디자이너를 박지수 선생님에서 김아름 선생님으로 바꿔 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "designer": {
        "accepted_values": [
          "김아름"
        ]
      },
      "selected_time": null,
      "service_type": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_designer"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_designer->designer"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:미용실 예약",
      "value": "confirming_info->change_designer"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_designer->designer"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 14. 예약:미용실 예약

- 후보 ID: `ai-coverage-v7-reservation-hair-name`
- AI 후보 발화: “예약자 이름은 김민지가 아니라 최유진입니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "designer": null,
      "selected_time": null,
      "service_type": null,
      "time": null,
      "user_name": {
        "accepted_values": [
          "최유진"
        ]
      }
    },
    "intent": "reservation",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:미용실 예약",
      "value": "confirming_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 15. 예약:미용실 예약

- 후보 ID: `ai-coverage-v7-reservation-hair-service`
- AI 후보 발화: “시술을 커트가 아니라 염색으로 변경할게요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "designer": null,
      "selected_time": null,
      "service_type": {
        "accepted_values": [
          "염색"
        ]
      },
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_service_type"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_service_type->service_type"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:미용실 예약",
      "value": "confirming_info->change_service_type"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_service_type->service_type"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 16. 예약:미용실 예약

- 후보 ID: `ai-coverage-v7-reservation-hair-time`
- AI 후보 발화: “예약 시간을 오후 2시에서 5시로 바꾸고 싶어요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "designer": null,
      "selected_time": null,
      "service_type": null,
      "time": {
        "accepted_values": [
          "오후 5시"
        ]
      },
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_time"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_time->time"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:미용실 예약",
      "value": "confirming_info->change_time"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:미용실 예약",
      "value": "change_time->time"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 17. 예약:병원 예약

- 후보 ID: `ai-coverage-v7-reservation-hospital-department`
- AI 후보 발화: “진료과를 내과에서 정형외과로 변경해 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": {
        "accepted_values": [
          "정형외과"
        ]
      },
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_department"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_department->department"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:병원 예약",
      "value": "confirming_info->change_department"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_department->department"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 18. 예약:병원 예약

- 후보 ID: `ai-coverage-v7-reservation-hospital-name`
- AI 후보 발화: “예약자 이름을 홍길동에서 박서준으로 정정합니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": {
        "accepted_values": [
          "박서준"
        ]
      }
    },
    "intent": "reservation",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:병원 예약",
      "value": "confirming_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 19. 예약:병원 예약

- 후보 ID: `ai-coverage-v7-reservation-hospital-time`
- AI 후보 발화: “진료 시간을 오전 10시가 아니라 11시로 바꿀게요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": {
        "accepted_values": [
          "오전 11시"
        ]
      },
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_time"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_time->time"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:병원 예약",
      "value": "confirming_info->change_time"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:병원 예약",
      "value": "change_time->time"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 20. 예약:식당 예약

- 후보 ID: `ai-coverage-v7-reservation-restaurant-name`
- AI 후보 발화: “예약자 이름을 홍길동에서 윤지호로 수정해 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": {
        "accepted_values": [
          "윤지호"
        ]
      }
    },
    "intent": "reservation",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:식당 예약",
      "value": "confirming_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 21. 예약:식당 예약

- 후보 ID: `ai-coverage-v7-reservation-restaurant-party`
- AI 후보 발화: “예약 인원을 다섯 명에서 여섯 명으로 바꿔 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": {
        "accepted_values": [
          "6명"
        ]
      },
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_party_size"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_party_size->party_size"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:식당 예약",
      "value": "confirming_info->change_party_size"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_party_size->party_size"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 22. 예약:식당 예약

- 후보 ID: `ai-coverage-v7-reservation-restaurant-time`
- AI 후보 발화: “예약 시간을 오후 6시가 아니라 7시로 변경할게요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": {
        "accepted_values": [
          "오후 7시"
        ]
      },
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_time"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_time->time"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:식당 예약",
      "value": "confirming_info->change_time"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:식당 예약",
      "value": "change_time->time"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 23. 예약:스터디룸 예약

- 후보 ID: `ai-coverage-v7-reservation-study-duration`
- AI 후보 발화: “이용 시간을 두 시간에서 세 시간으로 변경해 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "duration": {
        "accepted_values": [
          "3시간"
        ]
      },
      "party_size": null,
      "selected_time": null,
      "start_time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_duration"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_duration->duration"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:스터디룸 예약",
      "value": "confirming_info->change_duration"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_duration->duration"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 24. 예약:스터디룸 예약

- 후보 ID: `ai-coverage-v7-reservation-study-name`
- AI 후보 발화: “예약자 이름은 김민수 대신 정하늘로 해 주세요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "duration": null,
      "party_size": null,
      "selected_time": null,
      "start_time": null,
      "user_name": {
        "accepted_values": [
          "정하늘"
        ]
      }
    },
    "intent": "reservation",
    "user_action": "change_user_name"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_user_name->user_name"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:스터디룸 예약",
      "value": "confirming_info->change_user_name"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_user_name->user_name"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 25. 예약:스터디룸 예약

- 후보 ID: `ai-coverage-v7-reservation-study-party`
- AI 후보 발화: “이용 인원을 세 명이 아니라 네 명으로 바꿀게요.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "duration": null,
      "party_size": {
        "accepted_values": [
          "4명"
        ]
      },
      "selected_time": null,
      "start_time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_party_size"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_party_size->party_size"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:스터디룸 예약",
      "value": "confirming_info->change_party_size"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_party_size->party_size"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 26. 예약:스터디룸 예약

- 후보 ID: `ai-coverage-v7-reservation-study-start`
- AI 후보 발화: “시작 시간을 오후 5시에서 6시로 변경하고 싶습니다.”

```json
{
  "current_fields": {},
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "duration": null,
      "party_size": null,
      "selected_time": null,
      "start_time": {
        "accepted_values": [
          "오후 6시"
        ]
      },
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_start_time"
  },
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_start_time->start_time"
    },
    {
      "dimension": "state_action",
      "scenario_key": "예약:스터디룸 예약",
      "value": "confirming_info->change_start_time"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "예약:스터디룸 예약",
      "value": "change_start_time->start_time"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부

## 27. 고객센터:요금/약정 상담

- 후보 ID: `ai-coverage-v7-support-plan-consent-scope`
- AI 후보 발화: “개인정보 조회 동의를 취소하고 일반 안내만 받겠습니다.”

```json
{
  "current_fields": {
    "consent_scope": "authenticated_lookup",
    "consultation_goal": null,
    "current_service": null,
    "inquiry_type": null
  },
  "labels": {
    "change_field": "consent_scope",
    "fields": {
      "consent_scope": {
        "accepted_values": [
          "general_guidance"
        ]
      },
      "consultation_goal": null,
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
      "value": "change_detail->consent_scope"
    },
    {
      "dimension": "current_delta_relation",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "consent_scope->existing_value_replaced"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ],
  "target_obligations": [
    {
      "dimension": "action_field_present",
      "scenario_key": "고객센터:요금/약정 상담",
      "value": "change_detail->consent_scope"
    }
  ]
}
```

- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
