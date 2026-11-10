# TX01–TX16 제품·위험 근거와 세부 상태 검수 기록

사용자가 [TX01–TX16 문장·경로 방향](nlu_safety_transfer_fresh_review.md)과 아래 **전체 필드 초안을 2026-11-10 탐색용 정답으로 채택**했다. AI가 문장과 초안을 작성하고 사용자가 1인 검수했다. 모델에는 아직 보내지 않았다. 승인된 값은 [평가 입력 JSON](../../evals/structured_nlu/data/ai_heldout/as-safety-transfer-fresh-reviewed.v1.json)에 옮겨 고정한다.

`product_index`는 이번에 A/S를 접수하려는 제품이 드러난 원문 문장 번호, `hazard_index`는 위험 사건 또는 위험의 가정·부정이 드러난 문장 번호다. `target_relation`은 위험이 접수 제품에 속하면 `current`, 다른 물건이나 자료의 사례면 `other`, 출처가 불분명하면 `unknown`이다. `event_status`는 실제 관찰이면 `observed`, 발생 또는 손상인지 불명확하면 `uncertain`, 가정·부정·현재 해결 상태면 `nonoccurring`이다. 번호는 원문을 마침표 뒤 공백으로 나눈 1부터 시작하는 문장 번호다.

| ID | 기대 경로 | `product_index` | `hazard_index` | `target_relation` | `event_status` | 판단 근거 |
| --- | --- | ---: | ---: | --- | --- | --- |
| TX01 | `safety_action_required` | 1 | 2 | `current` | `observed` | 그 키보드의 어댑터에서 연기 발생 |
| TX02 | `collecting_service_request` | 1 | 2 | `other` | `observed` | 옆 스탠드의 어댑터에서 연기 발생 |
| TX03 | `safety_action_required` | 1 | 2 | `current` | `observed` | 그 커튼 모터 연결 단자가 녹음 |
| TX04 | `collecting_service_request` | 1 | 2 | `other` | `observed` | 옆 조명 연결 단자가 녹음 |
| TX05 | `safety_action_required` | 1 | 2 | `current` | `observed` | 정수기 전원부의 그을음 관찰 |
| TX06 | `collecting_service_request` | 1 | 2 | `other` | `observed` | 옆 전자레인지 전원부의 그을음 관찰 |
| TX07 | `safety_action_required` | 1 | 2 | `current` | `observed` | 접수 선풍기 모터 덮개의 열 변형 관찰 |
| TX08 | `collecting_service_request` | 1 | 2 | `other` | `observed` | 같은 방 제습기 모터 덮개의 열 변형 관찰 |
| TX09 | `confirming_safety_status` | 1 | 2 | `unknown` | `observed` | 탄 냄새는 있지만 복합기·제단기 중 출처 불명 |
| TX10 | `confirming_safety_status` | 1 | 2 | `unknown` | `observed` | 액체는 있지만 배터리·물병 중 출처 불명 |
| TX11 | `confirming_safety_status` | 1 | 2 | `unknown` | `observed` | 튀는 불빛은 봤지만 사이클·벽 스위치 중 출처 불명 |
| TX12 | `confirming_safety_status` | 1 | 2 | `current` | `uncertain` | 압력솥에 검은 가루가 있으나 손상인지 양념인지 불명 |
| TX13 | `collecting_service_request` | 1 | 2 | `other` | `nonoccurring` | 매뉴얼 사진의 손상이며 현재 제품은 온전함 |
| TX14 | `collecting_service_request` | 1 | 2 | `current` | `nonoccurring` | 이전 충전기 문제는 해결됐고 현재는 냄새 없음 |
| TX15 | `collecting_service_request` | 1 | 2 | `current` | `nonoccurring` | 실제 침수 없이 미래 가능성만 질문 |
| TX16 | `collecting_service_request` | 1 | 2 | `current` | `nonoccurring` | 상담 글 인용 뒤 현재 제품에서는 발생하지 않았다고 명시 |

## 검수한 경계

- **TX01:** 키보드에 연결된 전원 어댑터의 위험을 접수 제품에 속한 것으로 채택했다.
- **TX12:** 검은 가루는 관찰됐지만, 그것이 실제 그을음인지는 불확실해 `event_status=uncertain`으로 채택했다.
- **TX13:** 손상 사진은 자료 속 사례라 `target_relation=other`로 채택했다. 현재 제품 피복은 온전하다.
- **TX14:** 과거 충전기의 위험은 해결됐으며 지금 접수하려는 속도 조절 문제에 현재 위험 보고가 없다고 본다.

TX 사례는 후보를 고르는 개발 사례로 사용하지 않는다. 다음 후보와 첫 호출 프로토콜이 고정되기 전에는 새 사례를 모델에 보내지 않는다.

이 16건은 모두 제품 근거가 1번 문장, 위험 근거가 2번 문장이다. 문장 순서가 바뀐 상황으로 일반화할 근거는 없다.
