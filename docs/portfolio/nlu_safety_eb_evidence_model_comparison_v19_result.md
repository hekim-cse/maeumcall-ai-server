# A/S 번호 근거 선택 모델 대조 결과

[사전 방법](nlu_safety_eb_evidence_model_comparison_v19_method.md)은 `ea14375`, [프로토콜](../../evals/structured_nlu/data/ai_heldout/as-safety-eb-model-comparison-v19-protocol.json)은 첫 생성 전에 `ba1610b`에 고정했다. Qwen2.5-1.5B-Instruct Q5_K_M 공식 파일의 SHA-256을 확인하고, 기존 v18과 같은 설정으로 네 후보를 두 질문 순서에서 한 번씩 실행했다.

| 항목 | v18 Kanana Q5 | v19 Qwen Q5 |
| --- | ---: | ---: |
| 정답 후보 포함 | 8/8 | 8/8 |
| 정답 포함 조건에서 근거 선택 | 0/8 | 0/8 |
| 관계 상태 정답 일치 | 2/8 | 2/8 |
| 세 근거가 모두 공란 | 8/8 | 8/8 |
| 출력 계약 통과 | 8/8 | 8/8 |

각 질문 순서에서 두 모델 모두 근거 0/4, 상태 1/4였다. Qwen의 여덟 원시 응답은 대응하는 Kanana 응답과 바이트 단위로 같았다. 실제 전송 직전 본문의 해시 8개는 동결된 두 프로토콜과 일치했다. 토큰은 후보별로 Kanana 279·277·290·290개, Qwen 297·295·315·313개였다. 비교에는 모델 파일, 내장 템플릿과 토크나이저가 함께 포함된다.

전송·출력 오류와 재시도는 0건이었다. 원시 응답은 저장소 밖에 보관했다. 실행 뒤 추가한 `python -m experiments.as_safety_atomic_edges_v19_replay`와 별도 서브에이전트 검수에서 요청·저널 해시와 원시 응답을 대조하고 점수를 재계산했다. [공개 저널](../../evals/structured_nlu/data/ai_heldout/as-safety-eb-model-comparison-v19-journal.v1.jsonl)의 SHA-256은 `7975154bccfd21d8b5d007f5f7b4fd2fd2ef4abd28adac730afb7e98bb184cbf`다.

이 기노출 네 쌍에서는 전건 보류가 Kanana에만 나타나는 현상이 아니었다. 두 모델에 공통된 요청과 출력 제약이 왜 같은 응답을 유도했는지는 이번 대조로 특정할 수 없다. 개발 관문을 통과하지 못해 미노출 평가와 서비스 연결은 보류했다. 별도 개발 진단을 이어갈 경우 세 근거를 한 번에 반환하는 방식과 질문을 하나씩 나누는 방식을 비교해, 어느 단계에서 보류가 발생하는지 확인한다.
