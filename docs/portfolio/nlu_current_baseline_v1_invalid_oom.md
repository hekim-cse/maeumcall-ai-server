# 현재 NLU 개발 기준선 첫 실행: 메모리 부족으로 무효

> 2026-11-16. 이 기록은 **실패 실행 감사**다. 아래 결과 파일의 `3/32`를 모델 정확도나 개선율로 사용하지 않는다.

이미 모델에 노출된 AI 작성·사용자 검수 AH01–AH32로 현재 16개 상세 업무의 개발 기준선을 재측정하려 했다. [실행 전 프로토콜](../../evals/structured_nlu/data/ai_heldout/nlu-current-baseline-v1-development-protocol.json)은 코드 커밋 `8b27fdc`, Q5 파일 해시, 모델 서버 이미지와 컨테이너 메모리 **4GiB**를 고정했다. 32개 사례의 시작·종료와 요약은 [66행 저널](../../evals/structured_nlu/results/nlu-current-baseline-v1-invalid-oom-journal.jsonl)에, 정규화 예측은 [무효 결과 파일](../../evals/structured_nlu/results/nlu-current-baseline-v1-invalid-oom-result.json)에 보존했다. 원시 응답 29개는 저장소 밖 사용자 전용 위치에 권한 0600으로 보존했다.

실행 후 Docker의 해당 컨테이너 상태에서 `OOMKilled=true`, `ExitCode=137`을 확인했다. 공개 결과의 시도별 오류 유형에는 `RemoteDisconnected` **20회**가 포함된다. 원시 응답으로 재생한 독립 검증은 저널의 기록·계산이 일치함을 확인했지만, 서버가 정상 완주했다는 뜻은 아니다. 프로토콜 SHA-256은 `41979fa5732dd000516adc599da14cb802e0b0acadbf485b184ceb7be17b4460`, 저널 SHA-256은 `33e8df0a4dd131658ba24a6adcaa9e070d2a38189bfaa8e8901a2ff75a35d568`, 결과 SHA-256은 `3f93cf2ef7a816bef2f76342a4066cad1bd4e304b37ffe379ae557d07cdd2b76`이다.

### 원시 재생 검증 영수증

원시 문장을 제외한 [검증기 출력 영수증](../../evals/structured_nlu/results/nlu-current-baseline-v1-invalid-oom-verification-receipt.json)을 함께 보존했다. 이 영수증은 실패 실행의 기록 일치만 보여 준다.

검증은 프로토콜 커밋 `03ffcbb`의 코드를 별도 작업 트리에서 실행했다. 원시 응답은 저장소 밖 사용자 전용 폴더에 두고 내용은 공개하지 않았다. 아래는 재실행 명령 형식이다. `<저장소>`와 `<비공개 원시 폴더>`에는 각자의 실제 경로를 넣는다.

```sh
git worktree add --detach /private/tmp/maeumcall-nlu-baseline-frozen-03ffcbb 03ffcbb
cd /private/tmp/maeumcall-nlu-baseline-frozen-03ffcbb
<저장소>/.venv/bin/python -m experiments.nlu_current_baseline_v1.verify \
  --protocol evals/structured_nlu/data/ai_heldout/nlu-current-baseline-v1-development-protocol.json \
  --journal <저장소>/evals/structured_nlu/results/nlu-current-baseline-v1-invalid-oom-journal.jsonl \
  --result <저장소>/evals/structured_nlu/results/nlu-current-baseline-v1-invalid-oom-result.json \
  --private-dir <비공개 원시 폴더> --model-path /private/tmp/maeumcall-kanana-q5.gguf
```

실행 결과는 종료 코드 `0`, `case_count=32`, 위 세 SHA-256 일치였다. 저널은 `header` 1행·`begin` 32행·`end` 32행·`summary` 1행으로 **66행**이다. 접근 제한된 원시 응답 파일은 **29개**였다. 검증기가 계산한 `3/32`는 실패 실행 파일과 일치한다는 뜻일 뿐, 유효한 정확도가 아니다. 원시 파일을 공개하지 않으므로 제3자는 이 문서와 공개 파일만으로 원시 재생 자체를 독립 반복할 수 없다.

출력 파일에는 전체 일치 `3/32`가 계산돼 있지만, 연결 실패가 20회 섞여 있으므로 **평가 전체를 무효**로 판정한다. 이를 이전 Q4·Q5 탐색의 `1/32`와 비교하지 않는다. 실행기와 검증기에는 모델 응답 미수신 시 즉시 중단하고 완성 결과를 발행하지 않는 관문을 추가한다. 이전의 4GiB 부족 사례와 계획 재시작 성공 기록을 근거로, 새 메모리·재시작 조건을 별도 프로토콜로 동결한 뒤 처음부터 재실행한다. 실패 기록은 덮어쓰거나 성공 실행과 합치지 않는다.
