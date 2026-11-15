# 현재 NLU 개발 기준선: Q5 재실행 결과

> 2026-11-16. **이미 모델에 노출된 AI 작성·사용자 검수 AH01–AH32의 개발 진단**이다. 새 미노출 내부 공식 표본 test의 결과가 아니며, 정확도 개선율의 전후 비교값으로 사용하지 않는다.

## 조건과 검증

원시 문장을 제외한 [독립 검증기 출력 영수증](../../evals/structured_nlu/results/nlu-current-baseline-v2-development-verification-receipt.json)을 함께 보존했다.

후속 코드 변경과 구분하려면 프로토콜이 커밋된 `d1ada90`의 별도 작업 트리에서 검증한다. `<저장소>`와 `<비공개 원시 폴더>`에는 각자의 실제 경로를 넣는다.

```sh
git worktree add --detach /private/tmp/maeumcall-nlu-v2-frozen d1ada90
cd /private/tmp/maeumcall-nlu-v2-frozen
<저장소>/.venv/bin/python -m experiments.nlu_current_baseline_v1.verify \
  --protocol evals/structured_nlu/data/ai_heldout/nlu-current-baseline-v2-development-protocol.json \
  --journal <저장소>/evals/structured_nlu/results/nlu-current-baseline-v2-development-journal.jsonl \
  --result <저장소>/evals/structured_nlu/results/nlu-current-baseline-v2-development-result.json \
  --private-dir <비공개 원시 폴더> --model-path /private/tmp/maeumcall-kanana-q5.gguf
```

16개 상세 업무에서 각각 2건씩, 총 32건을 현재 서비스의 구조화 NLU 경로로 실행했다. [사전 동결 프로토콜](../../evals/structured_nlu/data/ai_heldout/nlu-current-baseline-v2-development-protocol.json)은 실행기·분석기·점수 함수가 들어 있는 코드 커밋 `ab2abc8`, Q5 모델 파일·서버 이미지 해시, 요청 정책을 고정했다. Docker Desktop 메모리 목표 12GiB, 실제 호스트 메모리 하한 11.5GiB, 컨테이너 10GiB·2 CPU, 8건마다 계획 재시작을 적용했다. 실행기의 최초 Docker 접근이 거부된 시도는 저널·결과·원시 응답을 만들기 전 종료돼 평가에 포함하지 않았다. 이후 같은 프로토콜로 처음부터 실행했다.

[공개 저널](../../evals/structured_nlu/results/nlu-current-baseline-v2-development-journal.jsonl)은 `header` 1행·서버 경계 8행·사례 `begin`/`end` 각 32행·`summary` 1행으로 **74행**이다. 8·16·24건 뒤 재시작 전후 경계와 최종 경계에서 서버 실행 상태·시작 시각·메모리를 기록했다. 경계의 OOM 표시는 모두 `false`, 모델 응답 미수신 오류는 **0건**이었다. 종료 직후 Docker에서도 실행 중·`OOMKilled=false`·종료 코드 0을 확인했다. 원시 응답 파일 **40개**는 저장소 밖 사용자 전용 폴더(디렉터리 0700, 파일 0600)에 보존했다.

[공개 결과](../../evals/structured_nlu/results/nlu-current-baseline-v2-development-result.json)는 원시 응답을 재생하는 독립 검증기로 검사했다. 저장소 밖 보존본으로 다시 검증해 `case_count=32`와 저널·결과·집계가 일치했다. 검증기는 동결된 동일 분석기를 원시 응답에 재적용하므로 **기록의 재현성**을 확인한다. 분석기의 의미 판단 자체를 독립적으로 보증하거나 비공개 원시 응답을 제3자에게 공개하는 증거는 아니다.

| 지문 | SHA-256 |
|---|---|
| 프로토콜 | `f05bd081771056cc85cde002ccab96a1d754cbc4aa6d54e2fefd45cce3932e81` |
| 저널 | `05097a019b91bb2d1783e5440ec012b84dee7d9bc3f9d4b8f5b101c10088dc46` |
| 결과 | `a2c0fdb77022742f6cae19c3edd91ff8f06b75c8c5cad7a3ca3ad32287a2417c` |

## 개발 진단 결과

| 지표 | 관측값 | 해석 |
|---|---:|---|
| 사례 전체 일치 | **3/32 (9.375%)** | 출력 계약·intent·행동·변경 필드·모든 업무 필드 동시 일치 |
| 첫 시도 출력 계약 통과 | 24/32 (75%) | 첫 응답이 계약에 맞은 사례 |
| 재시도 후 출력 계약 통과 | 27/32 (84.375%) | 최종 계약 실패 5/32 |
| 재시도 사례 | 8/32 (25%) | 첫 응답 계약 실패 뒤 한 번 재요청 |
| 모델 응답 미수신·OOM | 0건 | 이번 실행의 환경 실패 관측 없음 |

첫 4GiB 실행은 [OOM으로 무효](nlu_current_baseline_v1_invalid_oom.md)였으므로 그 파일에 계산된 `3/32`와 이 결과를 동일 조건의 전후 성능으로 비교하지 않는다. 특히 점수가 우연히 같은 `3/32`라는 사실은 개선이나 재현된 정확도를 뜻하지 않는다.

동결된 점수 함수는 최종 출력 계약에 실패한 사례에서 정답으로 채워진 슬롯을 `gold_present`·누락 분모에 넣지 않는 문제가 발견됐다. **슬롯 정밀도·재현율·누락률 등의 보조 지표는 이 실행에서 주장하지 않는다.** 위 사례 전체 일치율과 계약 통과 건수는 그 집계 경로를 사용하지 않는다. 버그 수정 뒤 결과 원본을 덮어쓰지 않고 새 버전으로 검증한다.

## 공식 개선율까지 남은 조건

이 32건은 개발 과정에 이미 노출돼 후보 선택과 오류 분석에만 쓴다. [AI 작성·사람 검수 내부 공식 표본 평가 방법](nlu_ai_reviewed_internal_benchmark_v1_method.md)에 따라 validation 32건으로 후보를 고르고, **후보 동결 후** 새 test 최소 64건을 작성·사람 검수·노출 점검·사전 동결해야 한다. 같은 test를 기존·수정 조건에서 짝지어 실행하고 원시 응답을 독립 검증한 뒤에만 내부 표본의 퍼센트포인트 차이를 계산한다. 그 결과가 양수여도 사전 정의한 구간과 안전 실패 조건을 충족하기 전에는 “개선 확인”이라고 쓰지 않는다. 이 결과를 실제 사용자 분포, 32개 전체 흐름 또는 사람 작성 V3 전수 공식 정확도로 표현하지 않는다.
