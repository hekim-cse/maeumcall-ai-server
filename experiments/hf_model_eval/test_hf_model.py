import time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

# 3차 테스트 첫 번째 모델: EXAONE
# 다음 모델 테스트 시 MODEL_NAME만 변경하면 된다.
MODEL_NAME = "kakaocorp/kanana-1.5-2.1b-instruct-2505"

BENCHMARK_PROMPT = """
너는 병원 예약 전화 시뮬레이션 AI이다.

역할:
- ai_message는 병원 접수 직원이 사용자에게 말하는 문장이다.
- recommended_replies는 사용자가 병원 접수 직원에게 답할 수 있는 환자 입장의 문장이다.

상황:
사용자가 말했다: "저기... 내일 오후에 진료 예약 가능할까요?"

규칙:
- 반드시 JSON 객체 하나만 출력한다.
- markdown 코드블록을 쓰지 않는다.
- assistant, user 같은 역할 이름을 출력하지 않는다.
- 설명 문장을 붙이지 않는다.
- JSON 뒤에 추가 문장을 붙이지 않는다.
- ai_message는 병원 접수 직원 말투로 1문장만 작성한다.
- ai_message에서 예약 가능 여부를 확정하지 않는다.
- ai_message는 다음에 필요한 정보를 부드럽게 물어본다.
- recommended_replies는 사용자가 실제로 말할 수 있는 짧은 문장 3개로 작성한다.
- recommended_replies는 병원 직원 말투로 작성하지 않는다.
- should_end_call은 false로 작성한다.

출력 형식:
{
  "ai_message": "문장",
  "recommended_replies": ["문장1", "문장2", "문장3"],
  "conversation_state": "asking_department",
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
    print(f"Loading model: {MODEL_NAME}", flush=True)

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

    inputs = tokenizer(
        prompt,
        return_tensors="pt",
    ).to(model.device)

    start = time.perf_counter()

    # 3차 Strict JSON Prompt 테스트 조건
    # max_new_tokens=100: JSON 하나만 짧게 생성하도록 제한한다.
    # do_sample=False: 모델별 비교 조건을 고정한다.
    # repetition_penalty=1.15: 반복 출력을 줄인다.
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=100,
            do_sample=False,
            repetition_penalty=1.15,
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