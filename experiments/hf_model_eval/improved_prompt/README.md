cat > experiments/hf_model_eval/improved_prompt/README.md <<'EOF'
# Hugging Face Improved Prompt Evaluation

## 목적

1차 Baseline Prompt에서 상위 후보로 남은 모델을 대상으로, 실제 서비스 적용 가능성을 확인하기 위해 역할 분리 프롬프트로 재평가한다.

## 2차 평가 대상

1. EXAONE-4.0-1.2B
2. Kanana 1.5 2.1B Instruct
3. HyperCLOVA X SEED 1.5B
4. Gemma-ko-2B

## 확인 항목

- recommended_replies가 사용자/환자 입장으로 생성되는지
- JSON 하나만 출력되는지
- assistant 블록이나 프롬프트 반복 출력이 사라지는지
- ai_message가 예약 가능 여부를 임의로 확정하지 않는지
- 응답 시간이 1차 대비 유지되는지
EOF