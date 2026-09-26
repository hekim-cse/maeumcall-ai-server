# 마음콜 구조화 NLU 모델 평가

## 평가 범위

이 평가는 마음콜의 32개 전체 시나리오 중 로컬 Hugging Face 모델이 실제로
구조화 분석을 담당하는 16개 상세 그래프만 다룬다.

- 예약 4개: 병원, 식당, 미용실, 스터디룸
- 교수님 3개: 면담 예약, 과제 문의, 결석 사유 전달
- 배달 3개: 주문 변경, 배달 지연 문의, 환불·재배달 문의
- 시청 3개: 여권 발급 문의, 주민등록 등본 문의, 대형폐기물 배출
- 고객센터 3개: 인터넷·통화 문제, 요금·약정 상담, A/S 접수

가족·친구·연인·회사에 속한 등록형 자유 대화 시나리오는 모델의 책임과 출력
계약이 다르므로 이 점수에 섞지 않는다. 자유 대화의 말투와 자연스러움은 별도
평가로 관리한다.

## 왜 기존 결과를 최종 근거로 사용할 수 없는가

기존 `experiments/hf_model_eval` 기록은 모델 선택 과정의 역사 자료로 보존한다.
다만 병원 예약 문장 한 건을 중심으로 실행했고, 사람이 1~5점을 부여한 항목이
많아 현재 구조화 NLU 모델의 선택 근거로는 부족하다.

- 16개 상세 그래프를 모두 포함하지 않았다.
- 같은 유형의 발화를 여러 개 평가하지 않아 우연한 성공을 구분할 수 없다.
- 단일 지연시간만 기록해 중앙값과 느린 요청 구간을 알 수 없다.
- 필드 누락, 사실 생성, 행동 분류 실패를 별도 수치로 계산하지 않았다.
- 현재 모델 역할은 자연어 응답 한 문장 생성이 아니라 업무 필드와
  `user_action`을 JSON으로 구조화하는 일까지 포함한다.
- 모델 저장소의 정확한 커밋과 평가 데이터 버전이 결과에 함께 고정되지 않았다.

새 평가는 기존 문서를 덮어쓰지 않는다. 과거 의사결정은 역사로 남기고, 현재
서비스 계약에 맞는 재현 가능한 벤치마크 결과를 별도로 생성한다.

## 평가 단위

### 1. 단일 턴 구조화 추출

모델이 현재 대화 상태와 사용자 발화 한 건을 받아 다음 값을 정확히 반환하는지
평가한다.

- `intent`: 어떤 업무인지 나타내는 고정 코드
- 업무 필드: 날짜, 시간, 주문번호, 문의 유형처럼 발화에서 명시된 값
- `user_action`: 정보 제공, 확인, 수정, 취소, 마무리 같은 현재 행동
- `change_field`: 공통 업무 그래프에서 사용자가 바꾸려는 필드

이 평가는 모델 자체의 추출 성능을 측정한다. LangGraph의 다음 상태 결정이나
응답 문장 생성 결과는 포함하지 않는다.

### 2. 다중 턴 그래프 궤적

단일 턴 추출기가 안정화된 뒤, 여러 발화를 차례로 입력해 다음을 평가한다.

- 이전 턴의 값이 다음 턴에도 보존되는가
- 수정 발화가 기존 값을 정확히 교체하는가
- 누락 필드를 모두 채우면 확인 상태로 이동하는가
- 확인, 취소, 안전 분기, 종료가 허용된 경로로만 이동하는가
- 사용자가 말하지 않은 값이 상태에 새로 생기지 않는가

두 평가를 분리하면 실패 원인이 모델 추출인지 LangGraph 상태 전이인지 구분할
수 있다.

## 골든 데이터 계약

`gold_dataset.schema.json`은 사람이 작성하고 검수한 정답 데이터의 형식을
정의한다. 각 케이스에는 다음 정보가 들어간다.

- 고유한 케이스 ID, 원본 대화 그룹 ID와 데이터 분할
- 시나리오 키와 현재 대화 상태
- 현재까지 검증된 필드, 서버가 제시한 예약 대체 시간과 이번 사용자 발화
- 정답 intent, 정답 user_action, 정답 change_field
- 각 필드가 null이어야 하는지 또는 허용되는 정확한 문자열 목록
- 어려움의 원인을 나타내는 태그
- 작성·검수 상태

값 비교에는 유사도 임계값이나 의미 추측을 사용하지 않는다. 같은 뜻으로 인정할
표현이 여러 개라면 사람이 데이터 작성 시 `accepted_values`에 명시한다. 평가기는
그 목록과 정확히 일치하는지만 판단한다.

`draft`와 `reviewed` 케이스는 점수 계산에 포함하지 않는다. 정답 합의를 마친
`adjudicated` 케이스만 마음콜 프로젝트 내부 공식 벤치마크 결과에 사용할 수 있다.
여기서 `adjudicated`는 오류나 의견 차이를 해결해 정답을 최종 확정한 상태라는
뜻이다. 케이스 안의 상태 문자열과 별도로 검증할 수 있도록 검수 원장이 최종 case
내용의 지문·adjudicator 역할 ID·확정 시각·판단 근거를 함께 보존한다. 검수 원장은
여러 사람이 검토했다거나 특정 인물이 승인했다는 사실을 암호학적으로 증명하지
않으며, 실제 변경 과정은 Git 커밋과 PR 이력으로 함께 추적한다.

현재 구현된 범위는 다음과 같다.

- 16개 라이브 추출 계약과 연결된 골든 데이터 스키마
- 현재 대화 상태에서 허용된 행동만 인정하는 상태-행동 계약
- 확인·완료·변경 같은 행동과 이번 발화에서 새로 추출한 필드가 모순되지 않는지 검사하는 action-field 교차 계약
- 예약 4개에서 선택 시간이 서버가 실제 제시한 대체 시간과 정확히 일치하는지 검사하는 동적 문맥 계약
- 계약 성공률, intent·행동·필드·사실 생성·누락 전역 집계기
- validation과 test 각각에서 상태-행동·행동-필드·시나리오별 난이도 태그 누락을 검사하는 V3 벤치마크 프로필
- 행동 이름의 접두사를 추측하지 않고 35개 라이브 행동의 수정·확인·취소·종료 의미를 명시해 태그와 coverage가 함께 사용하는 단일 계약
- 업무 workflow의 이전 필드 문맥과 예약의 대안시간 제시·미선택·선택 관계를 검사하는 V3 coverage 계약
- 같은 시나리오 안의 긍정 행동↔unknown, 예약 대안 행동, workflow 단계 행동을 명시하고 문자열 유사도 없이 대조하는 contrast manifest 계약
- 대조 묶음 전체의 지문과 검수자 역할 ID·시각·근거를 연결해 관계 변경 시 기존 승인 레코드의 재사용을 막는 검사
- 업무 상태와 현재 필드 값이 실제 그래프 계약에 맞는지 확인하는 검사
- 같은 원본 대화 그룹이 서로 다른 분할에 섞이지 않도록 막는 검사
- development·validation·test를 한 파일에 보존하고 전체 corpus 지문을 고정하는 검사
- `test` 분할과 `adjudicated` 상태를 강제하는 공식 결과 후보용 데이터 관문
- validation·test 케이스와 일대일로 연결되는 버전 지정 작성 지침·검수 원장 계약
- 공식 test 준비와 채점 직전에 작성 지침·검수 원장 지문을 다시 대조하는 검사
- 의미 원본 그룹별 작성 파일을 결정론적 순서의 V2 corpus로 합치는 compiler
- 그룹 파일과 분리된 원장에서 `conversation_group_id`별 split을 한 번만 소유하고, 원장과 작성 그룹의 정확한 일치를 강제하는 검사
- 공식 결과 후보에 split 원장의 의미 기반 SHA-256 식별값을 함께 보존하고 채점 직전에 다시 대조하는 검사
- 라이브 계약과 V3 문맥·대조 정책에서 1,562개 작성 의무를 자동 생성하는 V3 의무 목록
- source·split·compiled corpus·작성 지침·검수 원장·contrast·Coverage V3·AI-origin policy 조합과 입력 Git 커밋을 한 레코드로 고정하는 freeze record V2 계약
- freeze record가 가리킨 Git blob snapshot으로 공식 test를 준비하고 채점 직전에 같은 레코드·artifact·프로필을 다시 검증하는 경계
- 선택형 필드 한 건이 여러 enum 선택지 coverage를 대신하지 못하게 하는 검사
- 작성자가 다른 그룹 ID를 붙여도 완전히 동일한 모델 입력의 corpus 내 중복을 막는 검사
- AI가 만든 제안을 `human_authored` source와 분리하고 16개 시나리오 모두에
  `ai_assisted_unreviewed` hard-negative 시작 제안을 제공하는 draft sidecar 계약

프로필 내용은 정렬된 JSON으로 직렬화한 뒤 SHA-256 지문(프로필 내용 식별값)을
계산한다. 이후 실행 manifest(실행 조건 기록 파일)는 프로필 이름뿐 아니라 이
지문도 저장해야 하므로, 같은 V3 이름 아래 계약 내용이 바뀐 실행을 같은 조건으로
오해하지 않는다. 현재 V3는 action-field 규칙, 업무 현재 문맥, 예약 대안시간
관계와 contrast 역할 정책도 지문에 포함한다. 기대 지문을 코드에
고정했기 때문에 이 채점 계약이 바뀌면 자동 테스트가 중단되며, 기존 지문을
덮어쓰는 대신 새 프로필 버전을 만들어야 한다.

작은 사용자 정의 프로필은 개발 중 검사에만 사용할 수 있다. 공식 결과 후보용
test slice는 호출자가 명시한 versioned freeze record 경로가 없으면 준비할 수 없다.
검증기는 레코드가 가리키는 입력 Git 커밋의 source·split·compiled corpus·작성 지침·
검수 원장·contrast manifest·Coverage V3 의무 목록 blob을 불변 snapshot으로 읽는다.
현재 작업 파일도 그 snapshot과 정확히 같은지 확인하며, validation과 test coverage,
프로필·데이터 지문을 다시 계산한다. 최종 점수 계산 직전에도 같은 레코드와 Git
snapshot을 다시 검증한다. `latest`나 `current` 같은 움직이는 기본 경로는 사용하지 않는다.
이 과정에서 수동 조립된 프로필·데이터의 불일치, 컴파일 산출물의 직접 수정과
test-only 축소를 거부하지만,
지문 자체는 인증이나 전자서명이 아니라 내용이 같은지 확인하는 식별값이다.
freeze record 파일 자체도 현재 Git `HEAD`에 커밋된 정확한 blob과 같아야 한다.
다만 SHA-256과 일반 Git 이력은 승인자의 실제 신원을 증명하지 않는다.

`benchmark.py`의 밑줄(`_`)로 시작하는 준비·채점 함수는 단위 테스트와 내부 조합을
위한 저수준 함수이며 공식 결과 발행 경계가 아니다. 작성 원본만 받는 준비·채점
함수도 내부 저수준 함수로 내렸다. 현재 공개 공식 준비·채점 경계는 호출자가 명시한
freeze record를 필수로 요구한다. 향후 실모델 실행기와 결과 manifest도 이 공개
경계만 사용하고, 검증된 record fingerprint가 없는 저수준 점수를 공식 결과로
직렬화하지 않아야 한다.

여기서 `corpus`는 development·validation·test를 모두 포함한 평가 원본 전체
묶음이고, `test slice`는 그 corpus 중 `test` 분할에 속하면서 고정 프로필의
검사 조건을 모두 만족한 케이스 묶음이다. 상태와 행동을 각각 한 번 포함하는
것만으로는 부족하다. 예를 들어 `confirming` 상태에서 `cancel`이 허용된다면
그 상태-행동 조합 자체가 데이터에 있어야 한다. 배달·시청·고객센터의 공통
workflow 기반 상세 그래프는 현재 필드 문맥도 검사하므로, 확인 상태라면 필수 필드가 모두
채워져야 하고 선택형 필드는 계약에 선언된 값만 사용해야 한다.

아직 구현하지 않은 범위는 실제 골든 데이터와 그 데이터에 대응하는 split 원장·
검수 원장·contrast manifest·실제 freeze record, 실모델 실행기,
시나리오·태그별 집계, p50·p95·토큰·메모리 측정, 실행 manifest와 결과 파일이다.
따라서 현재 단위 테스트 수치는 후보 모델의 성능 점수가 아니다.

## 정답 작성 지침과 검수 원장

`guidelines/annotation-guideline.v1.md`는 필드의 `null` 판정, 행동과 이번 발화
필드의 관계, 예약 대안 시간, 난이도 태그, 개인정보 금지, split 배정과
`draft → reviewed → adjudicated` 승격 기준을 고정한다. 파일의 UTF-8 바이트에서
계산한 SHA-256을 코드에 고정했기 때문에 내용을 조용히 바꾸면 자동 검사가
중단된다. 기준을 바꿀 때는 기존 V1을 덮어쓰지 않고 새 지침 버전을 만든다.

`review_ledger.schema.json`은 validation과 test의 최종 정답마다 다음을 요구한다.

- case ID와 최종 case 전체 내용의 SHA-256
- 적용한 작성 지침 ID와 지침 파일 SHA-256
- 운영 규칙상 개인정보 대신 사용하는 adjudicator 역할 ID
- 시간대가 포함된 확정 시각과 판단 근거
- `approved` 결정

검증기는 validation·test case와 원장 항목의 ID 집합이 정확히 같은지 확인하고,
모든 case가 `adjudicated`인지 검사한다. 정답·상태·split·태그 중 하나라도 바뀌면
case 지문이 달라져 과거 승인을 재사용할 수 없다. development는 작성과 디버깅을
위한 영역이므로 이 최종 승인 원장의 필수 대상이 아니다.

검증기는 adjudicator ID의 소문자 영숫자 형식만 확인한다. 해당 값이 실제로
가명인지, 독립된 다른 사람이 검토했는지, 특정 계정 소유자가 승인했는지는
증명하지 않는다. 원장 전체의 의미 기반 지문은 공식 test 준비 결과에 보존되고
채점 직전에 다시 대조한다. 어떤 source·split·검수·contrast·coverage 조합을 모델
승인 대상으로 정했는지는 versioned freeze record가 함께 고정한다.

이 구현은 **검수 원장의 형식·검증기와 공식 test 경계 연결**을 만든 단계다. 실제 corpus가 없으므로
가짜 항목이나 임시 adjudicator를 넣은 원장 파일은 만들지 않았다. 실제 원장은
사람이 작성한 validation·test case가 생긴 뒤에만 생성·검수한다.

## Versioned freeze record

`freeze_record.schema.json`은 어떤 평가 조합을 승인 대상으로 정했는지
기록하는 확인서 형식이다. split을 배정하는 원장 자체가 아니라, 다음 artifact와
계약의 정확한 조합을 한 레코드로 묶는다.

- 작성 그룹 source, split 배정 원장, compiled corpus의 raw·semantic 지문
- 작성 지침, validation·test 검수 원장, contrast manifest 지문
- Coverage V3 의무 manifest와 공식 프로필·coverage·contrast 정책 지문
- 공식 corpus에서 그대로 승격할 수 없는 AI 원문·예약 ID를 고정한 AI-origin policy V1의 raw·semantic 지문
- dataset·state·authoring·split·review·contrast의 서로 독립적인 버전
- split별 case 수와 전체 group·case ID 집합 지문
- 이 입력들이 커밋된 정확한 Git object format과 full commit SHA

레코드는 자신을 제외한 입력이 모두 들어 있는 커밋 A를 가리킨다. 레코드 파일은
그다음 커밋 B에 추가하므로 자신의 커밋 SHA를 자기 안에 넣는 순환이 생기지 않는다.
공식 검증 시에는 커밋 A의 Git blob을 직접 읽어 하나의 불변 snapshot으로 검증하고,
현재 작업 파일도 같은 바이트인지 확인한다. 레코드 파일 자체는 현재 Git `HEAD`에
커밋된 정확한 blob이어야 한다.

첫 revision은 이전 레코드가 없어야 한다. 다음 revision은 임의의 SHA 문자열이 아니라
호출자가 revision 1부터 순서대로 명시한 모든 이전 레코드 파일을 읽어 같은 `freeze_id`,
연속 revision, 직전 지문을 확인한다. 각 과거 레코드가 가리킨 Git 입력 artifact와 자신의
지문도 과거 커밋에서 다시 검증하며, 과거 artifact가 현재 작업 파일과 같을 필요는 없다.
생성·공식 준비·채점은 모두 같은 전체 계보를 검증한다. 새 레코드는 기존 경로를 덮어쓰지 않고 새 파일로만
원자적으로 생성한다. 절대경로, `..`, source 내부 출력, symbolic-link 경로와
`latest` 기본 탐색은 허용하지 않는다.

`record_fingerprint`는 레코드 전체 내용, `benchmark_identity_fingerprint`는 corpus의
의미·split·검수·contrast·평가 정책 조합을 식별한다. 둘 다 변경 탐지용 SHA-256이며
전자서명이나 승인자 신원 증명이 아니다. 더 강한 공개 후 승인 증명이 필요하면
별도의 서명된 Git tag 또는 외부 보관 정책이 필요하다.
레코드 자체는 실제 사람이 모델 결과를 보기 전에 검토했다는 시점까지
증명하지 않으므로, 사전 승인 순서는 레코드를 먼저 리뷰·병합하는 Git/PR 이력과
후속 실행 manifest에서 관리해야 한다.

현재 생성 형식은 **freeze record V2**다. V2는 V1의 source·split·검수·contrast·coverage
조합에 AI-origin policy V1의 경로, 정확한 artifact SHA-256, semantic policy fingerprint와
schema version을 추가한다. V1 모델과 해시 알고리즘은 과거 레코드 해석을 위해 코드에
남기지만, 새 레코드는 V2로만 생성한다. 실제 source·원장·corpus가 없으므로 실제 freeze record 파일을 만들거나
데이터셋 동결이 끝났다고 기록하지 않는다.

## 작성 원본과 compiler

AI가 만든 문장을 곧바로 `human_authored` 골든 데이터로 저장하지 않는다.
`drafts/ai-assisted-seeds.v1.json`은 16개 구조화 NLU 시나리오마다 한 건씩 총 16건의
초기 hard-negative 제안을 담은 **공식 corpus 밖 sidecar**다. 모든 제안은
`provenance: ai_assisted_unreviewed`와 `human_review_required: true`를 가지며,
라이브 상태·행동·필드 계약과 Coverage V3의 `greeting→unknown` 의무에 맞는지만
검사한다. 이 파일에는 split이나 `review_status`가 없고 compiler 입력으로 사용할 수
없다. 제안 문장과 `ai-seed-*` ID를 그대로 복사해 `human_authored`라고 표시하는 것도
compiler가 거부한다. 사람은 제안을 참고 자료로만 사용하고, 작성 지침에 따라
문장과 정답을 직접 새로 작성해 별도 `AuthoringGroup` source로 만들어야 한다.
이 작성 단계도 검수 완료나 `adjudicated` 승격을 뜻하지 않는다.

`drafts/human-review-packet.v1.md`는 16개 제안의 시나리오·상태·기준 의무·제안
정답을 한곳에서 보고, 사람이 새 그룹 ID·case ID·발화·최종 정답·판단 근거를
작성하도록 만든 결정론적 작업지 원본이다. 이 파일 자체도 승인 원장이나 골든
데이터가 아니다. 커밋된 원본은 AI 제안과 계약이 바뀌었는지 검사하는 템플릿이므로
직접 채우지 않고 작업용 사본을 만들어 작성한다. 자동 importer를 두지 않아 빈
체크박스나 placeholder가 실수로 공식 source에 들어가는 경로도 만들지 않는다.

`drafts/subagent-assisted-candidates.v1.json`은 서브 에이전트 보조로 작성하고
라이브 계약으로 검증한 두 번째 AI 후보 묶음이다. 16개 시나리오마다 원래 seed와
다른 발화 한 건과
짧은 계약 판단 근거를 담지만 provenance는 계속 `ai_assisted_unreviewed`이고
`automatic_promotion_allowed: false`다. 대응하는
`drafts/subagent-human-review-packet.v1.md`도 사람이 새 표현·정답·근거를 쓰기
위한 참고 양식일 뿐 compiler 입력이나 승인 증거가 아니다. 원본 seed와 서브
에이전트 후보의 ID·발화는 모두 공식 source로 그대로 승격할 수 없다. 발화 차단은
시나리오나 ID에 의존하지 않고 NFC로 정규화한 정확한 원문 지문을 전역 대조하므로,
한글 조합형만 바꾸거나 다른 시나리오로 옮기는 우회도 거부한다. 유사도 임계값이나
공백 보정 같은 휴리스틱은 사용하지 않는다. 코드가 실제 인간 저작이나 재검토
사실을 증명하지는 않으므로 최종 책임은 사람이 새로 쓴 source와 검수 원장에 남긴다.
32개 원문의 ID·종류·시나리오·NFC 지문은
`manifests/ai-origin-policy.v1.json`에 결정론적으로 저장한다. V1 정책 지문은 코드에
고정되어 있으므로 기존 파일을 바꾸면 검사가 중단된다. 후보를 더 추가할 때는 V1을
덮어쓰지 않고 새 정책 버전과 이에 대응하는 작성·freeze 계약 버전을 만들어야 한다.
현재 실제 사람 작성 source나 freeze record가 없으므로 이 단계에서는 정책 형식과
차단 경계만 구현한 것이며, 데이터셋 동결을 완료한 것은 아니다.

```bash
# 편집기용 AI 초안 제안 schema와 16개 시작 제안을 재생성한다.
python -m scripts.compile_structured_nlu_corpus draft-schema \
  evals/structured_nlu/ai_draft_seed.schema.json
python -m scripts.compile_structured_nlu_corpus draft-seeds \
  evals/structured_nlu/drafts/ai-assisted-seeds.v1.json

# 커밋된 sidecar가 현재 16개 라이브 계약과 정확히 같은지 검사한다.
python -m scripts.compile_structured_nlu_corpus check-draft-schema \
  evals/structured_nlu/ai_draft_seed.schema.json
python -m scripts.compile_structured_nlu_corpus check-draft-seeds \
  evals/structured_nlu/drafts/ai-assisted-seeds.v1.json

# 16개 제안을 사람이 다시 작성할 작업지 원본을 생성·검사한다.
python -m scripts.compile_structured_nlu_corpus draft-review-packet \
  evals/structured_nlu/drafts/human-review-packet.v1.md
python -m scripts.compile_structured_nlu_corpus check-draft-review-packet \
  evals/structured_nlu/drafts/human-review-packet.v1.md

# 서브 에이전트 후보·schema·사람 작성용 참고 작업지를 생성·검사한다.
python -m scripts.compile_structured_nlu_corpus draft-subagent-schema \
  evals/structured_nlu/ai_subagent_candidate.schema.json
python -m scripts.compile_structured_nlu_corpus draft-subagent-candidates \
  evals/structured_nlu/drafts/subagent-assisted-candidates.v1.json
python -m scripts.compile_structured_nlu_corpus draft-subagent-review-packet \
  evals/structured_nlu/drafts/subagent-human-review-packet.v1.md
python -m scripts.compile_structured_nlu_corpus check-draft-subagent-schema \
  evals/structured_nlu/ai_subagent_candidate.schema.json
python -m scripts.compile_structured_nlu_corpus check-draft-subagent-candidates \
  evals/structured_nlu/drafts/subagent-assisted-candidates.v1.json
python -m scripts.compile_structured_nlu_corpus check-draft-subagent-review-packet \
  evals/structured_nlu/drafts/subagent-human-review-packet.v1.md
python -m scripts.compile_structured_nlu_corpus ai-origin-policy \
  evals/structured_nlu/manifests/ai-origin-policy.v1.json
python -m scripts.compile_structured_nlu_corpus check-ai-origin-policy \
  evals/structured_nlu/manifests/ai-origin-policy.v1.json
```

실제 corpus는 하나의 거대한 JSON을 직접 편집하지 않는다. 같은 의미 원본에서
파생된 문장 묶음을 `AuthoringGroup` 파일 하나로 관리하고, 그룹이
`conversation_group_id`와 `scenario_key`를 한 번만 소유한다. split은 그룹 파일에
적지 않고 별도의 `split-assignments.v1.json` 원장만 소유한다. compiler는 원장에
없는 그룹과 실제 그룹이 없는 원장 항목을 모두 거부한다. 같은 원본의 일부 문장만
다른 split에 넣거나 그룹 파일에서 배정을 몰래 덮어쓰는 경로를 구조적으로 막기
위해서다.

compiler는 작성 파일을 `(scenario_key, conversation_group_id, case.id)` 순서로
정렬해 현재 `GoldDataset` V2 형식으로 만든다. 파일 탐색 순서나 운영체제가 달라도
같은 입력에서 같은 결과와 지문을 얻기 위한 규칙이다. 컴파일된 JSON은 모델
평가 입력용 산출물이며 작성 원본이 아니다. `authoring_group.schema.json`과
`split_assignment.schema.json`은 편집기가 필수 키·타입·허용값 오류를 작성 중에
알려 주는 파일이다. 두 파일 모두 수동으로 고치지 않고 코드 계약에서 생성한다.
편집기 Schema는 1차 형식 검사이고,
시나리오별 상태·행동·필드의 교차 관계는 compiler가 라이브 계약으로 최종 검사한다.

`authoring_schema_version: 2`는 split을 제거한 그룹 원본 형식이고,
`split_assignment_schema_version: 1`은 별도 split 원장 형식의 첫 버전이다.
`dataset_version: 2`와 공식 프로필 V3는 컴파일된 평가 corpus와 채점 계약의
버전이므로 서로 다른 대상을 관리한다. 이 숫자들은 같을 필요가 없다.

```bash
# 현재 라이브 계약에서 작성해야 할 항목을 다시 생성한다.
python -m scripts.compile_structured_nlu_corpus obligations \
  evals/structured_nlu/manifests/coverage-obligations.v3.json

# 커밋된 의무 목록이 현재 라이브 계약과 같은지 검사한다.
python -m scripts.compile_structured_nlu_corpus check-obligations \
  evals/structured_nlu/manifests/coverage-obligations.v3.json

# 편집기용 작성 원본 JSON Schema를 코드 계약에서 다시 생성한다.
python -m scripts.compile_structured_nlu_corpus schema \
  evals/structured_nlu/authoring_group.schema.json

# 커밋된 작성 원본 JSON Schema가 코드 계약과 같은지 검사한다.
python -m scripts.compile_structured_nlu_corpus check-schema \
  evals/structured_nlu/authoring_group.schema.json

# split 원장 JSON Schema를 생성하고 커밋된 파일과 대조한다.
python -m scripts.compile_structured_nlu_corpus split-schema \
  evals/structured_nlu/split_assignment.schema.json
python -m scripts.compile_structured_nlu_corpus check-split-schema \
  evals/structured_nlu/split_assignment.schema.json

# 검수 원장 JSON Schema를 생성하고 커밋된 파일과 대조한다.
python -m scripts.compile_structured_nlu_corpus review-schema \
  evals/structured_nlu/review_ledger.schema.json
python -m scripts.compile_structured_nlu_corpus check-review-schema \
  evals/structured_nlu/review_ledger.schema.json

# 대조군 manifest JSON Schema를 생성하고 커밋된 파일과 대조한다.
python -m scripts.compile_structured_nlu_corpus contrast-schema \
  evals/structured_nlu/contrast_groups.schema.json
python -m scripts.compile_structured_nlu_corpus check-contrast-schema \
  evals/structured_nlu/contrast_groups.schema.json

# freeze record JSON Schema를 생성하고 커밋된 파일과 대조한다.
python -m scripts.freeze_structured_nlu_benchmark schema \
  evals/structured_nlu/freeze_record.schema.json
python -m scripts.freeze_structured_nlu_benchmark check-schema \
  evals/structured_nlu/freeze_record.schema.json

# 그룹별 작성 원본을 단일 V2 corpus로 컴파일한다.
python -m scripts.compile_structured_nlu_corpus compile \
  evals/structured_nlu/data/source \
  evals/structured_nlu/manifests/split-assignments.v1.json \
  evals/structured_nlu/data/compiled/gold-dataset.v2.json

# 커밋된 corpus가 작성 원본에서 다시 생성한 결과와 같은지 검사한다.
python -m scripts.compile_structured_nlu_corpus check \
  evals/structured_nlu/data/source \
  evals/structured_nlu/manifests/split-assignments.v1.json \
  evals/structured_nlu/data/compiled/gold-dataset.v2.json

# 실제 corpus가 생긴 뒤 별도 명령으로 validation·test의 최종 검수 원장을 대조한다.
python -m scripts.compile_structured_nlu_corpus check-review \
  evals/structured_nlu/data/source \
  evals/structured_nlu/manifests/split-assignments.v1.json \
  evals/structured_nlu/data/compiled/gold-dataset.v2.json \
  evals/structured_nlu/guidelines/annotation-guideline.v1.md \
  evals/structured_nlu/manifests/review-ledger.v1.json

# 실제 corpus가 생긴 뒤 validation·test의 대조 역할 exact-set을 검사한다.
python -m scripts.compile_structured_nlu_corpus check-contrast \
  evals/structured_nlu/data/source \
  evals/structured_nlu/manifests/split-assignments.v1.json \
  evals/structured_nlu/data/compiled/gold-dataset.v2.json \
  evals/structured_nlu/manifests/contrast-groups.v1.json

# 실제 artifact를 모두 커밋한 뒤 그 입력 커밋으로 첫 freeze record를 만든다.
# 모든 artifact 경로는 repo root 기준 상대경로이며 output은 기존 파일을 덮어쓰지 않는다.
python -m scripts.freeze_structured_nlu_benchmark create \
  --repo-root . \
  --freeze-id structured-nlu-corpus \
  --freeze-revision 1 \
  --input-git-revision <full-input-commit-sha> \
  --group-source-root evals/structured_nlu/data/source \
  --split-assignment-path evals/structured_nlu/manifests/split-assignments.v1.json \
  --compiled-corpus-path evals/structured_nlu/data/compiled/gold-dataset.v2.json \
  --annotation-guideline-path evals/structured_nlu/guidelines/annotation-guideline.v1.md \
  --review-ledger-path evals/structured_nlu/manifests/review-ledger.v1.json \
  --contrast-manifest-path evals/structured_nlu/manifests/contrast-groups.v1.json \
  --obligation-manifest-path evals/structured_nlu/manifests/coverage-obligations.v3.json \
  --ai-origin-policy-path evals/structured_nlu/manifests/ai-origin-policy.v1.json \
  --output evals/structured_nlu/freezes/structured-nlu-corpus.r1.json

# record 파일을 다음 커밋에 추가한 뒤, 명시한 record와 현재 Git blob을 다시 검증한다.
# revision 2 이상은 --previous-record를 반복해 revision 1부터의 모든 이전 파일을 순서대로 넘긴다.
python -m scripts.freeze_structured_nlu_benchmark verify \
  --repo-root . \
  --record evals/structured_nlu/freezes/structured-nlu-corpus.r1.json
```

역사 기준인 `coverage-obligations.v2.json`은 865개 의무와 상태-행동 352개를
그대로 보존한다. 현재 `coverage-obligations.v3.json`에는 의미상 불가능했던 업무
greeting→change 조합 9개를 제거한 상태-행동 343개와 시나리오별 태그, 이전 필드
문맥, 대안시간 관계, contrast 역할을 합쳐 총 1,562개의 계약 의무가 들어 있다.
이 파일은 실제 corpus가 의무를 얼마나 채웠는지
보여 주는 진척 보고서가 아니라, 무엇을 작성해야 하는지 나열한 inventory다.
전체 숫자만 남기지 않고 16개 차원별 개수와 16개 구조화 NLU 시나리오별 의무
개수도 같은 파일에 기록한다. 라이브 계약이 바뀌어 숫자가 달라지면
`check-obligations`와 회귀 테스트가 커밋된 목록의 불일치를 실패시킨다.
여러 차원을 한 케이스가 함께 충족할 수 있으므로 1,562개가 곧 필요한 문장 수라는
뜻은 아니다. validation과 test는 각각 343개 상태-행동 의무를 담아야 하므로
각 split에는 최소 343개 case가 필요하다. 이는 사용자 문장 문자열이 모두 서로 달라야 한다는
뜻이 아니라, 각 case가 하나의 시나리오·상태·행동 조합만 담당하기 때문에 생기는
구조적 하한이다.

V3 contrast는 이 구조화 NLU 평가기가 직접 예측하지 않는 시나리오 라우팅을
대신 평가한다고 주장하지 않는다. 동일 시나리오 안에서 비교할 역할과 공유해야 할
상태·현재 필드·서버 제시 후보를 정책으로 고정하고, manifest가 각 case 전체의
지문을 가리키도록 한다. 대조 묶음 전체도 별도 지문을 계산해 검수자 역할 ID·시각·
근거와 함께 승인 레코드에 묶는다. 케이스·역할·혼동 축을 바꾸면 기존 레코드를
재사용할 수 없다.
문장 의미가 실제 혼동 축에 맞는지는 이 사람 검수 기록으로 명시하며 임의의 문자열
유사도 임계값으로 판정하지 않는다. 역할 ID는 운영용 가명 형식만 검사하므로 실제
신원이나 다중 독립 검토, 실제 사람이 다시 읽고 승인했다는 사실을 암호학적으로
증명하지 않는다.

난이도 태그 중 수정·확인·취소·종료처럼 행동 계약으로 판정할 수 있는 항목은
행동 이름의 `change_`·`confirm_` 접두사로 추측하지 않는다. 현재 35개 라이브
행동마다 의미 태그를 정확히 한 번 선언하고, 데이터 태그 검사·V3 적용 범위·
action-field 의무가 같은 선언을 사용한다. 새 행동 선언이 빠지거나 삭제된 행동이
남으면 계약 초기화와 회귀 테스트가 실패한다.

V2 manifest는 정적 감사 이력으로 byte 지문을 고정해 보존한다. V2 실행 코드는
당시 Git 리비전이 재생 경계이며, 현재 V3 코드가 과거 V2 지문을 새 알고리즘으로
재계산한다고 주장하지 않는다.

`accepted_values`는 비선택형 문자열에서 모델 출력으로 허용할 정확한 정규화
결과를 기록한다. enum처럼 선택지가 정해진 필드는 케이스당 하나의 canonical
value만 허용한다. 한 문장에 서로 다른 선택지 여러 개를 넣어 여러 문제를 시험한
것처럼 coverage를 부풀릴 수 없게 하기 위해서다.

## 데이터 분할

- `development`: 프롬프트와 출력 계약을 개발할 때 사용한다.
- `validation`: 후보 설정과 재시도 정책을 선택할 때 사용한다.
- `test`: 최종 모델 선택에 한 번 사용한다. 결과를 확인한 뒤 프롬프트를 고치면
  새 데이터 버전으로 다시 분리한다.

같은 문장을 조금만 바꾼 사례나 동일한 대화 템플릿이 서로 다른 분할에 들어가면
모델이 사실상 본 문제를 다시 푸는 결과가 된다. 따라서 유사 문장과 같은 원본
대화에서 파생된 케이스는 `conversation_group_id`로 묶는다. 그룹의 split은 모델
결과를 보기 전에 별도 원장에 기록하고 Git 이력으로 고정한다. compiler는 그룹
파일이 split을 직접 소유하는 것을 거부하고, 원장과 실제 작성 그룹의 ID 집합이
정확히 같아야만 corpus를 만든다.

split 원장에는 내용에서 계산한 별도 SHA-256 식별값이 있다. 공식 test slice를
준비할 때 이 값을 기록하고 최종 채점 직전 다시 대조한다. 배정을 바꾸면 새 값과
새 corpus가 만들어지므로 이전 실행과 같은 조건으로 기록할 수 없다. 다만 이 값은
전자서명이 아니므로, 실제 후보 실행 전에는 원장을 먼저 커밋하고 이후 변경은
데이터 버전 변경과 PR 검토를 통해 관리한다.

그룹 ID는 사람이 지정하므로 비슷한 문장끼리 같은 그룹에 배정하는 검수는 여전히
필요하다. 이와 별개로 compiler는 시나리오, 상태, 현재 필드, 서버 제시 후보,
사용자 발화가 유니코드 NFC 정규화 뒤 완전히 같은 모델 입력이면 split이나 그룹
ID가 달라도 corpus 전체에서 결정론적으로 거부한다. 동일 입력의 반복 안정성은
case 복제가 아니라 후속 runner의 반복 실행 축으로 측정한다. 유사도 임계값으로
문장을 임의 판정하지는 않는다.

공식 결과 후보 관문은 test만 떼어 낸 파일을 받지 않는다. 세 분할을 모두 담은
하나의 corpus와 그 전체 지문을 요구하고, 채점 직전에 corpus에서 test slice를
다시 추출한다. 따라서 공식 입력을 test-only 파일로 축소해 누수 검사를 빈 비교로
만드는 우회를 차단한다.

`single_field`, `multi_field`, `correction`, `confirmation`, `cancellation`,
`closing`, `safety`처럼 정답 계약에서 계산할 수 있는 태그는 조건과 태그를
양방향으로 검사한다. 예를 들어 정답 필드가 하나라면 반드시 `single_field`가
있어야 한다. `ambiguous`, `colloquial`, `hard_negative`처럼 문맥 판단이 필요한
태그는 사람이 검수한다.

모든 문장은 실제 사용자 기록을 복사하지 않고 프로젝트 요구사항에 맞춰 직접
작성한다. 개인정보, 실제 주문번호, 실제 학생·고객 이름은 넣지 않는다.

## 수치 지표

### 계약 안정성

- **첫 시도 계약 성공률**: 재시도 없이 JSON 파싱과 도메인 검증을 통과한 비율
- **최종 계약 성공률**: 최대 2회 시도 안에 계약을 통과한 비율
- **재시도율**: 첫 출력 실패로 두 번째 호출이 필요했던 비율
- **완전 실패율**: 두 번 모두 실패해 서비스 오류가 되는 비율

### 의미 정확도

- **intent 정확도**: 정답 업무 코드와 정확히 일치한 비율
- **user_action 정확도와 macro F1**: 행동 종류별 성능을 동일 비중으로 계산
- **change_field 정확도**: 수정 발화에서 바꿀 필드를 정확히 찾은 비율
- **필드 존재 slot-micro precision·recall·F1**: 모든 필드 판정을 합쳐 값이 있는
  필드와 null 필드를 구분하는 성능
- **필드 값 정확 일치율**: 값이 있어야 하는 필드가 허용 정답 중 하나와 일치한 비율
- **사실 생성률**: 정답은 null인데 모델이 값을 만들어낸 필드의 비율
- **필드 누락률**: 정답에는 값이 있는데 모델이 null을 반환한 필드의 비율

필드 존재와 값 관련 지표는 최종 출력이 실제 시나리오 계약을 통과한 케이스만
계산한다. JSON 파싱 실패나 허용되지 않은 필드·선택값처럼 구조화 출력 자체가
유효하지 않은 케이스는 계약 성공률과 완전 실패율에 반영한다. 계약 실패를 모든
필드가 null인 정상 출력으로 간주하면 누락률과 사실 생성률의 의미가 왜곡되기
때문이다.

후속 집계기에서는 전체 평균뿐 아니라 16개 시나리오별 점수와 `correction`,
`negation`, `colloquial`, `ambiguous`, `hard_negative`, `safety` 같은 난이도 태그별
점수를 함께 기록한다. 현재 구현은 전체 집계까지만 제공한다.

### 후속 실행기에서 측정할 성능

- 모델 최초 로드 시간
- 워밍업 이후 요청 지연시간 p50과 p95
- 초당 생성 토큰 수
- 입력·출력 토큰 수
- 측정 가능한 장치의 최대 메모리 사용량

`p50`은 요청 절반이 그 시간 안에 끝났다는 뜻이고, `p95`는 100번 중 느린 쪽
5번을 제외한 대부분의 요청이 그 시간 안에 끝났다는 뜻이다. 단 한 번의 빠른
결과 대신 실제 사용자가 겪을 수 있는 느린 구간까지 확인하기 위해 둘 다 기록한다.

## 비교 조건

실제 정확도 비교 실행기를 구현할 때 다음 조건을 모든 모델에 동일하게 적용한다.

- Python, PyTorch, Transformers 버전 고정
- 동일한 장치와 dtype 사용
- 각 모델의 공식 chat template 사용
- `do_sample=False`로 확률 표본 추출 비활성화
- 동일한 최대 출력 토큰과 재시도 횟수 사용
- 모델명뿐 아니라 Hugging Face 커밋 SHA 고정
- 동일한 데이터 버전과 동일한 케이스 순서 사용
- 양자화 모델과 원본 정밀도 모델을 한 표에서 직접 순위 비교하지 않음

후속 실행기는 Git 커밋, 데이터 버전, 모델 리비전, 프롬프트 버전, 라이브러리
버전, 장치 정보와 실행 시각을 manifest에 함께 저장해야 한다.

## 마음콜 프로젝트 내부 공식 결과 조건

다음 조건을 모두 만족한 `test` 실행만 마음콜 프로젝트 내부 공식 벤치마크
결과라고 부른다.

1. validation과 test가 각각 고정 V3 프로필의 상태-행동·행동-필드·현재 문맥·
   예약 대안시간 관계·시나리오별 난이도 태그 coverage와 contrast 역할 검사를 통과한다.
2. `test` 분할만 사용하고 모든 케이스가 `adjudicated` 상태이다.
3. 세 분할을 모두 담은 단일 corpus와 대화 그룹 배정, corpus 지문을 보존한다.
4. 데이터 버전, 모델 리비전, 프롬프트 버전, 런타임(실행 환경)과 Git 리비전을
   고정한다.
5. 실행 manifest(실행 조건 기록 파일)와 원시 예측 결과를 보존한다.

`coverage`는 점수가 높다는 뜻이 아니다. 시험에 포함해야 할 범위가 빠지지
않았는지 보는 검사다. 현재 V3 프로필은 각 coverage 요소가 최소 한 번 등장하는
범주형 완전성만 강제한다. 케이스 개수가 통계적으로 충분하다는 뜻은 아니며,
실제 파일럿 결과의 실패 분포를 근거로 다음 프로필에서 표본 수를 확장한다.

## 비교 후보

첫 내부 공식 비교는 다음 역할을 가진 후보군을 검토 대상으로 시작한다. 실제
실행 전 각 모델의 리비전, 라이선스, 로딩 방식과 현재 서버 호환성을 확인해
manifest에 고정한다. 이 관문을 통과하기 전에는 실행 승인된 후보 또는 비교
완료로 간주하지 않는다.

| 후보 | 비교 역할 |
|---|---|
| `kakaocorp/kanana-1.5-2.1b-instruct-2505` | 현재 서비스 기준선 |
| `kakaocorp/kanana-2-1.3b-instruct` | 더 작은 최신 Kanana 후보 |
| `kakaocorp/kanana-2-3b-instruct` | 최신 Kanana 품질 후보 |
| `LGAI-EXAONE/EXAONE-4.0-1.2B` | 기존 속도 기준선 |
| `naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B` | 한국어 특화 비교군 |

Kanana 2 1.3B의 공식 모델 카드는 저장소의 사용자 정의 모델 코드를 불러오는
`trust_remote_code`가 필요하다고 명시한다. 현재 서버는 원격 코드를 실행하지
않는 표준 `Transformers` 로딩 경계를 사용하므로, 별도의 보안 검토와 격리된
호환성 검증 없이는 이 후보를 실행 대상에 넣지 않는다. Kanana 2 1.3B와 3B는
Kanana Open License이고 기존 Kanana 1.5와 라이선스가 다르므로 후보별 사용 조건도
각각 검토한다.

## 선택 규칙

서로 다른 지표를 임의의 가중치로 더해 하나의 종합 점수를 만들지 않는다. 높은
속도가 사실 생성이나 상태 오판을 가리는 일을 막기 위해 다음 순서로 판단한다.

1. JSON과 도메인 계약을 안정적으로 통과하는가
2. `user_action`과 필드 존재 여부를 정확히 판단하는가
3. 필드 값을 정확히 추출하고 사실을 만들지 않는가
4. 16개 시나리오와 어려운 태그에서 성능 편차가 작은가
5. 앞 조건을 충족한 후보 중 지연시간과 메모리가 운영 범위에 맞는가

새 모델이 현재 Kanana보다 일부 지표만 높고 안전 관련 실패가 늘어나면 교체하지
않는다. 모델 교체는 전체 평균이 아니라 실패 사례와 서비스 영향까지 검토한 뒤
결정한다.
