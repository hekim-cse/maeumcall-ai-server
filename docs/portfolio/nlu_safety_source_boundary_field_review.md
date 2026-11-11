# GB01–GB24 전체 필드 검토 초안

**상태: AI 작성 라벨 초안·사용자 미검수·모델 미실행.** [채택된 문장·방향](nlu_safety_source_boundary_fresh_review.md)에 대해 모든 비교 필드와 공란을 제안한다. 숫자는 원문 문장 번호다. `대상`은 접수 대상의 원문 구절, `사건`은 위험 사실이나 위험 주제를 담은 원문 구절, `주체`는 **물리적 위험 주체의 원문 구절**이다. 인용은 해당 문장에 연속으로 등장한다. 자료 속 가정·영상·안내와 출처 불명 문맥에 물리적 주체를 억지로 지정하지 않는다.

`current`는 접수 제품 자체·소속 부품, `other`는 별도 실체 또는 자료에만 있는 위험, `unknown`은 출처 미확정, `none`은 위험 사건 자체를 특정하지 못한 상태다. `observed`는 발생 관찰, `uncertain`은 발생 자체가 불확실하거나 전언, `nonoccurring`은 가정·일반 자료, `none`은 위험 사건 없음이다. `none/none`이면 대상·사건 번호도 공란이어야 한다. 아래에서 적지 않은 **추가 필드·대체 주체·허용 정답은 모두 공란**으로 제안한다. 검수 전 정답으로 확정하지 않는다.

초안 분모는 현재 제품 실제 위험 6건, 다른 출처 실제 위험 6건, 출처 불명 6건, 미발생 위험 주제 4건, 위험 사건 없음 2건이다. 합계 24건이며, GB15 등 검수 판단이 바뀌면 이 분모도 다시 계산한다.

| ID | 대상 번호·원문 구절 | 사건 번호·원문 구절 | 주체 번호·원문 구절 | 관계 / 발생 | 기대 경로 |
| --- | --- | --- | --- | --- | --- |
| GB01 | 1 `현관 스마트 도어락` | 2 `뜨거워졌어요` | 2 `도어락 배터리 덮개` | `current / observed` | `safety_action_required` |
| GB02 | 1 `현관 스마트 도어락` | 2 `뜨거워졌어요` | 2 `디지털 초인종의 배터리 덮개` | `other / observed` | `collecting_service_request` |
| GB03 | 1 `프린터` | 2 `연기가 났어요` | 2 `프린터 전원 코드` | `current / observed` | `safety_action_required` |
| GB04 | 1 `프린터` | 2 `연기가 났어요` | 2 `책상 스탠드 전원 코드` | `other / observed` | `collecting_service_request` |
| GB05 | 1 `캠핑용 전기랜턴` | 2 `연기가 났어요` | 2 `제 전기랜턴 충전 단자` | `current / observed` | `safety_action_required` |
| GB06 | 1 `캠핑용 전기랜턴` | 2 `연기가 났어요` | 2 `동행인이 가져온 전기랜턴 충전 단자` | `other / observed` | `collecting_service_request` |
| GB07 | 1 `전동 높이 조절 책상` | 2 `타는 냄새가 났어요` | 2 `책상 모터` | `current / observed` | `safety_action_required` |
| GB08 | 1 `전동 높이 조절 책상` | 2 `타는 냄새가 났어요` | 2 `발 마사지기 모터` | `other / observed` | `collecting_service_request` |
| GB09 | 1 `가정용 NAS` | 2 `타는 냄새가 났어요` | 2 `NAS의 전원 어댑터` | `current / observed` | `safety_action_required` |
| GB10 | 1 `가정용 NAS` | 2 `타는 냄새가 났어요` | 2 `탁상시계의 전원 어댑터` | `other / observed` | `collecting_service_request` |
| GB11 | 2 `탁상용 공기살균기` | 1 `연기가 났습니다` | 1 `탁상용 공기살균기` | `current / observed` | `safety_action_required` |
| GB12 | 2 `탁상용 공기살균기` | 1 `연기가 났습니다` | 1 `충전식 독서등` | `other / observed` | `collecting_service_request` |
| GB13 | 1 `전자피아노` | 2 `탄 냄새가 퍼졌는데` | 공란 | `unknown / observed` | `confirming_safety_status` |
| GB14 | 1 `블루투스 마이크` | 2 `연기가 보였는데` | 공란 | `unknown / observed` | `confirming_safety_status` |
| GB15 | 1 `자동 급식기` | 2 `열이 느껴지는데` | 공란 | `unknown / uncertain` | `confirming_safety_status` |
| GB16 | 1 `디지털 액자` | 2 `연기가 난 것 같은데` | 공란 | `unknown / uncertain` | `confirming_safety_status` |
| GB17 | 1 `휴대용 라디오` | 2 `타는 냄새가 나서` | 공란 | `unknown / observed` | `confirming_safety_status` |
| GB18 | 1 `전동 연필깎이` | 2 `작은 불꽃을 봤다고 했는데` | 공란 | `unknown / uncertain` | `confirming_safety_status` |
| GB19 | 1 `전자 체중계` | 2 `배터리가 과열될 때` | 공란 | `other / nonoccurring` | `collecting_service_request` |
| GB20 | 1 `무선 이어버드` | 2 `충전 케이스가 뜨거워질 경우` | 2 `충전 케이스` | `current / nonoccurring` | `collecting_service_request` |
| GB21 | 공란 | 공란 | 공란 | `none / none` | `collecting_service_request` |
| GB22 | 1 `전기면도기` | 2 `배터리 폭발 영상` | 공란 | `other / nonoccurring` | `collecting_service_request` |
| GB23 | 1 `무선 게임 컨트롤러` | 2 `과열 시` | 공란 | `other / nonoccurring` | `collecting_service_request` |
| GB24 | 공란 | 공란 | 공란 | `none / none` | `collecting_service_request` |

## 판단이 필요한 경계

- **GB09:** `NAS의 전원 어댑터`를 접수 NAS에 소속된 부품으로 해석해 `current`를 제안했다. 별도 공유 어댑터라면 관계가 달라진다.
- **GB15:** ‘주변에서 열이 느껴진다’는 관찰이지만 실제 위험 발생 여부는 불확실해 `uncertain`을 제안했다. `observed`로 볼 수도 있으므로 판단이 필요하다. 어느 쪽이어도 출처는 `unknown`, 경로는 안전 확인이다.
- **GB18:** 타인의 전언이므로 기존 RE10 기준으로 발생 상태 `uncertain`을 제안했다. 출처의 물리적 주체도 미확정이다.
- **GB19·GB22·GB23:** 자료·영상·판매 안내의 조건부 위험은 물리적 주체 추출의 성공으로 세지 않는다. 관계 `other`, 발생 `nonoccurring`, 주체 공란을 제안했다.
- **GB21·GB24:** 경고등의 의미·예방 점검을 묻지만 특정 위험 사건을 진술하지 않아 `none/none`과 두 번호 공란을 제안했다. 이 두 사례를 `current/nonoccurring`으로 보려면 위험 사건으로 간주할 원문 구절을 먼저 지정해야 한다.
- **GB13–GB18:** 주체 공란은 **평가 정답**일 뿐 모델에 주는 오라클 입력이 아니다. 이 6건을 gold-owner 링크 실험에 섞지 않고 원문 기반 추출·관계 평가에서 다룬다.

이 표의 문장 번호와 인용 구절은 기계적으로 원문에 앵커되는지 확인한 뒤 데이터 파일로 고정한다. 모델 입력에는 이 정답 표를 넣지 않는다. 모든 필드·공란·허용값은 사용자 검수 후에만 평가 정답이 된다.
