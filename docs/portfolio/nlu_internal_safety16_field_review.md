# SS01–SS16 A/S 안전 표본: 행동·전체 필드 검수 기록

> **실모델 실행 전 사용자 1인 전체 필드 검수 기록.** 사용자가 [발화와 대상·위험 방향](nlu_internal_safety16_draft.md), 행동, 모든 필드 값·공란, SS15·SS16 교체안, SS13 `safety_status=null`을 채택했다. 이후 데이터를 동결하고 원문 재검사와 [실모델 평가](nlu_internal_test80_verified_result.md)를 완료했다. 모두 가상 사례다.

## 공통 계약과 읽는 법

- 모든 사례의 `scenario_key=고객센터:a/s 접수`, `conversation_state=greeting`, `current_fields={"product_type":null,"model_name":null,"symptom":null,"occurred_at":null,"safety_status":null,"service_channel":null,"preferred_schedule":null}`이다. 모델 입력에 이전 대화는 없다.
- 아래 모든 행의 `intent=service_request`, `user_action=provide_details`, `change_field=null`이다. 각 행은 추출 결과의 **일곱 필드를 빠짐없이** 표시한다. 문자열은 현재 발화에서만 확인한 사용자 검수 정규화 값이다.
- `예상 그래프 상태`는 현행 `SERVICE_REQUEST_SPEC`의 `safety_status=safety_issue` 가드와 필드 충족 조건을 기준으로 한다. 현재 서비스에는 `confirming_safety_status` 상태가 없다. 따라서 위험 출처·발생 여부가 불확실한 SS05–SS08은 별도 분석 차원에서 **안전 확인 필요**지만, 현행 서비스 그래프 예상 상태는 `collecting_service_request`다. 이 상태가 적절한 안전 안내를 제공한다는 뜻은 아니다.
- `safety_status=null`은 현재 접수 제품의 위험이 **없다는 판정이 아니다**. 위험이 다른 물건에서 일어났거나, 현재 물건에서 일어났는지 확정되지 않은 경우에도 공란을 유지한다. SS13은 침수만 부정해 다른 안전 이상의 부재를 단정할 수 없으므로 공란이다. `no_safety_issue`는 해당 제품에서 다른 안전 이상도 없다고 명시된 SS15·SS16 등에 채택했다.

## 현재 접수 제품에서 관찰된 위험: SS01–SS04

| ID | `product_type` | `model_name` | `symptom` | `occurred_at` | `safety_status` | `service_channel` | `preferred_schedule` | 예상 그래프 상태 | 판단 근거 |
|---|---|---|---|---|---|---|---|---|---|
| SS01 | `가정용 제빙기` | `null` | `얼음을 만들다 멈춤; 물통 아래로 샌 물이 전원 소켓에 닿아 차단기가 내려감` | `null` | `safety_issue` | `null` | `null` | `safety_action_required` | 제빙기의 물통·소켓에서 누수와 차단기 동작을 관찰했다. `사용하던 중`은 최초 발생 시점이 아니다. |
| SS02 | `전동 재봉틀` | `null` | `바늘땀을 놓침; 바늘 고정 나사가 풀려 바늘이 튀어 손등에 박힘` | `null` | `safety_issue` | `null` | `null` | `safety_action_required` | 재봉틀 부품이 튀어 신체 손상이 발생했다. `사용 중`은 발생 시점의 날짜·반복 여부가 아니다. |
| SS03 | `로봇 잔디깎이` | `null` | `충전되지 않음; 본체 배터리실에서 누런 액체가 흘러나옴` | `null` | `safety_issue` | `null` | `null` | `safety_action_required` | 액체는 접수 제품의 배터리실에서 실제 누출됐다. 성분을 배터리 전해액으로 단정하지 않는다. |
| SS04 | `휴대용 공기압 주입기` | `null` | `압력 표시 불가; 주입기 호스 연결부가 터져 조각이 손에 튐` | `null` | `safety_issue` | `null` | `null` | `safety_action_required` | 호스 연결부는 접수하려는 주입기의 부위이며 파열·신체 위험이 실제 발생했다. |

## 발생 여부·출처가 불확실함: SS05–SS08

| ID | `product_type` | `model_name` | `symptom` | `occurred_at` | `safety_status` | `service_channel` | `preferred_schedule` | 예상 그래프 상태 | 판단 근거 |
|---|---|---|---|---|---|---|---|---|---|---|
| SS05 | `전기 그릴` | `null` | `온도 조절 불가; 손잡이 안쪽에 작은 돌기가 생김` | `null` | `null` | `null` | `null` | `collecting_service_request` | 돌기는 관찰됐지만 열 변형인지 보호 비닐 들뜸인지 불명확하다. **안전 확인 필요**. |
| SS06 | `휴대용 발전기` | `null` | `시동이 걸리지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 휘발유 냄새는 관찰됐지만 발전기와 별도 기름통 중 출처가 불명확하다. 냄새를 발전기 증상으로 옮기지 않는다. **출처 확인 필요**. |
| SS07 | `자동 젖병 소독기` | `null` | `버튼이 눌리지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 소독 후 손잡이 열감은 정상 잔열인지 이상 발열인지 구분되지 않는다. **안전 확인 필요**. |
| SS08 | `스팀다리미` | `null` | `물이 분사되지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 검은 가루의 원인이 전선 피복인지 다림판 보풀인지 불명확하다. 피복 손상을 확정하지 않는다. **손상 확인 필요**. |

## 위험이 다른 제품·물건에서 발생함: SS09–SS12

| ID | `product_type` | `model_name` | `symptom` | `occurred_at` | `safety_status` | `service_channel` | `preferred_schedule` | 예상 그래프 상태 | 판단 근거 |
|---|---|---|---|---|---|---|---|---|---|
| SS09 | `블루투스 턴테이블` | `null` | `회전 속도가 일정하지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 불은 다른 작업대의 납땜 인두·종이에서 났다. 턴테이블의 위험이나 안전을 확정하지 않는다. |
| SS10 | `휴대용 번역기` | `null` | `화면이 깨짐` | `null` | `null` | `null` | `null` | `collecting_service_request` | 동생이 쓰는 같은 모델의 케이블 사고는 현재 접수 제품의 사고가 아니다. 전언으로 현재 제품의 안전을 단정하지 않는다. |
| SS11 | `스마트 화분 센서` | `null` | `흙 습도를 잘못 표시함` | `null` | `null` | `null` | `null` | `collecting_service_request` | 액체는 떨어진 선반의 살충제 통에서 흘렀다. 센서의 누출로 옮기지 않는다. |
| SS12 | `차량용 블랙박스` | `null` | `주행 영상이 저장되지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 터진 것은 차량 냉각수 호스이며 블랙박스 부품이 아니다. 블랙박스의 위험을 확정하지 않는다. |

## 가정·부정 또는 미발생: SS13–SS16

| ID | `product_type` | `model_name` | `symptom` | `occurred_at` | `safety_status` | `service_channel` | `preferred_schedule` | 예상 그래프 상태 | 판단 근거 |
|---|---|---|---|---|---|---|---|---|---|
| SS13 | `자외선 살균함` | `null` | `문 센서가 작동하지 않음` | `null` | `null` | `null` | `null` | `collecting_service_request` | 배선 침수는 가정이고 현재 제품은 물에 닿은 적이 없다고 명시한다. 다른 안전 이상 전체의 부재를 입증하지 못해 공란이다. |
| SS14 | `차량용 무선 충전기` | `null` | `충전이 자주 끊김` | `null` | `no_safety_issue` | `null` | `null` | `collecting_service_request` | 검은 줄은 원래 무늬이고 만져도 뜨겁지 않다고 명시한다. |
| SS15 | `전동 와인 오프너` | `null` | `버튼을 눌러도 회전하지 않음` | `null` | `no_safety_issue` | `null` | `null` | `collecting_service_request` | 스크루 변형을 걱정해 확인했지만 실제 변형이나 다른 안전 이상은 없다고 명시한다. |
| SS16 | `음식물 처리기` | `null` | `뚜껑 버튼이 고장 남` | `null` | `no_safety_issue` | `null` | `null` | `collecting_service_request` | 칼날이 밖으로 드러나지 않았고 다른 안전 이상도 없다고 명시한다. |

## 사용자 검수로 확정한 판단과 평가 경계

1. **SS03·SS04:** 배터리실의 액체 누출과 주입기 호스 파열을 각각 현재 제품의 직접 위험으로 보고 `safety_issue`를 채택했다. SS03의 액체 성분은 라벨에 넣지 않았다.
2. **SS05–SS08:** 현행 그래프는 확인 전용 상태가 없으므로 `safety_status=null`을 추출해도 일반 수집 상태로 간다. 이 네 건의 별도 현장 안전 안내 적절성은 이번 정답에 포함하지 않았다. 현재 서비스가 그 안내를 제공한다고 주장하지 않는다.
3. **SS09·SS11·SS12:** 다른 물건에서 실제 화재·화학물질 누출·차량 고장이 발생했다. **접수 제품의 안전 경로**와 **현장 전체에 대한 안전 안내**는 별개의 책임이다. 이 테스트의 필드·그래프 정답은 전자만 다룬다. 현장 안내의 적절성은 이번 정답에 포함하지 않았다.
4. **SS13–SS16:** SS13은 특정 침수만 부정해 안전 필드를 공란으로 확정했다. SS14–SS16의 명시된 위험 미발생은 `no_safety_issue`로 채택했다. SS15·SS16은 이전 노출과 가까운 문장을 교체해 검수했다.
5. **실행 전 검수 당시 판단:** 사용자 행동·일곱 필드의 값과 공란 검수를 끝냈고, 원본 중복·계약 검증 뒤에 동결·실행하기로 했다. 당시에는 안전 성능 수치가 없었다. 이후 검증한 수치와 해석은 [내부 평가 결과](nlu_internal_test80_verified_result.md)에 기록했다.
