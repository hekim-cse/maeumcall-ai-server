# A/S 위험 주체 후보 경계 오프라인 감사 결과

> 2026-11-22. [방법](nlu_safety_eb_boundary_v8_offline_method.md)에 따른 **기노출 개발 자료의 후보 가용성 감사**다. Kanana 모델을 실행하지 않았으며, 정확도·개선율이나 안전 분기 성능이 아니다.

## 재현 범위

`.venv/bin/python -m experiments.as_safety_atomic_edges_v8.boundary_audit`는 입력 4개 파일의 SHA-256과 `kiwipiepy==0.23.2`를 확인하고 [사례별 결과 JSON](../../evals/structured_nlu/data/ai_heldout/as-safety-eb-boundary-v8-offline-result.v1.json)을 출력한다. 저장된 JSON의 SHA-256은 `3370ef8ebb6da5a5f8d0c6722cc4e6c20bf5f5580d51a36c55ca846a63df124b`이며 같은 명령의 재출력과 일치했다. 원문 34건의 문자열만 후보 생성 함수에 전달하고, 생성 뒤 검수 주체 라벨이 있는 **26건**의 포함 여부를 채점했다. PC/NC 원문과 정답은 같은 파일에 들어 있어 파일 바이트 자체는 후보 생성 전에 읽는다. 나머지 8건의 정답 포함률은 계산하지 않았다. TX·GB는 감사 코드의 입력·집계에 포함하지 않았다.

자료 탐색 중 `as-safety-source-boundary-reviewed.v1.json`의 첫 110행을 실수로 열람했다. GB01–GB06 일부 문장이 이 작업 세션에 노출됐으므로 **GB 전체가 이 세션에서 완전 미노출이었다고 주장하지 않는다.** 해당 내용은 후보 조건 설계·코드·결과 집계에 사용하지 않았고, 앞으로 GB를 새 미노출 평가로 취급하지 않는다. TX는 열람하지 않았다.

| 후보 조건 | 26건의 후보 합계 | 기준선 대비 후보 감소 | 양성 검수 구절 포함 | 기준선 대비 새 탈락 |
| --- | ---: | ---: | ---: | ---: |
| 기존 5토큰 원문 후보 전체 | 1,570 | 기준선 | 23/23 | 0 |
| 명사류 형태소 끝 N | 525 | 66.6% | 23/23 | 0 |
| 연속 명사구 C | 239 | 84.8% | 21/23 | 2 |

양성 23건에는 PC01과 RE/V의 검수 주체 구절이 들어 있다. C가 잃은 두 구절은 RE09 `오래된 멀티탭`(기준선·N 후보 P027)과 RE10 `친구가 쓰는 같은 모델`(P054)이다. Kiwi가 관형 수식과 서술어를 포함해 분석하므로 C의 단순한 연속 명사구 조건이 이를 제외한다. 사전 기준인 **기준선 포함 정답의 추가 손실 0건**을 지키지 못했으므로 C를 단독 강제 후보 집합으로 채택하지 않는다.

PC01은 기존 22개에서 N 7개, C 5개가 됐다. 정답 P014 `선풍기 모터`는 두 조건에 남고, v7에서 잘못 선택한 P013 `선풍기 모터에서`와 P022 문장 전체는 빠졌다. 그러나 N에는 `모터에서 연기`(P016)와 `선풍기 모터에서 연기`(P020)가 남는다. C에서도 `선풍기`(P005), `모터`(P007) 같은 짧은 경쟁 후보가 남는다. **정답 후보 보존과 경쟁 후보 제거는 모델의 정확 선택을 증명하지 않는다.**

정답이 공란인 NC01·RE07·V09는 양성 포함률과 따로 세었다. 세 사례의 N 후보는 각각 4·32·20개, C 후보는 3·11·8개다. 후보가 남아 있어도 물리적 출처를 확정할 수 없으므로 보류 정확도는 평가하지 않았다.

## 판단

N은 이번 기노출 개발 자료에서 후보 수를 줄이며 검수 구절을 새로 잃지 않았으므로 **다음 소규모 개발 대조의 후보**로만 남긴다. N도 과다 인용 후보가 남고, 형태소 분석 오류·다른 문장 유형에서 정답을 잃을 수 있다. 다음 모델 진단을 하려면 출처 불명 보류를 함께 보는 요청·순서·검증 기준을 사전에 고정해야 한다. 이 감사만으로 ES 전체나 서비스 안전 경로에 적용하지 않는다. 별도 미노출 평가 전에는 포트폴리오의 공식 정확도 개선율로 쓰지 않는다.

집중 테스트 `.venv/bin/python -m pytest tests/test_as_safety_atomic_edge_boundary_audit_v8.py -q`는 **7개 통과**했다. 기존 후보 생성·v7 테스트까지 포함한 `.venv/bin/python -m pytest tests/test_as_safety_source_lattice.py tests/test_as_safety_atomic_edge_candidate_order_v7.py tests/test_as_safety_atomic_edge_boundary_audit_v8.py -q`는 **31개 통과**했다. `.venv/bin/python -m ruff check experiments/as_safety_atomic_edges_v8 tests/test_as_safety_atomic_edge_boundary_audit_v8.py`와 같은 범위의 `ruff format --check`도 통과했다. 이 테스트는 후보 생성·집계 코드의 검증이며 모델 성능 테스트가 아니다. 이번 단계에서는 Docker, AWS, KT cloud를 실행하지 않았다.
