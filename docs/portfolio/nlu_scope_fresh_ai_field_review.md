# 새 범위 판단 탐색 사례 F01–F32: 필드 값 검토표

**작성 당시 상태: AI 작성 정규화 필드 초안, 2026-11-05 사용자 탐색용
검토·수정, 모델 실행 전.** 이후 실행한 [탐색 결과](nlu_scope_fresh_ai_findings.md)를
별도로 기록했다. 실행 보고서의 검토표 지문은 실행 당시 커밋 `9ec6797`의
이 문서를 가리킨다. 사용자가 문장과
행동 방향을 탐색용으로 채택한 [발화 32건](nlu_scope_fresh_ai_review.md)의
범위 안 16건에 대해서만 현재 턴 필드 값을 제안한다. 범위 밖 짝수 ID는
`unknown`과 모든 업무 필드 `null`로 제안한다. 이 표의 값과 공란은
[JSON 초안](../../evals/structured_nlu/data/exploratory/fresh-scope-ai-field-draft-2026-11-05.json)에
대응하며, 라이브 계약 형식 검사도 통과했다. 사용자는 F17의 재배달 희망과 F29의
날짜 공란을 수정했고 나머지 제안은 탐색용으로 채택했다. 정답 확정이나 공식
평가가 아니다.

| ID | AI가 제안한 현재 턴 필드 값 | 검토할 공란·판단 |
| --- | --- | --- |
| F01 | `product_type=무선 청소기`, `symptom=모터에서 덜컹거리는 소리가 나고 몇 분 뒤 전원이 꺼짐` | 발화에 안전 이상 여부가 없어 `safety_status=null` |
| F03 | `inquiry_type=discount`, `current_service=인터넷 결합`, `consultation_goal=약정과 할인 조건 확인` | 청구서에도 언급하지만 주된 상담 주제를 할인으로 분류 |
| F05 | `service_type=voice_call`, `symptom=통화가 자꾸 끊김`, `scope=specific_location` | 특정 장소는 엘리베이터. 별도 위치 필드는 없음 |
| F07 | `class_name=운영체제`, `absence_date=금요일`, `absence_reason=수술 후 진료 예약` | `user_name=null` |
| F09 | `course_name=알고리즘`, `assignment_topic=PDF 제출 마감 시각`, `question=금요일 자정인지 확인` | 금요일 자정은 확인을 구하는 내용이며 확정된 마감 사실은 아님 |
| F11 | `appointment_purpose=장학금 지원 방향 상담`, `date=수요일`, `time=오후` | **시간이 모호함:** `오후`를 추출할지 `time=null`로 둘지 판단 필요 |
| F13 | `delay_detail=예상 도착 시각이 30분 지났는데 배달 상태가 이동 중`, `inquiry_goal=estimated_arrival` | 주문번호·희망 조치는 언급되지 않아 공란 |
| F15 | `change_type=menu_option`, `requested_change=세트 음료를 콜라에서 사이다로 변경` | 주문번호가 없어 `order_number=null` |
| F17 | `issue_type=damaged_or_quality`, `issue_detail=음료 뚜껑이 열려 내용물이 모두 쏟아짐`, `resolution_preference=redelivery` | 사용자는 질문형 표현을 재배달 희망으로 판단했다. 증빙 언급 없어 `evidence_status=null` |
| F19 | `region=수원시`, `item_name=부서진 사무용 의자`, `quantity=1개`, `request_topic=fee` | 수수료 문의이며 실제 수수료 액수는 추출하지 않음 |
| F21 | `application_type=reissue`, `inquiry_topic=documents` | 분실자의 나이·신청 주체가 명시되지 않아 `applicant_type=null` |
| F23 | `document_type=register_copy`, `inquiry_topic=delivery` | **발급 경로:** “집에서 온라인”만으로 `issuance_channel=government24`를 확정할지 판단 필요. 현재는 `null` |
| F25 | `date=내일`, `time=오전 11시`, `service_type=커트` | 디자이너·이름은 공란 |
| F27 | `department=소아과`, `date=월요일`, `time=오후 2시` | 예약자 이름은 공란 |
| F29 | `start_time=오전 10시`, `duration=2시간`, `party_size=2명` | 사용자는 `평일`을 특정 날짜로 추출하지 않고 `date=null`로 두어 다시 묻기로 했다. 현재 예약 응답 정책은 부족한 날짜와 예약자 이름을 함께 묻는다 |
| F31 | `date=일요일`, `time=오후 6시`, `party_size=5명` | 예약자 이름은 공란 |

사용자의 검토는 AI 초안의 탐색용 의미 방향에 한정된다. 출처는 계속
`ai_assisted_unreviewed`이며 공식 `human_authored` test가 되지 않는다. F11의
`time=오후`와 F23의 온라인 발급 경로 공란은 사용자가 수정 없이 채택한 탐색용
초안이다. 실제 서비스 판단이나 공식 정답으로 일반화하지 않는다.
