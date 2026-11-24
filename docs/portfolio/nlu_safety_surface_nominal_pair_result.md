# A/S 원문 명사구 보완 오프라인 대조 결과

[SN01~SN09 검수표](nlu_safety_surface_nominal_pair_review.md)를 사용자 검수로 채택했다. SN03 집진판, SN07 붙여 쓴 프린터집진판, SN08 인쇄기 여과격자는 승인으로, SN05 두 후보는 보류로 확정했다. [입력](../../evals/structured_nlu/data/ai_heldout/as-safety-surface-nominal-sn-reviewed.v1.json)과 채점 코드는 첫 평가 전에 `e3912cc`에 고정했다. 동일한 관찰 사건과 후보 18개를 기존 조합 규칙과 새 원문 보완 규칙에 입력했다. 관찰 장소 분모는 SN04-1, SN05-2, SN09-1에 고정했다.

| 지표 | 기존 조합 규칙 | 새 원문 보완 규칙 |
| --- | ---: | ---: |
| 실제 출처 누락 | 5/5 | 2/5 |
| 관찰 장소 오승인 | 0/3 | 0/3 |
| 전체 오승인 | 0/13 | 0/13 |
| 두 후보를 모두 맞힌 발화 | 4/9 | 7/9 |
| 실행 오류 | 0/18 | 0/18 |

새 규칙은 SN01 프린터 집진판, SN02 전원 공급기 고정편, SN03 공기청정기 집진판을 복구했다. SN05의 목격 위치와 SN06의 같은 사건 후속 정정은 보류했다. 붙여 쓴 SN07과 등록된 기능·형태 조합 밖인 SN08은 승인 정답이지만 계속 누락됐다.

기존 CP07 인쇄기 집진판은 회귀 테스트에서 새 규칙이 승인하고 원문 오프셋도 일치하는 것을 확인했다. CP07은 SN 분모와 분리했다. 기존 규칙의 CP·DP 결과는 같은 명령으로 다시 실행해 기록과 일치했다.

[SN 결과](../../evals/structured_nlu/results/as-safety-surface-nominal-sn-evaluation.v1.json)는 `python -m experiments.as_safety_surface_nominal_evaluation`으로 재현한다. 입력 SHA-256은 `7182240703a1a9d3c5190ea02ea22c393df9b065a9e36979b9c6374d17019761`이다. AI 작성·사용자 검수 오프라인 9건이며 사건과 후보가 주어진 조건이다. 실제 서비스 정확도 및 최종 안전 경로는 평가 범위에 포함하지 않는다.
