# AI 작성 새 발화의 전체 정답 초안 검토표

**상태:** AI 제안, 사람의 전체 정답 검수 전, Q4·Q5 미실행. 대응 발화는
[AH01–AH32 문장 후보](ai_authored_nlu_heldout_review.md)다. 아래 표에서
적지 않은 업무 필드는 모두 `null`로 제안한다. 모든 사례의 대화 상태는
`greeting`, 이전 필드는 비어 있으며, 예약 대체 시간도 없다. 모든
`change_field`는 `null`이다. 이는 입력 문맥까지 포함한 **초안**이지
검수 완료 정답이나 모델 실행 허가가 아니다.

| ID | `intent` | `user_action` | 비공란 필드 초안 | 태그 초안 |
| --- | --- | --- | --- | --- |
| AH01 | `service_request` | `provide_details` | `product_type=전자레인지`; `symptom=작동 버튼을 누르면 차단기가 내려감`; `safety_status=safety_issue` | `multi_field`, `safety` |
| AH02 | `service_request` | `unknown` | 없음 | `hard_negative` |
| AH03 | `plan_contract_consultation` | `provide_details` | `inquiry_type=billing`; `consultation_goal=이번 달 요금이 지난달보다 1만 원 더 청구된 이유 확인` | `multi_field` |
| AH04 | `plan_contract_consultation` | `unknown` | 없음 | `hard_negative` |
| AH05 | `network_call_issue` | `provide_details` | `service_type=voice_call`; `symptom=상대방 목소리는 들리지만 내 목소리가 전달되지 않음`; `occurred_at=오늘 오후` | `multi_field` |
| AH06 | `network_call_issue` | `unknown` | 없음 | `hard_negative` |
| AH07 | `absence_notice` | `provide_absence_info` | `class_name=실험 수업`; `absence_date=금요일`; `absence_reason=교통사고로 이동이 어려움` | `multi_field` |
| AH08 | `absence_notice` | `unknown` | 없음 | `hard_negative` |
| AH09 | `assignment_inquiry` | `provide_assignment_info` | `assignment_topic=이번 보고서`; `question=참고문헌이 본문 분량에 포함되는지` | `multi_field` |
| AH10 | `assignment_inquiry` | `unknown` | 없음 | `hard_negative` |
| AH11 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=진로 상담`; `date=이번 주 금요일`; `time=오전` | `multi_field` |
| AH12 | `appointment_booking` | `unknown` | 없음 | `hard_negative` |
| AH13 | `delivery_delay_inquiry` | `provide_details` | `delay_detail=음식점에서 나온 뒤 한참 동안 이동 기록이 없음`; `inquiry_goal=delay_reason` | `multi_field` |
| AH14 | `delivery_delay_inquiry` | `unknown` | 없음 | `hard_negative` |
| AH15 | `delivery_order_change` | `provide_details` | `order_number=V-208`; `change_type=delivery_address`; `requested_change=회사 후문` | `multi_field` |
| AH16 | `delivery_order_change` | `unknown` | 없음 | `hard_negative` |
| AH17 | `delivery_refund_redelivery` | `provide_details` | `issue_type=damaged_or_quality`; `issue_detail=우유 유통기한이 지남`; `evidence_status=available` | `multi_field` |
| AH18 | `delivery_refund_redelivery` | `unknown` | 없음 | `hard_negative` |
| AH19 | `bulky_waste_guidance` | `provide_details` | `request_topic=collection_status` | `single_field` |
| AH20 | `bulky_waste_guidance` | `unknown` | 없음 | `hard_negative` |
| AH21 | `passport_guidance` | `provide_details` | `application_type=reissue`; `inquiry_topic=documents` | `multi_field` |
| AH22 | `passport_guidance` | `unknown` | 없음 | `hard_negative` |
| AH23 | `resident_certificate_guidance` | `provide_details` | `document_type=register_copy`; `applicant_relation=self`; `issuance_channel=in_person`; `inquiry_topic=documents` | `multi_field` |
| AH24 | `resident_certificate_guidance` | `unknown` | 없음 | `hard_negative` |
| AH25 | `reservation` | `continue_collecting` | `date=화요일`; `time=저녁 6시`; `service_type=앞머리 커트` | `multi_field` |
| AH26 | `reservation` | `unknown` | 없음 | `hard_negative` |
| AH27 | `reservation` | `continue_collecting` | `department=피부과`; `date=다음 주 수요일`; `time=오전` | `multi_field` |
| AH28 | `null` | `unknown` | 없음 | `hard_negative` |
| AH29 | `reservation` | `continue_collecting` | `date=금요일`; `start_time=저녁 7시`; `duration=두 시간`; `party_size=세 명` | `multi_field` |
| AH30 | `reservation` | `unknown` | 없음 | `hard_negative` |
| AH31 | `reservation` | `continue_collecting` | `date=금요일`; `time=밤 8시`; `party_size=두 명` | `multi_field` |
| AH32 | `reservation` | `unknown` | 없음 | `hard_negative` |

특히 다음 판단을 확인해야 한다.

- AH01: 차단기가 내려가는 증상을 `safety_issue`로 기록할지.
- AH02·04·06·12·22: 현재 업무와 가까운 정보 질문을 `unknown`으로 볼지.
- AH11·27: `오전`을 시간 필드의 허용 문자열로 둘지. AH27은 구체적 시각이
  없으므로 `time=null`도 가능한 초안이다.
- AH13: 이동 기록 정지를 배달 지연 사실로 볼지.
- AH15: `requested_change`에 새 위치 `회사 후문`만 둘지, 원래 위치도 포함할지.
- AH17: 처리 방법 문의라 `resolution_preference=null`로 둘지.
- AH19: 수거 상태 문의 `collection_status`가 맞는지.
- AH23: `in_person`과 `documents`의 의미 방향이 맞는지.
- AH29: 화상회의가 가능한 방이라는 조건은 현재 계약에 필드가 없으므로
  정답 필드를 추가하지 않는다.

문장 후보 검수와 이 표의 행동·모든 필드·공란·허용 문자열 검수는 구분한다.
수정할 ID와 필드별 값을 알려주면 반영한다. 검수 전에 이 표를
`adjudicated` 데이터나 정확도 결과로 바꾸지 않는다.
