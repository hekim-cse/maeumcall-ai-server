# 리뷰 후 수정의 신규 사례 비교 실행 기록

## 실행 전 동결

이 평가는 PR #49의 리뷰 후 수정만 좁게 확인한다. AI 작성 발화 RF01–RF12는 사용자 한 명이 문장·행동·모든 필드 값과 공란을 모델 실행 전에 검수했다. 독립적인 두 번째 검수자는 없다. 기존 NS11과 리뷰 후 개발 진단 발화는 재사용하지 않는다.

- 이전 후보: `f52d991`.
- 최종 코드: `ae91656`.
- 데이터: `nlu-review-followup-reviewed.v1.json`, 검수 원장: `nlu-review-followup-ledger.v1.json`.
- 모델: 같은 Kanana Q5 GGUF 파일, SHA-256 `644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d`.
- 실행 조건: [동결 프로토콜](../../evals/structured_nlu/data/ai_heldout/nlu-review-followup-code-pair-protocol.v1.json). 12건을 같은 서버에서 전후 순서를 번갈아 실행하며, 6쌍 뒤 서버를 재시작한다. 계약 실패 시 한 번만 재시도한다.
- 주장 범위: A/S와 교수님 면담 예약의 `greeting` 상태, 두 코드의 짝비교. 전체 16개 업무나 실제 사용자 발화 분포의 정확도로 일반화하지 않는다.

**실행 상태:** 입력·검수 원장·프로토콜을 커밋으로 고정하기 전. 모델 호출 없음. 실행 결과와 무효 시도는 발생하면 아래에 추가한다.
