# 보수적 출처 연결 규칙의 개발 단계 기각

## 시험한 가설

[이전 Q5 진단](nlu_safety_gold_owner_link_result.md)은 위험 주체의 검수 구간을 알려줘도 다른 출처 6건을 모두 `current`로 판단했다. 이에 따라 [출처 연결 규칙](../../scripts/probe_as_safety_source_link_v1.py)을 **개발 전용**으로 만들어, 동일 구간·명시적 소속 부품만 `current`, 명시적 타개체 표현만 `other`, 나머지는 `unknown`으로 보류하는 가설을 확인했다. 문자열이 다르다는 이유만으로 다른 물건이라고 단정하지 않는다. 이 코드는 원문 구간을 추출하지 않으며 서비스 그래프에 연결되지 않았다.

검수된 [기존 RE/V 22건](../../evals/structured_nlu/data/ai_heldout/as-safety-owner-evidence-reviewed.v1.json)에 **정답 접수 대상·위험 주체 구간을 입력으로 준 유리한 조건**에서 [재현 감사](../../scripts/audit_as_safety_source_link_development.py)를 실행했다. 모델 호출은 없었다. 새 GB01–GB24는 후보 설계·실행에 쓰지 않았고 모델에도 보내지 않았다.

재현 명령: 저장소 루트에서 `.venv/bin/python -m scripts.audit_as_safety_source_link_development`. 이 감사기가 읽는 후보·감사기·RE/V 원본·구간·위험 주체 라벨의 SHA-256은 다음과 같다. 계산은 `shasum -a 256 <경로>`로 확인할 수 있다.

| 파일 | SHA-256 |
| --- | --- |
| `scripts/probe_as_safety_source_link_v1.py` | `099a5ebee53e2af9654ae8d242831941e674f16eec4200a8d7b5e4df0cf0d743` |
| `scripts/audit_as_safety_source_link_development.py` | `1457f2b93785691a815a33cd8904dd07273e3879cf13e1520fa7989728098890` |
| `as-safety-relation-fresh-reviewed.v1.json` | `b601d000ee4a8b8ffee114179099283f1d75f9226514cfd31467f99993f158cd` |
| `as-safety-relation-v2-fresh-reviewed.v1.json` | `cf07b01f1107d3fc15b232ff85692188d2a807fc425865768163f4d4fb12bf5e` |
| `as-safety-oracle-relation-spans-reviewed.v1.json` | `01016261bb8c83e22f50204f2f37c64f9f87cb13f6c88ecd4c377a71e6bbfc1e` |
| `as-safety-owner-evidence-reviewed.v1.json` | `785b2cab6c4cf4cc3ed545676ed27f1b39ce09c24ff0465e963f298aecb15f56` |

GB 미노출은 감사기 출력으로 증명되는 값이 아니라 이 작업에서 모델 호출을 하지 않았고 GB를 후보 코드·감사기의 입력으로 사용하지 않은 절차 기록이다.

## 관찰과 기각

| 검수 관계 | 정확히 확정 | 보류 |
| --- | ---: | ---: |
| 현재 제품 `current` | 5/16 | 11/16 |
| 다른 출처 `other` | 1/6 | 5/6 |
| 전체 | 6/22 | 16/22 |

실제 발생이 관찰된 현재 제품 위험 13건 중 이 규칙이 `current`로 확정한 사례는 **5/13**이다. 나머지 8건은 단독 적용 시 즉시 안전 조치 대신 확인으로 늦어질 수 있다. 다른 출처를 현재 제품으로 잘못 확정한 건 없지만, 다른 출처 6건 중 5건을 일반 접수로 확정하지도 못했다. 기존에 정한 보호·출처별 게이트를 충족하지 못하므로 **새 GB 사례에 실행하지 않고 후보를 기각했다.** 6/22는 정답 구간을 받은 링크 하위 과제의 일치 수이며 전체 안전 경로 정확도가 아니다.

독립 검토에서 `친구가 쓰는 노트북`이 접수 대상과 위험 주체 양쪽에 등장하는 문장, `다른 쪽 배터리`가 같은 제품의 부위를 가리키는 문장을 거짓 `other`로 만들 수 있음을 발견했다. 두 경우는 확정 대신 보류하도록 고친 뒤 합성 회귀 테스트를 통과했고, 위 기노출 집계도 다시 계산해 같았다. 이 보강에도 높은 보류율이 남아 있다.

PR 리뷰에서 같은 문장 안의 `수리할 다른 노트북`과 그 구절에 포함된 `다른 노트북`도 `other`로 오판하는 반례가 발견됐다. 두 인용이 실제로 **동일 원문 구간을 공유**하면 `current`로 판단하도록 좁게 수정했다. 별도 합성 회귀 테스트와 기노출 22건 재계산에서 위 집계가 유지됐다.

## 다음 판단

명시적 연결 근거를 보수적으로 확정하는 규칙만으로는 이 조건의 현재 제품 위험을 충분히 즉시 보호하지 못한다. 후속 [중립적 개체 연결 단일 판단 진단](nlu_safety_entity_link_diagnostic_result.md)도 기노출 사례에서 다른 출처 1/6에 그쳐 기각됐다. 새 후보가 기존 사례에서 안전 경계를 충족하기 전에는 사용자 검수 후 고정한 GB 24건을 모델에 노출하지 않는다. GB는 최종적으로 AI 작성·사용자 검수 탐색 평가에만 쓸 수 있다.
