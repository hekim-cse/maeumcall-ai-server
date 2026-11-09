# V01–V16 제품·위험 관계 전체 필드 검토 초안

[문장·기대 경로](nlu_safety_relation_v2_fresh_review.md)는 사용자가 2026-11-09에 탐색용으로 채택했다. 이 표의 **근거 번호·관계·발생·함의 정답도 같은 날 탐색용으로 채택**했다. `product_index`와 `hazard_index`는 원문 문장 번호다. `target_relation`은 접수 제품과 위험의 관계, `event_status`는 위험의 실제 발생 여부다. 새 [함의 후보 계약](../../scripts/probe_as_safety_entailment_v2.py)의 `claim`/`reason`도 함께 검수했다. V 사례는 아직 모델에 보내지 않았다. 먼저 노출된 RE 사례의 [함의 후보 개발 점검](nlu_safety_entailment_exposed_development_result.md)에서 후보를 미채택했으므로, 이 표의 검수만으로 모델을 실행하지 않는다.

| ID | 제품 근거 | 위험 근거 | 관계 | 발생 | 함의 주장 | 이유 | 기대 경로 |
| --- | ---: | ---: | --- | --- | --- | --- | --- |
| V01 | 1 | 2 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V02 | 1 | 2 | `other` | `observed` | `contradicted` | `other_source` | 일반 수집 |
| V03 | 1 | 2 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V04 | 1 | 2 | `other` | `observed` | `contradicted` | `other_source` | 일반 수집 |
| V05 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V06 | 1 | 2 | `other` | `observed` | `contradicted` | `other_source` | 일반 수집 |
| V07 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V08 | 1 | 2 | `other` | `observed` | `contradicted` | `other_source` | 일반 수집 |
| V09 | 1 | 1 | `unknown` | `observed` | `uncertain` | `uncertain` | 안전 확인 |
| V10 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V11 | 1 | 1 | `other` | `nonoccurring` | `contradicted` | `nonoccurring` | 일반 수집 |
| V12 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V13 | 1 | 1 | `current` | `nonoccurring` | `contradicted` | `nonoccurring` | 일반 수집 |
| V14 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |
| V15 | 1 | 1 | `current` | `nonoccurring` | `contradicted` | `nonoccurring` | 일반 수집 |
| V16 | 1 | 1 | `current` | `observed` | `entailed` | `same_product_observed` | 즉시 보호 |

V09는 **탄 냄새 발생은 관찰**됐지만 어느 제품의 현상인지 모른다는 판단이다. V11은 설명서의 가능성이 현재 청소기에서 발생했다는 뜻이 아니므로 `other + nonoccurring`이다. V05·V07의 뒤따르는 수리 가능 여부 질문은 앞서 보고한 위험 발생을 취소하지 않는다.
