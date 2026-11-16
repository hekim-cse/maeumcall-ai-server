# 내부 validation 짝 비교

이 도구는 AI 작성·사용자 검수 validation 32건에서 **사전 후보를 고르는 개발 평가**만 수행한다. 공식 test64나 전체 정확도 개선율의 근거로 사용하지 않는다. 알려진 저장소 발화와의 정확 일치만 검사하며, 과거 모델 노출 전체를 증명하지 않는다.

## 실행 순서

1. baseline 코드 커밋과 candidate 코드 커밋을 각각 깨끗한 별도 worktree로 준비한다. 후보 코드가 validation 문장·라벨을 보고 수정되지 않았는지 개발 기록도 확인한다.
2. 선택 규칙 문서는 후보 모델 코드 커밋보다 먼저 커밋해 그 커밋에 포함되도록 한다. 프로토콜 생성 명령의 `--candidate-commit`에는 **후보 모델 코드 커밋**을 넣는다. 이 실행기는 후보 worktree의 별도 후속 커밋에 담을 수 있지만, 모델 코드 바이트는 후보 코드 커밋과 같아야 한다.
3. 모델 파일 SHA와 로컬 Q5 이미지·메모리 한도를 준비한다. 미검증 결과 JSON, JSONL 저널, 비공개 원문 디렉터리, 검증 완료 영수증 경로를 두 worktree **밖**에 정하고, `qualification build`에 `--result`, `--journal`, `--private-dir`, `--receipt`로 미리 지정한다. 생성된 프로토콜을 후보 worktree에 커밋한다. 이 커밋에서는 프로토콜 외 Python 파일을 변경하지 않는다.
4. `qualification check`로 커밋된 프로토콜을 재검증한다. `run`은 같은 경로·worktree·모델 파일을 받아 32쌍, 총 64 arm 평가를 수행한다. 각 8 arm 평가마다 계획된 서버 재시작을 기록한다. 응답 원문은 저장소 밖 0700 디렉터리에 개별 0600 파일로만 남긴다.
5. `run` 결과는 `verification_status=unverified`이며 점수 요약을 담지 않는다. `verify`는 저널 순서·서버 경계·원문 파일 해시와 권한을 확인하고 각 arm의 고정 코드에서 원문을 재생한 뒤 결과를 다시 계산한다. 성공하면 별도의 `verification_status=verified` 영수증에만 점수 요약을 쓴다. **이 영수증이 생긴 후에만** validation 결과를 후보 선택 규칙에 대조한다.

모든 명령은 `python -m experiments.internal_validation_pair_v1.<module> --help`에서 인수를 확인한다. `qualification`에는 `build`와 `check` 하위 명령이 있다. 실행 오류나 중단이 생기면 기존 저널을 이어 쓰거나 덮어쓰지 않는다. 원인을 기록하고 새 경로·새 실행으로 시작한다.

정확도 수치에는 반드시 baseline/candidate 커밋, Q5 모델 SHA, Docker 이미지, 프로토콜·저널 SHA, 32건 분모와 `AI 작성·사용자 검수 validation`이라는 출처를 함께 표시한다. 이 결과를 본 후 후보 코드를 다시 고치면 같은 validation을 새 test로 재사용하지 않는다.
