# 구조화 NLU 대안 시간 커버리지 후보 검토 작업지 V3

> 31개 발화와 정답은 AI가 작성한 미검수 진단 후보입니다.
> 공식 corpus에 자동 승격할 수 없으며 human_authored로 표시할 수 없습니다.

- 후보 묶음: `structured-nlu-coverage-candidates-v3`
- 선행 후보 묶음: `structured-nlu-coverage-candidates-v2`
- 기준 진단 case 수: `28`
- 기준 충족/미충족: `613` / `949`
- 투영 증가: `55`
- 투영 충족/미충족: `668` / `894`
- 자동 승격 허용: `false`

## 01. 예약:미용실 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-ask-other-time-no-offers`
- AI 후보 발화: “그럼 가능한 다른 시술 시간이 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->ask_other_time"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 02. 예약:미용실 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-ask-other-time-offers-unselected`
- AI 후보 발화: “말씀해 주신 시간 말고 다른 시술 시간도 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->offers_unselected"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 03. 예약:미용실 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-change-date-no-offers`
- AI 후보 발화: “미용실 예약 날짜를 이번 주 목요일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "이번 주 목요일"
        ]
      },
      "designer": null,
      "selected_time": null,
      "service_type": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "value": "change_date->date"
    },
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->no_offers"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 04. 예약:미용실 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-change-date-offers-unselected`
- AI 후보 발화: “제시된 시간 대신 미용실 예약을 다음 주 화요일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "다음 주 화요일"
        ]
      },
      "designer": null,
      "selected_time": null,
      "service_type": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->offers_unselected"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 05. 예약:미용실 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-unknown-no-offers`
- AI 후보 발화: “주차 지원이 되나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "unknown"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 06. 예약:미용실 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hair-salon-unavailable-unknown-offers-unselected`
- AI 후보 발화: “제시된 시간은 선택하지 않고 주차 지원 여부를 알고 싶어요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "unknown"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->offers_unselected"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 07. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-suggest-ask-other-time-no-offers`
- AI 후보 발화: “다른 진료 가능 시간도 더 알려주세요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->ask_other_time->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "suggest_alternative->ask_other_time"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 08. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-suggest-ask-other-time-offers-unselected`
- AI 후보 발화: “제안하신 두 시간 외에 다른 진료 시간도 있나요?”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->ask_other_time->offers_unselected"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 09. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-suggest-change-date-no-offers`
- AI 후보 발화: “병원 예약 날짜를 이번 주 금요일로 바꿀게요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "이번 주 금요일"
        ]
      },
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->change_date->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "suggest_alternative->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 10. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-suggest-change-date-offers-unselected`
- AI 후보 발화: “제안 시간 대신 예약 날짜를 다음 주 월요일로 바꿀게요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "다음 주 월요일"
        ]
      },
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->change_date->offers_unselected"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 11. 예약:병원 예약 / selected_offer

- 후보 ID: `ai-coverage-v3-hospital-suggest-select-alternative-time-selected-offer`
- AI 후보 발화: “제안해 주신 진료 시간 중 오후 3시로 할게요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
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
    "user_action": "select_alternative_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->select_alternative_time->selected_offer"
    },
    {
      "dimension": "state_action",
      "value": "suggest_alternative->select_alternative_time"
    }
  ],
  "tags": [
    "single_field"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 12. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-suggest-unknown-no-offers`
- AI 후보 발화: “진료비 결제 방법이 궁금해요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->unknown->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "suggest_alternative->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 13. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-suggest-unknown-offers-unselected`
- AI 후보 발화: “제안 시간은 선택하지 않을게요. 진료비 결제 방법이 궁금해요.”
```json
{
  "conversation_state": "suggest_alternative",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "suggest_alternative->unknown->offers_unselected"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 14. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-unavailable-ask-other-time-no-offers`
- AI 후보 발화: “그럼 가능한 다른 진료 시간이 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->ask_other_time"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 15. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-unavailable-ask-other-time-offers-unselected`
- AI 후보 발화: “말씀해 주신 시간 말고 다른 진료 시간도 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->offers_unselected"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 16. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-unavailable-change-date-no-offers`
- AI 후보 발화: “그럼 병원 예약 날짜를 내일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "내일"
        ]
      },
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "value": "change_date->date"
    },
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->no_offers"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 17. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-unavailable-change-date-offers-unselected`
- AI 후보 발화: “제시된 진료 시간 대신 예약 날짜를 모레로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "모레"
        ]
      },
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->offers_unselected"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 18. 예약:병원 예약 / no_offers

- 후보 ID: `ai-coverage-v3-hospital-unavailable-unknown-no-offers`
- AI 후보 발화: “병원 주차장은 어디예요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 19. 예약:병원 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-hospital-unavailable-unknown-offers-unselected`
- AI 후보 발화: “그 시간들은 고르지 않을게요. 병원 주차장은 어디예요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "department": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->offers_unselected"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 20. 예약:식당 예약 / no_offers

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-ask-other-time-no-offers`
- AI 후보 발화: “그럼 가능한 다른 식사 시간이 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->ask_other_time"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 21. 예약:식당 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-ask-other-time-offers-unselected`
- AI 후보 발화: “말씀해 주신 시간 말고 다른 식사 시간도 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->offers_unselected"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 22. 예약:식당 예약 / no_offers

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-change-date-no-offers`
- AI 후보 발화: “식당 예약 날짜를 이번 주 토요일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "이번 주 토요일"
        ]
      },
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "value": "change_date->date"
    },
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->no_offers"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 23. 예약:식당 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-change-date-offers-unselected`
- AI 후보 발화: “제시된 시간 대신 식당 예약을 다음 주 토요일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "다음 주 토요일"
        ]
      },
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->offers_unselected"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 24. 예약:식당 예약 / no_offers

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-unknown-no-offers`
- AI 후보 발화: “식당에 주차할 수 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 25. 예약:식당 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-restaurant-unavailable-unknown-offers-unselected`
- AI 후보 발화: “그 시간들은 고르지 않을게요. 식당 주차가 가능한가요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": null,
      "party_size": null,
      "selected_time": null,
      "time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "unknown"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->offers_unselected"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 26. 예약:스터디룸 예약 / no_offers

- 후보 ID: `ai-coverage-v3-study-room-unavailable-ask-other-time-no-offers`
- AI 후보 발화: “그럼 가능한 다른 이용 시간이 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->ask_other_time"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 27. 예약:스터디룸 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-study-room-unavailable-ask-other-time-offers-unselected`
- AI 후보 발화: “말씀해 주신 시간 말고 다른 이용 시간도 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "ask_other_time"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->ask_other_time->offers_unselected"
    }
  ],
  "tags": [
    "ellipsis"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 28. 예약:스터디룸 예약 / no_offers

- 후보 ID: `ai-coverage-v3-study-room-unavailable-change-date-no-offers`
- AI 후보 발화: “스터디룸 예약 날짜를 내일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "내일"
        ]
      },
      "duration": null,
      "party_size": null,
      "selected_time": null,
      "start_time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "action_field_present",
      "value": "change_date->date"
    },
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->no_offers"
    },
    {
      "dimension": "scenario_difficulty_tag",
      "value": "correction"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->change_date"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 29. 예약:스터디룸 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-study-room-unavailable-change-date-offers-unselected`
- AI 후보 발화: “제시된 시간 대신 스터디룸 예약을 이번 주 일요일로 바꿀게요.”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
    "change_field": null,
    "fields": {
      "date": {
        "accepted_values": [
          "이번 주 일요일"
        ]
      },
      "duration": null,
      "party_size": null,
      "selected_time": null,
      "start_time": null,
      "user_name": null
    },
    "intent": "reservation",
    "user_action": "change_date"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->change_date->offers_unselected"
    }
  ],
  "tags": [
    "single_field",
    "correction"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 30. 예약:스터디룸 예약 / no_offers

- 후보 ID: `ai-coverage-v3-study-room-unavailable-unknown-no-offers`
- AI 후보 발화: “스터디룸에 화이트보드가 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "unknown"
  },
  "offered_alternative_times": [],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->no_offers"
    },
    {
      "dimension": "state_action",
      "value": "reservation_unavailable->unknown"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}

## 31. 예약:스터디룸 예약 / offers_unselected

- 후보 ID: `ai-coverage-v3-study-room-unavailable-unknown-offers-unselected`
- AI 후보 발화: “그 시간들은 고르지 않을게요. 화이트보드가 있나요?”
```json
{
  "conversation_state": "reservation_unavailable",
  "labels": {
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
    "user_action": "unknown"
  },
  "offered_alternative_times": [
    "오후 3시",
    "오후 4시"
  ],
  "projected_obligations": [
    {
      "dimension": "alternative_time_relation",
      "value": "reservation_unavailable->unknown->offers_unselected"
    }
  ],
  "tags": [
    "hard_negative"
  ]
}
```
- 검토 판단: [ ] 승인  [ ] 수정 필요  [ ] 거부
- 수정안 또는 판단 근거:
  > {{발화 의미와 정답을 확인하고, 수정이 필요할 때만 작성}}
