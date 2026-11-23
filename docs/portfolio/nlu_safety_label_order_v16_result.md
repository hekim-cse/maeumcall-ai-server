# A/S 후보 관계 상태 설명 순서 통제 결과

> 2026-11-24. 이미 노출된 AI 작성·사용자 검수 후보 네 쌍의 **개발 진단**이다. 공식 정확도·개선율, 운영 안전 경로 성능이 아니다.

## 실행과 재검증

- [사전 방법](nlu_safety_label_order_v16_method.md)의 실행기·검증기·검수 입력은 `66498f0`에, [프로토콜](../../evals/structured_nlu/data/ai_heldout/as-safety-label-order-v16-development-protocol.json)은 첫 생성 호출 전 별도 `4b6a3b5`에 커밋했다. 프로토콜 SHA-256은 `dcf9414bb012c240e9c18678f4a362e5c7ea690fb2ab2045ae3f5d5405d99538`이다. 독립 재구성한 새 요청 해시 4/4가 프로토콜과 일치했다.
- [v12](nlu_safety_eb_pair_relation_v12_development_result.md)의 네 쌍·검수 정답·호출 순서, Q5 모델 파일 SHA-256 `644b04cde835d486df33c6d4d7552ba367fcb28802fe39b6b4bb9c60b9ab6f3d`, 서버 이미지 digest `sha256:17155a3ce4cc906728ec99a2814bf0b4eaffaf3b4872bad8c3affed310cdbc35`와 생성 설정을 유지했다. 생성 전 Docker 메모리는 12,527,820,800바이트였고, 실제 입력은 순서대로 346·344·365·365토큰이었다. JSON 요청에서는 **사용자 메시지의 상태 설명 순서 한 곳만** v12와 달랐다. 검수 상태·근거 번호는 모델에 주지 않았다.
- 네 쌍을 각 한 번 호출했다. 전송·길이 종료·출력 계약 오류는 0/4이고 계약 통과는 4/4다. [공개 저널](../../evals/structured_nlu/data/ai_heldout/as-safety-label-order-v16-development-journal.v1.jsonl)의 SHA-256은 `2d578726b65f2c182d16983fcf9010b25b3fba59a03c7c237f070f26b9eb7971`, [독립 재생 결과](../../evals/structured_nlu/data/ai_heldout/as-safety-label-order-v16-development-verification.v1.json)의 SHA-256은 `0c008e7f85bf259b621d55c33da8753d292c3198acd3393667811e939a892b40`이다. 원시 응답은 저장소 밖의 제한 권한 폴더에 보존했다.

## 관찰

| 후보 쌍 | 사용자 검수 정답 | v12: `supported` 첫 설명 | v16: `insufficient` 첫 설명 |
| --- | --- | --- | --- |
| PC01/P014 `선풍기 모터` | `supported`·2 | `supported`·2 | `insufficient`·공란 |
| PC01/P016 `모터에서 연기` | `unsupported`·2 | `supported`·2 | `insufficient`·공란 |
| NC01/P020 `타는 냄새` | `unsupported`·2 | `supported`·2 | `insufficient`·공란 |
| NC01/P002 `선풍기` | `insufficient`·3 | `supported`·2 | `insufficient`·공란 |

새 네 응답은 서로 바이트 단위로 같았고, v12의 같은 후보 응답과는 달랐다. **상태 정답 일치는 양쪽 모두 1/4**이며, 근거 번호 정답 일치는 v12 3/4에서 v16 0/4로 내려갔다. 후보를 구별한 개선은 관찰되지 않았다. 단일 상태가 네 후보에 반복된 채로, 그 상태가 설명의 첫 항목 `supported`에서 `insufficient`로 바뀌었다.

## 해석 경계

같은 원문·후보·스키마·모델 설정에서 상태 설명 순서 변경과 네 응답의 일괄 변화가 함께 관찰됐다. 이는 이 **고정된 네 사례**에서 설명 순서 민감성 가설을 지지한다. v12의 동일 응답을 시스템 지시 누락이나 후보 미전달만으로 설명하기 어렵다는 [입력 경로 점검](nlu_safety_chat_template_audit.md)과도 일치한다.

한 번의 순서 반전으로 일반적인 ‘항상 첫 항목을 고른다’는 규칙이나 모델 내부의 단일 원인을 증명할 수는 없다. 같은 날의 조건별 반복도 없고, 네 문장은 이미 노출된 개발 사례다. 후보별 물리적 출처 판단 능력이나 서비스의 안전 성능이 개선됐다고 주장하지 않는다. 다음 설계는 라벨 열거 위치와 후보 근거 판단을 분리하고, 새로운 미노출 자료에서 다시 검증해야 한다. TX·GB, AWS·KT cloud와 서비스 경로는 사용하거나 변경하지 않았다.

PR 리뷰 후에는 사전 방법의 “결과가 같으면 순서 편향을 배제”한다는 과한 해석을 바로잡고, 별도 테스트 파일에 실행기 오류 중단 검사를 추가했다. 실행 당시 코드·방법을 해시로 고정한 커밋 검사는 유지한다. 현재 작업 트리 해시 대조에서는 **실행 후 수정한 방법 문서와 검증기만** 제외하며, 요청 생성 코드·기존 테스트·프로토콜·저널·원시 응답 검사는 그대로 유지한다. 모델 재호출은 하지 않았다.
