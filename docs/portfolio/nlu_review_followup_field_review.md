# 리뷰 후 수정 검증: RF01–RF12 전체 필드 검토 초안

**상태:** AI가 제안한 행동 코드·전체 필드 값·공란을 사용자가 2026-11-06에 채택했다. [문장·행동 방향](nlu_review_followup_fresh_review.md)도 별도로 채택했다. 모델 미노출.

모든 사례는 해당 업무의 `greeting` 상태이며 기존 수집 필드와 대체 시간은 비어 있다. 모든 `change_field`는 `null`이다. 표에 쓰지 않은 업무 필드는 **모두 `null`**로 제안한다. 비공란 문자열은 현재 한 가지 허용값으로 제안하며, 동의어를 추가하려면 실행 전에 확정한다. 아래 정답은 실제 판매·보증·행정 정책을 판단하지 않고 발화의 구조화 의미만 다룬다.

| ID | `intent` | `user_action` 초안 | 비공란 필드 초안 |
| --- | --- | --- | --- |
| RF01 | `service_request` | `provide_details` | `symptom=배터리가 부풀어 오르고 충전할 때 뜨거워짐`; `safety_status=safety_issue` |
| RF02 | `service_request` | `unknown` | 없음 |
| RF03 | `service_request` | `provide_details` | `symptom=충전 단자에서 타는 냄새가 남`; `safety_status=safety_issue` |
| RF04 | `service_request` | `provide_details` | `product_type=공기청정기`; `symptom=연기가 남`; `safety_status=safety_issue`; `service_channel=visit` |
| RF05 | `service_request` | `provide_details` | `product_type=선풍기`; `symptom=회전 버튼이 눌리지 않음` |
| RF06 | `service_request` | `unknown` | 없음 |
| RF07 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=대학원 연구 주제 상의`; `date=이번 주 금요일`; `time=오전 11시` |
| RF08 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=졸업 작품 방향 상담`; `date=다음 주 월요일`; `time=오후 2시`; `user_name=박서연` |
| RF09 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=실습 과목 선택 상의` |
| RF10 | `appointment_booking` | `unknown` | 없음 |
| RF11 | `appointment_booking` | `provide_appointment_info` | `date=다음 주 목요일`; `time=오전 10시` |
| RF12 | `appointment_booking` | `provide_appointment_info` | `appointment_purpose=교환학생 복학 후 수강 계획 상의`; `user_name=이도현` |

## 특히 확인할 판단

- RF01·RF03은 주된 구매·보증 문의가 A/S 접수 범위 밖이지만, 발화에 안전 이상이 있으므로 `provide_details`와 안전 필드만 남기는 초안이다. 제품 유형이 언급돼도 범위 밖 요청에 딸린 정보라 `product_type=null`, 접수 방식도 `null`로 제안한다.
- RF04의 “점검이 필요하면 서비스센터에 가져가겠습니다”를 방문 희망으로 보아 `service_channel=visit`로 제안한다. 조건부 표현이므로 공란으로 두는 판단도 검토 대상이다.
- RF05의 수리 접수 **방법 문의**는 현재 A/S 진행 의사를 함께 나타낸다고 보고 `provide_details`로 제안했다. 접수 방식은 선택하지 않았으므로 공란이다.
- RF08의 학과·학번은 `user_name`에 합치지 않고 명시된 이름 `박서연`만 제안한다.
- RF11은 면담 일시는 말했지만 주제와 이름은 말하지 않아 `appointment_purpose=null`, `user_name=null`로 제안한다.

이 표는 사용자 한 명의 검수를 거쳤다. 독립적인 두 번째 검수자는 없으며, 데이터·실행 프로토콜을 별도로 동결하기 전에는 모델을 실행하지 않는다.
