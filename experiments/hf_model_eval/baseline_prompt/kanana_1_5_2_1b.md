```markdown
### Kanana 1.5 2.1B Instruct

```text
MODEL_NAME = "kakaocorp/kanana-1.5-2.1b-instruct-2505"

{
  "ai_message": "네, 내일 오후에도 진료 예약이 가능합니다. 원하시는 시간대를 알려주시면 더 정확히 안내해드릴 수 있습니다.",
  "recommended_replies": [
    "오후 3시로 예약해주시겠어요?",
    "다른 시간대도 괜찮으신가요?",
    "예약을 원하시는 시간을 말씀해주시면 바로 도와드리겠습니다."
  ],
  "conversation_state": "asking_time",
  "should_end_call": false
}

Latency

* 4.67s

판단

* JSON 안정성 좋음
* 응답 속도 좋음
* 한국어 전화 응대 말투 자연스러움
* 추천 답변 일부는 사용자 입장으로 더 명확히 조정 필요
* Keep