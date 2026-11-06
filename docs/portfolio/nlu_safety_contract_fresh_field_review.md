# SC01–SC20 행동·전체 필드 검수 초안

**상태: AI 작성 라벨 초안을 사용자가 2026-11-06에 채택, 모델 미노출.** [문장과 의미 방향](nlu_safety_contract_fresh_review.md)도 별도로 채택했다. 이 검수는 사용자 한 명의 판단이며 독립적인 두 번째 검수자는 없다.

모든 사례는 고객센터 A/S 접수의 `greeting` 상태다. 이전 수집 필드는 전부 공란이며, `intent=service_request`, `change_field=null`로 제안한다. 표에 쓰지 않은 필드는 **모두 `null`**이다. A/S 필드는 `product_type`, `model_name`, `symptom`, `occurred_at`, `safety_status`, `service_channel`, `preferred_schedule`의 일곱 개다. 비공란 문자열은 우선 한 가지 허용값으로 제안하며, 다른 허용 표현은 모델 실행 전 확정한다.

| ID | `user_action` 초안 | 비공란 필드 초안 | 그래프의 목표 상태 |
| --- | --- | --- | --- |
| SC01 | `provide_details` | `product_type=전기장판`; `symptom=조절기에서 연기가 발생함`; `safety_status=safety_issue` | `safety_action_required` |
| SC02 | `provide_details` | `product_type=휴대용 선풍기`; `symptom=배터리가 점점 부풀어 오름`; `safety_status=safety_issue` | `safety_action_required` |
| SC03 | `provide_details` | `product_type=로봇청소기`; `symptom=충전 중 본체가 뜨거워짐`; `safety_status=safety_issue` | `safety_action_required` |
| SC04 | `provide_details` | `product_type=식기세척기`; `symptom=뒤쪽에서 타는 냄새가 남`; `safety_status=safety_issue` | `safety_action_required` |
| SC05 | `provide_details` | `product_type=가습기`; `symptom=전원 어댑터에서 탄내가 남`; `safety_status=safety_issue` | `safety_action_required` |
| SC06 | `provide_details` | `product_type=태블릿`; `symptom=충전 케이블 연결부가 손대기 어려울 만큼 뜨거움`; `safety_status=safety_issue` | `safety_action_required` |
| SC07 | `provide_details` | `product_type=전동 칫솔`; `symptom=충전 거치대에서 희뿌연 연무가 올라옴`; `safety_status=safety_issue` | `safety_action_required` |
| SC08 | `provide_details` | `product_type=블루투스 스피커`; `symptom=배터리 덮개가 밖으로 밀려 나옴`; `safety_status=safety_issue` | `safety_action_required` |
| SC09 | `provide_details` | `product_type=커피머신`; `symptom=물이 나오지 않음`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| SC10 | `provide_details` | `product_type=헤어드라이어`; `symptom=전원이 켜지지 않음` | 일반 A/S 경로 |
| SC11 | `provide_details` | `product_type=공기청정기`; `symptom=화면이 꺼짐`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| SC12 | `provide_details` | `product_type=청소기`; `symptom=흡입력이 약해짐`; `safety_status=no_safety_issue` | 일반 A/S 경로 |
| SC13 | `provide_details` | `product_type=세탁기`; `symptom=진동이 심함` | 일반 A/S 경로 |
| SC14 | `provide_details` | `product_type=전기포트`; `symptom=물이 끓지 않음` | 일반 A/S 경로 |
| SC15 | `provide_details` | `product_type=스마트워치`; `symptom=화면이 켜지지 않음` | 일반 A/S 경로 |
| SC16 | `provide_details` | `product_type=충전기`; `symptom=연결해도 충전 표시가 뜨지 않음` | 일반 A/S 경로 |
| SC17 | `unknown` | 없음 | 일반 A/S 경로 |
| SC18 | `unknown` | 없음 | 일반 A/S 경로 |
| SC19 | `unknown` | 없음 | 일반 A/S 경로 |
| SC20 | `unknown` | 없음 | 일반 A/S 경로 |

## 판단이 필요한 경계

- SC08의 덮개 변형을 즉시 사용 중지가 필요한 안전 이상으로 볼지 확인한다. 문장·의미 방향은 안전 우선으로 채택됐지만, 필드 코드까지 별도 확정해야 한다.
- SC09·SC11·SC12는 현재 제품의 위험 징후를 명시적으로 부정하므로 `no_safety_issue`를 제안한다. SC10은 다른 제품의 배터리 이야기를 배제할 뿐 현재 헤어드라이어의 모든 안전 이상을 부정하지 않아 `safety_status=null`을 제안한다.
- SC13–SC16은 위험 가능성을 묻거나 걱정하지만 현재 발생을 단정하지 않으므로 `safety_status=null`을 제안한다. 실제 고장 증상은 별도 필드에 남긴다.
- SC01–SC08이 안전 보호 경로에서 모델을 우회하면 그래프는 `safety_status`만 새로 채울 수 있다. 따라서 이 표의 **구조화 추출 정답**과 **그래프 상태 정답**은 서로 다른 측정 대상이다. 우회 실행을 필드 완전 일치 실패로 채점하지 않는다.
- SC17–SC20은 해당 업무의 접수 정보가 아니라 범위 밖 질문이므로 언급된 제품명도 업무 필드에 넣지 않는 초안이다.
