# 채택된 AI 발화 36건의 구조화 NLU 정답 초안

**상태: `ai_assisted_unreviewed`.** [문장 후보](heldout_nlu_ai_draft_round2.md)를
사용자가 검토 대상으로 채택한 뒤 AI가 제안한 **라벨 초안**이다. 문장·라벨의
사람 작성, 최종 정답 확정, split 배정, 공식 test 등록 또는 정확도 측정은 아니다.
표에 적지 않은 새 필드는 모두 `null`, `change_field`는 모두 `null`,
`offered_alternative_times`는 모두 빈 목록을 제안한다. 값은 정규화 결과 초안이지
사용자가 말하지 않은 정보를 보충한 확정값이 아니다.

문장·라벨 표가 어긋나지 않았는지 다음 명령으로 확인할 수 있다.

```bash
.venv/bin/python -m scripts.validate_nlu_review_draft
```

이 검사는 36개 슬롯, 채택 표시, 기존 개발·AI 후보와의 **정확 원문 중복**,
라이브 출력 계약만 확인한다. 의미가 비슷한 문장, 실제 정답, 사람 저작 여부는
판정하지 않는다.

## 2026-11-03 사용자 판정 반영

| 슬롯 | 사용자 판정 | 반영 내용 |
| --- | --- | --- |
| H04 | `unknown` | 행동 초안 유지 |
| H08 | 결석 통지 | `provide_absence_info`, `absence_date=지난주`로 변경. 수업명·사유는 공란 |
| H13 | 미수령을 빼고 지연 문의 | 발화를 배달 예정 시간 경과와 현재 위치 문의로 수정 |
| H17 | 재배달 희망 | `resolution_preference=redelivery` 유지 |
| H21 | 주제 공란 | `inquiry_topic=null` 유지 |
| H23 | 관계를 다시 질문 | `applicant_relation=null` 유지. 관계를 추측하지 않고 추가 질문 필요로 기록 |

이 판정은 위 항목의 해석 방향에 관한 사용자 확인이다. 나머지 필드와 전체
case의 최종 정답 검수·출처 판정·동결을 완료했다는 뜻은 아니다.

| 슬롯 | 현재 상태 초안 | intent 초안 | user_action 초안 | 이번 발화의 새 필드 초안 | 확인할 쟁점 |
| --- | --- | --- | --- | --- | --- |
| H01 | `collecting_service_request` | `service_request` | `provide_details` | `product_type=태블릿`; `symptom=충전 케이블을 빼면 전원이 꺼짐`; `occurred_at=지난주부터`; `service_channel=visit` | 증상을 더 짧게 정규화할지 |
| H02 | `collecting_service_request` | `service_request` | `unknown` | 없음 | “아까 설명한” 이전 문맥이 비어 있어 발화 독립성 검토 |
| H03 | `collecting_plan_contract` | `plan_contract_consultation` | `provide_details` | `inquiry_type=contract_expiry`; `current_service=인터넷 결합 상품`; `consultation_goal=약정 종료 시점 확인` | 계약서가 없다는 말은 새 필드로 넣지 않음 |
| H04 | `collecting_plan_contract` | `plan_contract_consultation` | `unknown` | 없음 | 사용자 판정: `unknown` 유지 |
| H05 | `collecting_network_issue` | `network_call_issue` | `provide_details` | `service_type=voice_call`; `symptom=상대 목소리가 끊겨 들림`; `troubleshooting_done=기기 재부팅` | 발생 시점은 말하지 않음 |
| H06 | `collecting_network_issue` | `network_call_issue` | `unknown` | 없음 | 장애 처리 대신 공유기 배치 조언 요청 |
| H07 | `collecting_absence_info` | `absence_notice` | `provide_absence_info` | `class_name=운영체제`; `absence_date=금요일`; `absence_reason=학과 행사 참석` | “금요일”의 기준일을 추가하지 않음 |
| H08 | `collecting_absence_info` | `absence_notice` | `provide_absence_info` | `absence_date=지난주` | 사용자 판정: 결석 통지. 수업명·사유는 말하지 않음 |
| H09 | `collecting_assignment_info` | `assignment_inquiry` | `provide_assignment_info` | `course_name=알고리즘`; `assignment_topic=과제 3번`; `question=입력 크기 상한 확인` | 과제 번호와 질문 분리 |
| H10 | `collecting_assignment_info` | `assignment_inquiry` | `unknown` | 없음 | 강의실 변경 문의는 과제 내용과 무관 |
| H11 | `collecting_appointment_info` | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=진로 상담` | “학기 말 전”을 정확한 날짜로 만들지 않음 |
| H12 | `collecting_appointment_info` | `appointment_booking` | `unknown` | 없음 | 서류 전달과 재실 여부 문의를 면담 예약으로 볼지 검토 |
| H13 | `collecting_delay_inquiry` | `delivery_delay_inquiry` | `provide_details` | `order_number=Z-913`; `delay_detail=배달 예정 시간이 지남`; `inquiry_goal=delivery_location` | 사용자 판정: 미수령 표현 제외, 현재 위치 문의 |
| H14 | `collecting_delay_inquiry` | `delivery_delay_inquiry` | `unknown` | 없음 | 배달 장소 변경은 지연 문의 범위 밖 |
| H15 | `collecting_order_change` | `delivery_order_change` | `provide_details` | `order_number=Q-218`; `change_type=delivery_address`; `requested_change=배달 주소를 사무실에서 집으로 변경` | 가상 주소를 실제 주소로 채우지 않음 |
| H16 | `collecting_order_change` | `delivery_order_change` | `unknown` | 없음 | 주문 변경 의사가 없는 재료 확인 문의 |
| H17 | `collecting_refund_redelivery` | `delivery_refund_redelivery` | `provide_details` | `order_number=R-527`; `issue_type=damaged_or_quality`; `issue_detail=포장 용기 파손으로 내용물이 흐름`; `resolution_preference=redelivery` | 사용자 판정: 재배달 희망으로 해석 |
| H18 | `collecting_refund_redelivery` | `delivery_refund_redelivery` | `unknown` | 없음 | 보관 방법 문의는 환불·재배달 요청과 무관 |
| H19 | `collecting_bulky_waste` | `bulky_waste_guidance` | `provide_details` | `region=대전 서구`; `item_name=장롱`; `quantity=1개`; `request_topic=application` | 품목명에 “낡은”을 포함할지 |
| H20 | `collecting_bulky_waste` | `bulky_waste_guidance` | `unknown` | 없음 | 분리배출 요일 문의는 대형폐기물 접수 범위 밖 |
| H21 | `collecting_passport_inquiry` | `passport_guidance` | `provide_details` | `application_type=reissue` | 사용자 판정: `inquiry_topic` 공란 유지 |
| H22 | `collecting_passport_inquiry` | `passport_guidance` | `unknown` | 없음 | 주민등록증 문의는 여권 발급 범위 밖 |
| H23 | `collecting_certificate_inquiry` | `resident_certificate_guidance` | `provide_details` | `document_type=register_copy`; `inquiry_topic=eligibility` | 사용자 판정: `applicant_relation` 공란, 관계를 다시 질문 |
| H24 | `collecting_certificate_inquiry` | `resident_certificate_guidance` | `unknown` | 없음 | 인감증명서 문의는 등본 범위 밖 |
| H25 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `date=내일`; `service_type=커트와 두피 관리` | “낮”을 정확한 시각으로 만들지 않음 |
| H26 | `collecting_reservation_info` | `reservation` | `unknown` | 없음 | 반려동물 미용은 사람 미용실 예약 범위 밖 |
| H27 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `service_type=레이어드 커트` | 이전 날짜·시간은 사람 검토 문맥이며 이번 발화의 새 추출값이 아님 |
| H28 | `asking_date` | `reservation` | `continue_collecting` | `date=다음 달 3일`; `time=오전 11시` | 재진 여부는 현재 추출 필드에 없음 |
| H29 | `asking_department` | `reservation` | `unknown` | 없음 | 주차장 문의를 예약 정보로 보지 않는지 검토 |
| H30 | `asking_department` | `reservation` | `continue_collecting` | `department=안과` | 이전 시간·예약자 값은 사람 검토 문맥이며 이번 발화의 새 추출값이 아님 |
| H31 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `duration=2시간`; `party_size=6명` | “평일 저녁”은 특정 날짜·시각으로 만들지 않음 |
| H32 | `collecting_reservation_info` | `reservation` | `unknown` | 없음 | 와이파이 이용 안내는 공간 예약 범위 밖 |
| H33 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `party_size=5명` | 이전 날짜·시작 시각·기간은 사람 검토 문맥이며 새 추출값이 아님 |
| H34 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `date=다음 주 화요일`; `party_size=2명` | “점심”을 특정 시각으로 만들지 않음; 창가 좌석 필드는 없음 |
| H35 | `collecting_reservation_info` | `reservation` | `unknown` | 없음 | 포장 메뉴 문의는 자리 예약 범위 밖 |
| H36 | `collecting_reservation_info` | `reservation` | `continue_collecting` | `party_size=3명` | 이전 날짜·시각·예약자 값은 사람 검토 문맥이며 새 추출값이 아님 |

## 현재 계약과 충돌할 수 있는 부분

- H27·H30·H33·H36의 상세 업무 추출기는 `conversation_state`, 이번 발화와
  예약 대안 시간만 모델에 전달한다. 이전 필드는 그래프 상태에 보관되고 추출 뒤
  합쳐진다. 따라서 이 **NLU 추출 평가**에서 `current_fields`는 빈 객체로 두고,
  이전 턴 문맥은 사람이 발화 의미를 검토하는 참고로만 쓴다. 기존 상태값까지
  포함한 전체 대화 흐름은 별도의 그래프 테스트로 검증해야 한다.
- H04·H08·H13·H17·H21·H23의 쟁점은 위 사용자 판정 방향을 반영했다. 다른
  필드와 전체 사례의 정답 확정은 남아 있다. 이 결정을 모델 출력에 맞춰 사후
  변경해서는 안 된다.
- 이 36건은 AI 문장 후보를 채택한 상태다. 최종 독립 test의 `human_authored`
  출처 조건을 충족하려면 사람이 직접 새 문장을 작성하고, 정답과 검수 원장을
  모델 실행 전에 고정해야 한다.
