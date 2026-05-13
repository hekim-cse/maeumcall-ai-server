import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = "naver-hyperclovax/HyperCLOVAX-SEED-Text-Instruct-1.5B"

BENCHMARK_PROMPT = """
너는 전화 공포증 완화를 위한 통화 시뮬레이션 상대이다.
현재 상황은 병원 예약 전화이다.

규칙:
- 실제 병원 접수 직원처럼 자연스럽고 공손하게 응답한다.
- 사용자를 압박하지 않는다.
- 한 번에 하나의 질문만 한다.
- 1~2문장으로 짧게 답한다.
- 반드시 JSON 형식으로만 답한다.
- 번역체 표현을 쓰지 않는다.
- 한국 병원에서 실제로 들을 수 있는 자연스러운 존댓말을 사용한다.

좋은 예시:
{
  "ai_message": "네, 확인해드리겠습니다. 원하시는 진료과가 있으실까요?",
  "recommended_replies": [
    "내과 진료를 예약하고 싶습니다.",
    "처음 방문인데 예약 가능할까요?",
    "오후 3시 이후 시간이 괜찮습니다."
  ],
  "conversation_state": "asking_department",
  "should_end_call": false
}

사용자 발화:
"저기... 내일 오후에 진료 예약 가능할까요?"

출력 형식:
{
  "ai_message": "...",
  "recommended_replies": ["...", "...", "..."],
  "conversation_state": "...",
  "should_end_call": false
}
"""


def build_prompt(tokenizer):
    messages = [
        {"role": "user", "content": BENCHMARK_PROMPT.strip()},
    ]

    if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
        return tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

    return BENCHMARK_PROMPT.strip() + "\n\n답변:"


def main():
    print(f"Loading model: {MODEL_NAME}")

    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        trust_remote_code=True,
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        dtype=torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    prompt = build_prompt(tokenizer)
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)

    start = time.perf_counter()

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=180,
            do_sample=False,
            repetition_penalty=1.0,
        )

    end = time.perf_counter()

    input_length = inputs["input_ids"].shape[-1]
    generated_tokens = outputs[0][input_length:]
    decoded = tokenizer.decode(generated_tokens, skip_special_tokens=True)

    print("\n===== GENERATED OUTPUT ONLY =====")
    print(decoded)

    print("\n===== LATENCY =====")
    print(f"{end - start:.2f}s")


if __name__ == "__main__":
    main()