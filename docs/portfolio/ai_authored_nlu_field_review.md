# AI 작성 새 발화의 전체 정답 초안 검토표

**상태:** AI 제안에 대해 사용자가 전체 정답 방향을 채택, Q4·Q5 미실행. 대응 발화는
[AH01–AH32 문장 후보](ai_authored_nlu_heldout_review.md)다. 아래 표에서
적지 않은 업무 필드는 모두 `null`로 제안한다. 모든 사례의 대화 상태는
`greeting`, 이전 필드는 비어 있으며, 예약 대체 시간도 없다. 모든
`change_field`는 `null`이다. 검수 결정은
[검수 원장](../../evals/structured_nlu/data/ai_heldout/ai-heldout-review-ledger.v1.json)에
기록했다. 이는 모델 실행 허가나 정확도 결과가 아니다.

기계 검증 가능한 [JSON 초안](../../evals/structured_nlu/data/ai_heldout/ai-heldout-draft.v1.json)은
이 표와 문장을 옮긴 것이다. 초안은 `review_status=draft`라 검수 관문을
통과하지 못한다. [검수본](../../evals/structured_nlu/data/ai_heldout/ai-heldout-reviewed.v1.json)은
같은 32건의 상태·행동·전체 필드·공란·허용값을 사용자가 채택한 뒤
`adjudicated`로 기록한 별도 파일이다. 실제 검수 주체는 사용자 한 명이다.

사용자는 AH02·04·06·08·10·12·14·16·18·20·22·24·26·28·30·32의
요청 의미를 아래처럼 설명했고, **현행 계약 평가에서 `unknown`·업무 필드
공란으로 두되 의미 라벨을 별도로 기록**하는 기준을 채택했다. 이 합의는
해당 16건의 행동·업무 필드 방향에 관한 것이며 나머지 정보 제공 16건의
전체 정답 검수까지 끝났다는 뜻은 아니다.

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

## 요청 의미 라벨과 서비스 행동 코드

사용자는 아래 16건의 실제 요청 의미를 구체적으로 제안했다. 이 설명은
`unknown`이 “발화의 뜻을 모른다”는 의미가 아님을 보여 준다. 현재 해당
업무 그래프에는 이 요청을 수행하는 별도 `user_action`이나 추출 필드가 없다.
따라서 아래의 자연어 의미 라벨은 **분석용 보조 라벨**이며, 위 표의 구조화
출력 정답이나 전체 일치율 분자에 새 항목으로 추가하지 않는다. 사용자는
현행 계약으로 평가하고 의미 라벨을 별도로 기록하기로 결정했다.

| ID | 사용자 제안 요청 의미 |
| --- | --- |
| AH02 | 무상보증 기간 확인 방법 요청 |
| AH04 | 회선 명의 이전 방법 요청 |
| AH06 | 공유기 관리자 비밀번호 변경 방법 요청 |
| AH08 | 다음 주 수업의 온라인 진행 여부 확인 요청 |
| AH10 | 학과 세미나 신청 링크 위치 확인 요청 |
| AH12 | 학부생 연구 참여 모집 여부 확인 요청 |
| AH14 | 다음 주문의 배달 알림 소리 끄는 방법 요청 |
| AH16 | 배달 봉투 스티커의 분리배출 방법 요청 |
| AH18 | 일회용 용기 반납 가능 여부 확인 요청 |
| AH20 | 폐형광등을 가져갈 장소 확인 요청 |
| AH22 | 해외에서 여권을 분실했을 때 대사관 신고 방법 요청 |
| AH24 | 가족관계증명서 발급 장소 확인 요청 |
| AH26 | 염색 후 펌 가능 기간 확인 요청 |
| AH28 | 증상에 따라 응급실에 가야 하는지 상담 요청 |
| AH30 | 이미 예약한 방의 화이트보드 유무 확인 요청 |
| AH32 | 아이가 먹을 수 있는 맵지 않은 메뉴 확인 요청 |

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
사용자는 2026-11-06에 정보 제공 16건의 행동·필드·공란·허용값 초안을
채택했다. 향후 정답을 수정하면 기존 검수본과 결과를 덮어쓰지 않고 새 버전으로
기록한다. 현재 문서는 정확도 결과가 아니다.
