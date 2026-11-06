# 신규 업무 범위 전후 평가 실행 기록

## 첫 실행: 무효

NS01–NS32를 수정 전후 코드로 번갈아 요청하는 첫 실행은
`nlu-scope-code-pair-protocol.v1.json`에 따라 시작했다. 컨테이너는
6GiB 메모리 한도에서 `oom` 이벤트와 종료 코드 137을 기록하고 자동
삭제됐다. 결과 파일
`evals/structured_nlu/results/nlu-scope-code-pair-invalid-oom-v1.json`에는
연결 종료 후의 `RemoteDisconnected`가 수정 전 54회, 수정 후 56회
남아 있다. **이 파일의 점수는 정확도나 성능 비교로 사용하지 않는다.**

원인은 Docker 이벤트의 `oom`, `die(exitCode=137)`로 확인했다. 첫 실행 후
코드·모델·발화·정답을 변경하지 않았다. Docker Desktop 메모리 한도는
기존 8GiB에서 이전에 승인된 12GiB로 일시 변경했고, 컨테이너 한도를
10GiB로 올려 새 프로토콜에 기록한 뒤 처음부터 재실행한다. 이 조치는
첫 노출 이후의 실행 환경 수정이므로, 재실행 결과를 **최초 프로토콜을
그대로 지킨 사전 평가**라고 설명하지 않는다. 실패와 수정 내역을 함께
공개한다.
