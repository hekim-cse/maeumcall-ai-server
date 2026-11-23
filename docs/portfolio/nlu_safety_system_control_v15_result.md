# A/S 시스템 지시 반응 통제 결과

> 2026-11-24. AI 작성·기노출 PC01/P014의 **인위적 장치 점검**이다. 의미 정확도·공식 개선율·서비스 안전 경로 성능이 아니다.

## 별도 고정과 검증

- [v14](nlu_safety_response_controls_v14_result.md)는 첫 스키마 통제의 출력 계약 실패에서 멈췄다. 그 저널·원시 응답을 재시도하거나 수정하지 않고, 미실행 시스템 통제를 새 코드 `4bf033c`와 별도 [프로토콜](../../evals/structured_nlu/data/ai_heldout/as-safety-system-control-v15-protocol.json) 커밋 `73a0a6d`에 고정했다. 프로토콜 SHA-256은 `4719cbc67444978dcf02d2cd0a732dd6b79846c8d629e6373244145833c8c856`이다.
- 고정 Q5 파일 SHA-256 `644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d`, 서버 이미지 digest `sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35`를 사용했다. 실제 요청은 **383 입력 토큰**이며, 독립 생성 요청과 해시가 일치했다. 기존 v12 요청에서 시스템 메시지의 인위적 지시 한 문단 외 모든 JSON 필드가 같다. 검수 정답은 요청에 넣지 않았다.
- 한 번만 호출해 `stop`으로 끝났고 전송·출력 계약 오류는 없었다. [공개 저널](../../evals/structured_nlu/data/ai_heldout/as-safety-system-control-v15-journal.v1.jsonl) SHA-256은 `530262d79e67d84a3f4ca93e27aeac4e167cd95dbd763d3979b3182b26f2ca9b`, [독립 검증 결과](../../evals/structured_nlu/data/ai_heldout/as-safety-system-control-v15-verification.v1.json) SHA-256은 `77ec88a7ffa604e28a4eca45655d3ea6edd9d70180716415d35c0b780a7d7acb`다. 원시 응답은 저장소 밖 제한 권한 폴더에 있고 공개 파일만으로 의미를 독립 재생할 수는 없다.

## 관찰과 해석

| 조건 | 출력 상태·근거 번호 | 계약 |
| --- | --- | --- |
| 기존 v12 PC01/P014 | `supported`·2 | 통과 |
| v14 스키마 enum을 `unsupported`로 제한 | 원시 `unsupported`·`null` | 실패: `evidence_clause_missing` |
| v15 시스템 지시에서 `unsupported`·2를 요구 | `supported`·2 | 통과 |

v15 원시 응답 SHA-256은 v12 PC01/P014와 같았다. 따라서 이 **한 호출에서** 시스템 메시지 끝의 명백한 지시 변화가 결과를 바꾸지 못했다. 반면 v14의 **한 호출에서** 스키마 enum 변화는 상태를 바꿨지만, 상태와 근거 번호의 일관성을 만들지 못했다. 이는 구조화 출력 제약과 의미 판단 계약을 구별해야 한다는 구체적 관찰이다.

두 통제는 각각 단회이고, v15 지시는 기존 과제와 의도적으로 충돌한다. 따라서 모델이 시스템 메시지를 전혀 받지 못했다거나 Q5가 일반적으로 지시를 따르지 못한다고 단정할 수 없다. 스키마 자체가 기존 네 사례에서 `supported`로 수렴시킨 유일 원인이라고도 단정할 수 없다. 다음에는 서버가 실제로 렌더링한 채팅 템플릿과 입력 역할을 확인하고, **원래 의미 과제를 유지한 조건**에서 후보별 응답 차이를 다시 설계해야 한다. 공식 정확도를 주장하려면 별도의 미노출 평가가 필요하다. TX·GB, AWS·KT cloud는 사용하지 않았고 서비스 경로는 변경하지 않았다.
