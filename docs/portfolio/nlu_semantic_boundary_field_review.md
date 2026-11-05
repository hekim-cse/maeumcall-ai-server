# NLU 새 의미 대조 사례 12건: 나머지 필드 검토 초안

[값이 있는 8건](nlu_semantic_boundary_review.md)과
[공란 대조 4건](nlu_semantic_negative_review.md)의 문장·행동·초점 필드 방향은
2026-11-05에 사용자가 탐색용으로 채택했다. 이 표는 **그 외 필드를 포함한 전체 출력값의
AI 초안**이다. 공란도 명시한다. 사용자가 SB02·SB04·SB06·SB08의 초점 값을
지지한다고 수정했고 다른 필드 수정 요청은 없었다. 아직 모델에 입력하지 않았다.
정규화 문자열은 여러 표현이 가능하므로 특히 문제 상세와 이용 시간을 확인한다.

| ID | 비공란 필드 초안 | 공란 초안·판단 |
| --- | --- | --- |
| SB01 | `issue_type=wrong_item`, `issue_detail=도시락 대신 다른 음식이 옴`, `resolution_preference=refund` | 주문번호·증빙 없음 |
| SB02 | `issue_type=wrong_item`, `issue_detail=도시락 대신 다른 음식이 옴`, `resolution_preference=refund` | 주문번호·증빙 공란. 사용자는 환불 조건 문의에도 환불 희망이 드러난다고 판단 |
| SB03 | `issue_type=damaged_or_quality`, `issue_detail=케이크 상자가 젖어 안쪽이 망가짐`, `resolution_preference=redelivery` | 주문번호·증빙 없음. 질문형이지만 같은 물건을 다시 받으려는 요청으로 제안 |
| SB04 | `issue_type=damaged_or_quality`, `issue_detail=케이크 상자가 젖어 안쪽이 망가짐`, `resolution_preference=redelivery` | 주문번호·증빙 공란. 사용자는 재배달 기준 문의에도 재배달 희망이 드러난다고 판단 |
| SB05 | `document_type=register_copy`, `issuance_channel=government24`, `inquiry_topic=delivery` | 신청 관계 공란. 인쇄 절차를 출력·수령 방법 문의로 분류 |
| SB06 | `document_type=register_copy`, `issuance_channel=government24`, `inquiry_topic=delivery` | 신청 관계 공란. 사용자는 이 문맥의 온라인 발급을 정부24 경로로 판단 |
| SB07 | `date=다음 주 화요일`, `start_time=오전 10시`, `duration=두 시간` | 인원·예약자 이름·대체 시간 선택 공란 |
| SB08 | `date=매주 화요일`, `start_time=오전 10시`, `duration=두 시간` | 인원·예약자 이름·대체 시간 선택 공란. 사용자는 반복 예약 의사와 날짜가 드러난다고 판단 |
| SB09 | `issue_type=wrong_item`, `issue_detail=도시락 대신 다른 음식이 옴` | 주문번호·증빙·희망 처리 공란. 환불 미요청을 명시 |
| SB10 | `issue_type=damaged_or_quality`, `issue_detail=케이크 상자가 젖어 안쪽이 망가짐` | 주문번호·증빙·희망 처리 공란. 재배달 미요청을 명시 |
| SB11 | `document_type=register_copy` | 신청 관계·발급 경로·문의 항목 공란. 발급 방법 비교가 기존 `inquiry_topic` 코드 중 하나에 맞는지 검토 필요 |
| SB12 | `start_time=오전 10시`, `duration=두 시간` | 날짜·인원·예약자 이름·대체 시간 선택 공란 |

SB01–SB08은 사용자 수정 방향을 반영했고, SB09–SB12의 **나머지 필드**도
2026-11-05에 탐색용으로 채택받았다. SB11의 방법 비교는 이 실험에서
`inquiry_topic=null`인 AI 초안으로 취급한다. 자료의 해시와 검토 기록을
고정한 뒤 모델에 입력한다. 출처는 계속
`ai_assisted_unreviewed`이며 공식 test로 쓰지 않는다.
