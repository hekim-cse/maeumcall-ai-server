# A/S 안전 관계 계약 오류 재발 진단 결과

2026-11-11에 [사전 고정 프로토콜](../../evals/structured_nlu/data/ai_heldout/as-safety-typed-relation-diagnostic-protocol.v1.json)과 커밋 `98650f2`로 기존 후보·Q5·요청 조건을 고정한 뒤, 이미 노출된 RE·V 32건을 후보에만 다시 한 번 실행했다. [새 저널](../../evals/structured_nlu/data/ai_heldout/as-safety-typed-relation-diagnostic-result.v1.jsonl)은 65줄이며 SHA-256은 `0a54c0b0c79d53c332229cab0f406fdce1894d1ad52eecaf234338cd0174dfee`다. 응답 원문과 예외 문구는 저장하지 않았다. TX와 서비스 그래프는 사용하지 않았다.

| 새 실행 결과 | 건수 |
| --- | ---: |
| 유효한 경로 | 4/32 |
| 사건 또는 발생 근거 번호 누락 | 26/32 |
| 접수 제품 근거 번호 누락 | 2/32 |

[독립 검증기](../../scripts/verify_as_safety_typed_relation_diagnostic.py)는 고정 입력 해시, 32건의 순서, 제한된 저널 필드, 성공 경로와 집계를 재계산해 통과했다. 원문을 보존하지 않으므로 **실패 이유 코드의 의미가 실제 응답에 맞는지 독립 재계산할 수는 없다**. 새 실행의 오류 사례 ID 28개는 [이전 실행](nlu_safety_typed_relation_development_result.md)의 계약 오류 ID 28개와 모두 같았다. 이는 실패의 재발을 보여주지만 이전 응답 각각의 원인을 복원하거나 모델의 일반 성능을 증명하지 않는다.

후보는 그대로 기각한다. 다음 설계에서는 모델이 사건·발생 근거 번호를 대부분 비우는 현상을 먼저 다뤄야 한다. 근거 번호 요구를 없애거나 공란을 임의로 채워 계약 통과율만 높이는 방식은 안전 판단의 증거를 잃을 수 있으므로, 별도 개발 가설과 사전 실패 기준을 정한 뒤 검증한다. AI 작성·1인 검수의 노출 사례 결과이므로 공식 정확도 개선율로 쓰지 않는다.
