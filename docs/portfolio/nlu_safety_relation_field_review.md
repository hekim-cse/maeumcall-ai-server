# RE01–RE16 제품·위험 관계 필드 검토 초안

[문장과 기대 경로](nlu_safety_relation_fresh_review.md)는 사용자가 2026-11-09에 탐색용으로 채택했다. 이 표는 **아직 검수받지 않은** 모델 출력 정답 초안이다. `product_index`는 접수 대상 제품을 식별하는 문장, `hazard_index`는 위험 사건이 언급된 문장이다. 두 번호는 원문 문장 순서다. `target_relation`과 `event_status`의 값은 [고정된 후보 계약](../../scripts/probe_as_safety_relation.py)을 따른다.

| ID | product_index | hazard_index | target_relation | event_status | 판단 근거 |
| --- | ---: | ---: | --- | --- | --- |
| RE01 | 1 | 2 | `current` | `observed` | 믹서기를 접수하며 작동 중 번쩍임과 소리를 보고 |
| RE02 | 1 | 2 | `current` | `observed` | 접수 제품의 콘센트 쪽 플라스틱이 녹았다고 보고 |
| RE03 | 1 | 2 | `current` | `observed` | 전동 칫솔 손잡이에서 전기 자극을 느꼈다고 보고 |
| RE04 | 1 | 2 | `current` | `observed` | 소형 냉장고 뒤쪽의 연무를 직접 보고 |
| RE05 | 1 | 2 | `current` | `uncertain` | 뜨겁게 느껴졌지만 착각일 수 있다고 표현 |
| RE06 | 1 | 2 | `current` | `uncertain` | 누수인지 청소하며 흘린 물인지 불명확 |
| RE07 | 1 | 2 | `unknown` | `uncertain` | 냄새 자체와 모니터·멀티탭 중 출처가 불명확 |
| RE08 | 1 | 2 | `current` | `uncertain` | 내부 빛이 불꽃인지 표시등 반사인지 불명확 |
| RE09 | 1 | 2 | `other` | `observed` | 연기는 접수 대상 TV가 아닌 멀티탭에서 발생 |
| RE10 | 1 | 2 | `other` | `uncertain` | 친구 제품의 사고를 전해 들었고 직접 관찰한 것은 아님 |
| RE11 | 1 | 2 | `other` | `observed` | 탄 냄새는 접수 세탁기가 아닌 욕실 전등에서 발생 |
| RE12 | 1 | 2 | `other` | `nonoccurring` | 설명서의 화재 사례이며 현재 태블릿에서 발생하지 않음 |
| RE13 | 1 | 1 | `current` | `nonoccurring` | 청소기의 탄 냄새를 명시적으로 부정 |
| RE14 | 1 | 2 | `current` | `nonoccurring` | 전기포트의 미래 스파크를 가정한 질문 |
| RE15 | 1 | 2 | `current` | `nonoccurring` | 현재 팽창 보고 없이 충전 케이스의 가능성만 질문 |
| RE16 | 1 | 2 | `current` | `nonoccurring` | 불꽃처럼 보인 것은 제품 사진의 조명 효과 |

검수할 때 특히 **RE07**의 `product_index=1`은 접수 제품을 식별하는 근거일 뿐 위험의 출처를 확정하지 않는다는 점, **RE10**의 전언을 `uncertain`으로 둔 점, **RE12**의 설명서 사례를 `other + nonoccurring`으로 둔 점, **RE13**의 두 근거가 모두 첫 문장인 점을 확인해야 한다. 요청 후속 조치의 불확실성은 위험 사건의 불확실성과 구분한다.

검수 전에는 이 표를 정답으로 확정하거나 모델에 실행하지 않는다. 확정 후에도 AI 작성·1인 검수 표적 탐색으로만 사용한다.
