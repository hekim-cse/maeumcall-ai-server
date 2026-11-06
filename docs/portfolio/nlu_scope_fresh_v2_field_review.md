# 신규 업무 범위 평가 정답 필드 검토 초안

**상태:** AI가 제안한 전체 정답을 사용자가 2026-11-06에 채택했다.
모델 미노출.
[NS01–NS32 발화](nlu_scope_fresh_v2_review.md)의 문장과 업무 안/범위 밖
방향은 사용자가 채택했다. 아래 표의 값·공란·허용 문자열도 채택됐다.

모든 사례는 해당 업무 그래프의 `greeting` 상태이며 이전 수집 필드와 대체
시간은 비어 있다. 모든 `change_field`는 `null`이다. 아래에 적지 않은 업무
필드는 모두 `null`로 제안한다. 각 비공란 값은 현재 한 가지 허용 문자열로
제안하며, 평가 전에 다른 허용 표현을 추가하려면 이 표에서 확정해야 한다.

| ID | `intent` | `user_action` | 비공란 필드 제안 |
| --- | --- | --- | --- |
| NS01 | `service_request` | `provide_details` | `product_type=가습기`; `symptom=물통을 채우면 아래쪽으로 물이 샘`; `service_channel=parcel` |
| NS02 | `service_request` | `unknown` | 없음 |
| NS03 | `plan_contract_consultation` | `provide_details` | `inquiry_type=plan_change`; `consultation_goal=통화 제공량이 적은 요금제로 변경 후 월 요금 확인` |
| NS04 | `plan_contract_consultation` | `unknown` | 없음 |
| NS05 | `network_call_issue` | `provide_details` | `service_type=wifi`; `symptom=와이파이에 연결되지만 웹페이지가 열리지 않음`; `scope=multiple_devices`; `next_action=remote_check` |
| NS06 | `network_call_issue` | `unknown` | 없음 |
| NS07 | `absence_notice` | `provide_absence_info` | `class_name=통계학 수업`; `absence_date=이번 주 목요일`; `absence_reason=대회 참가 일정과 겹침` |
| NS08 | `absence_notice` | `unknown` | 없음 |
| NS09 | `assignment_inquiry` | `provide_assignment_info` | `course_name=컴퓨터비전`; `assignment_topic=영상 파일`; `question=영상 파일에 용량 제한이 있는지` |
| NS10 | `assignment_inquiry` | `unknown` | 없음 |
| NS11 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=교환학생 지원 계획 상의`; `date=다음 주 화요일`; `time=오후 4시` |
| NS12 | `appointment_booking` | `unknown` | 없음 |
| NS13 | `delivery_delay_inquiry` | `provide_details` | `order_number=J-562`; `delay_detail=예상 도착 시각이 지났지만 아직 배차 전` |
| NS14 | `delivery_delay_inquiry` | `unknown` | 없음 |
| NS15 | `delivery_order_change` | `provide_details` | `order_number=K-731`; `change_type=menu_option`; `requested_change=치즈 추가 옵션` |
| NS16 | `delivery_order_change` | `unknown` | 없음 |
| NS17 | `delivery_refund_redelivery` | `provide_details` | `order_number=R-864`; `issue_type=not_received`; `issue_detail=배달 완료로 표시되지만 음식을 찾지 못함`; `resolution_preference=redelivery` |
| NS18 | `delivery_refund_redelivery` | `unknown` | 없음 |
| NS19 | `bulky_waste_guidance` | `provide_details` | `region=창원 성산구`; `item_name=2인용 소파`; `quantity=한 개`; `request_topic=place_and_schedule` |
| NS20 | `bulky_waste_guidance` | `unknown` | 없음 |
| NS21 | `passport_guidance` | `provide_details` | `application_type=first_issue`; `applicant_type=adult_self`; `inquiry_topic=processing_time` |
| NS22 | `passport_guidance` | `unknown` | 없음 |
| NS23 | `resident_certificate_guidance` | `provide_details` | `document_type=register_copy`; `applicant_relation=self`; `issuance_channel=kiosk`; `inquiry_topic=documents` |
| NS24 | `resident_certificate_guidance` | `unknown` | 없음 |
| NS25 | `reservation` | `continue_collecting` | `date=다음 주 토요일`; `time=오후 1시`; `service_type=뿌리 염색` |
| NS26 | `reservation` | `unknown` | 없음 |
| NS27 | `reservation` | `continue_collecting` | `department=이비인후과`; `date=이번 주 금요일`; `time=오후 5시` |
| NS28 | `null` | `unknown` | 없음 |
| NS29 | `reservation` | `continue_collecting` | `date=다음 주 목요일`; `start_time=오후 4시`; `duration=세 시간`; `party_size=다섯 명` |
| NS30 | `reservation` | `unknown` | 없음 |
| NS31 | `reservation` | `continue_collecting` | `date=다음 주 수요일`; `time=오후 7시`; `party_size=여섯 명` |
| NS32 | `reservation` | `unknown` | 없음 |

검수 초점:

- NS13의 “언제 출발하나요?”는 현재 `inquiry_goal` 허용 코드인 도착 예상,
  지연 이유, 현재 위치 중 어느 것도 정확히 뜻하지 않아 `null`로 제안했다.
- NS17의 “재배달을 요청합니다”는 가능 여부 질문이 아니라 명시적 희망
  조치이므로 `resolution_preference=redelivery`로 제안했다.
- NS19의 배출일 지정 방법 질문을 `place_and_schedule`로 볼지 확인이 필요하다.
- NS23의 준비물 질문은 `inquiry_topic=documents`로 제안했다. 실제
  무인발급 정책의 사실 여부는 이 구조화 라벨의 근거로 사용하지 않는다.

이 표의 정답은 사용자 검수를 거쳤다. AI 작성 발화이며 독립적인 두 번째
검수자는 없었다. 모델 실행 전 기계 판독 데이터와 해시를 별도로 고정한다.
