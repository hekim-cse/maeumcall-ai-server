# A/S 응답 경로 통제 검사: 첫 호출에서 중단

> 2026-11-24. AI 작성·기노출 PC01/P014를 사용한 **인위적 장치 점검**이다. 의미 정확도나 안전 경로 평가가 아니다.

## 고정과 실행

- 설계·실행기·검증기는 생성 전 `86b5421`에, [프로토콜](../../evals/structured_nlu/data/ai_heldout/as-safety-response-controls-v14-protocol.json)은 생성 전 별도 `d20e216`에 커밋했다. 프로토콜 SHA-256은 `389f54d5efdde788bc95d4b5b7b2b96474363b15fa8a38d9fd05af34c4b57001`이다.
- 기존 v12의 같은 PC01/P014 요청·원시 응답을 독립 재생했다. 고정 Q5 SHA-256은 `644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d`, 서버 이미지 digest는 `sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35`다. 스키마 제약 요청은 **스키마 enum만** 기존 요청과 달랐고 입력 346토큰이었다.
- [공개 저널](../../evals/structured_nlu/data/ai_heldout/as-safety-response-controls-v14-journal.v1.jsonl) SHA-256은 `9b56ed175df2f8acfdbcc518ea2f47a78c11ce081a0d6590e5661acd8fadd020`이다. 원시 응답은 저장소 밖 권한 제한 폴더에 보관했다. [독립 검증 결과](../../evals/structured_nlu/data/ai_heldout/as-safety-response-controls-v14-verification.v1.json) SHA-256은 `ed3764bcf6cb38e1cdc112469bb3ac5b6d350690702a012558ba138ce4026c68`다. 공개 자료만으로 원시 응답을 독자적으로 재생할 수는 없다.

## 관찰과 경계

첫 `schema_forced_unsupported` 호출은 `stop`으로 끝났고 원시 응답의 `relation_status`가 이전 `supported`에서 **`unsupported`로 바뀌었다**. 그러나 `evidence_clause_index=null`이어서 기존 계약의 “`unsupported`에는 근거 문장 번호 필수” 조건을 위반했다. 오류 코드는 `evidence_clause_missing`이다. 스키마가 허용 상태의 **enum에는 영향을 준 관찰**이지만, 상태와 근거 번호 사이의 의미 일관성까지 보장하지는 않았다.

사전 고정한 오류 시 중단·재시도 금지 규칙에 따라 두 번째 `system_forced_unsupported`는 **호출하지 않았다**. 따라서 시스템 지시 반응 여부는 이 실행에서 **미평가**이며 검증 결과에도 `null`로 남긴다. 첫 호출의 출력 계약은 실패했으므로 성공률 지표의 분자에 넣지 않는다.

실행 후 검증 보고서가 **관찰된 원시 상태와 전체 계약 유효성**을 별도로 표시하도록 수정했다. 고정 커밋의 모든 소스 해시·프로토콜·저널·원시 파일 해시 검사는 유지했고, 이 실행 후 수정된 검증기·테스트 파일만 현재 작업 트리의 소스 해시 대조에서 제외했다. 원시 응답, 저널, 프로토콜은 바꾸지 않았으며 추가 모델 호출도 하지 않았다. 다음 시스템 지시 통제는 별도 프로토콜을 사전 고정해 독립 실행해야 한다. AWS·KT cloud는 사용하지 않았다.
