# A/S 붙여쓰기와 부위 표현 확장 대조 결과

사용자가 [AP01~AP10 검수표](nlu_safety_attached_device_part_pair_review.md)를 채택했다. AP05~AP08은 양쪽 모두 보류, AP09의 전원장치발열체와 AP10의 공기순환기 여과격자는 승인이다. [입력](../../evals/structured_nlu/data/ai_heldout/as-safety-attached-device-part-ap-reviewed.v1.json)과 채점 코드를 평가 전 `81de94f`에 고정했다. 두 규칙에 같은 발화와 고정 사건·후보를 입력했으며 관찰 장소 분모는 AP05-1, AP06-1, AP08-2다.

| 지표 | 기존 원문 명사구 규칙 | 새 조합 규칙 |
| --- | ---: | ---: |
| 실제 출처 누락 | 6/6 | 2/6 |
| 관찰 장소 오승인 | 0/3 | 0/3 |
| 전체 오승인 | 0/14 | 0/14 |
| 두 후보 모두 맞힌 발화 | 4/10 | 8/10 |
| 실행 오류 | 0/20 | 0/20 |

AP01 전원 공급기절연판, AP02 정수기 여과막, AP03 인쇄기 차폐격자, AP04 제습기여과격자를 승인했다. 위치 후보, 후속 출처 정정, 목격 표현이 들어 있는 AP05~AP08은 보류를 유지했다. AP09는 기기명 내부까지 공백이 사라진 경우이고, AP10은 등록 기기명 범위 밖이라 놓쳤다.

SN07 프린터집진판과 SN08 인쇄기 여과격자는 별도 회귀 테스트에서 원문 오프셋과 함께 승인됐다. 새 AP 점수에는 두 회귀 사례를 포함하지 않았다. 기존 SN 결과도 기존 규칙으로 재현했다.

[후보별 결과](../../evals/structured_nlu/results/as-safety-attached-device-part-ap-evaluation.v1.json)는 `python -m experiments.as_safety_attached_device_part_evaluation`으로 재현한다. 입력 SHA-256은 `ea15bb20a2bcc71ffb736810f0eb559450b8d8d0460dd13c5a414098ca67ec77`이다. AI 작성·사용자 검수 오프라인 10건이며 사건과 후보 구절을 고정했다. 서비스 정확도 또는 최종 안전 경로 검증은 포함하지 않는다.
