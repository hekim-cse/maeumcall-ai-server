# 한국어 TTS 공급자 비교

## 목적

운영 TTS 공급자를 이름이나 공개 지표만으로 교체하지 않고, 동일한 한국어 문장과 고정된 모델 리비전으로 직접 청취한다. 생성 WAV는 Git에 올리지 않으며, 모델·실행 경로·문장·생성 설정·파일 SHA-256을 manifest로 남겨 비교 계약만 버전 관리한다.

기본 평가 문장은 다음과 같다.

> 안녕하세요. 마음콜 통화 연습을 시작하겠습니다. 천천히 말씀해 주세요.

## 비교 경계

| 공급자 | 실행 경계 | 비교 목적 |
|---|---|---|
| Qwen3-TTS 0.6B CustomVoice | Apple MPS 로컬 실행 | 현재 운영 후보 9개 음색의 기준선 |
| NVIDIA MagpieTTS v2607 | NVIDIA 공식 Hugging Face Space | 한국어를 지원하는 5개 고정 음성 비교 |
| MeloTTS Korean | 격리된 Python 3.11 CPU 환경 | 단일 한국어 경량 모델의 속도·품질 기준선 |

Magpie 공식 Space 호출은 평가 전용이다. 입력 문장이 외부 NVIDIA Hugging Face Space로 전송되므로 실제 사용자 발화나 개인정보를 사용하지 않는다. 운영 API 공급자로 채택하려면 공개 데모가 아닌 고정 체크포인트 또는 정식 운영 엔드포인트를 별도로 구성해야 한다.

로컬에서 실행하는 Qwen과 MeloTTS는 Python·NumPy·PyTorch 난수 시드를 42로 고정하고 manifest에 기록한다. Magpie 공식 데모 API는 시드 입력을 제공하지 않으므로 모델·Space 리비전과 생성 파일 해시는 기록하되, 동일 WAV 바이트의 재생성을 보장하는 후보로 취급하지 않는다.

MeloTTS는 `transformers==4.27.4`와 `librosa==0.9.1`을 요구한다. 현재 서버와 Qwen TTS의 의존성을 낮추지 않도록 반드시 별도 Linux 컨테이너에서만 실행한다. Librosa 0.9.1이 사용하는 `pkg_resources`를 제공하기 위해 평가 환경의 `setuptools`도 80.9.0으로 고정한다. 직접 관리하는 요구사항과 실제 합성에 성공한 전체 전이 의존성 잠금 파일을 분리해, 후보 갱신 의도와 재현 가능한 설치 결과를 함께 관리한다. 한국어 텍스트 처리에 내부적으로 사용하는 `kykim/bert-kor-base`는 현재 Hub SHA를 검증한 뒤 그 SHA 자체로 내려받고 manifest에 함께 기록한다.

## 생성 명령

```bash
python -m scripts.generate_tts_auditions \
  --output-dir /absolute/path/to/qwen \
  --device mps \
  --dtype bfloat16

python -m scripts.generate_magpie_tts_auditions \
  --output-dir /absolute/path/to/magpie \
  --allow-network

docker build \
  --file experiments/tts_model_eval/melotts.Dockerfile \
  --tag maeum-call-melotts-eval:2026-08-18 \
  .
docker run --rm \
  --user "$(id -u):$(id -g)" \
  --env HOME=/tmp/melotts-home \
  --env HF_HOME=/tmp/melotts-home/huggingface \
  --volume "$PWD:/workspace" \
  maeum-call-melotts-eval:2026-08-18 \
  --output-dir /workspace/artifacts/tts-auditions/melotts-korean \
  --device cpu \
  --allow-network
```

UniDic 다운로드는 약 526MB이며, 한국어 합성에서도 MeloTTS가 일본어 모듈을 함께 초기화하기 때문에 필요하다. 한국어 G2P가 실행 중에 패키지를 설치하지 않도록 `python-mecab-ko`와 사전 버전도 평가 요구사항에 선제 고정했다. macOS의 대소문자 비구분 파일시스템에서는 한국어용 `mecab`과 일본어용 `MeCab` 패키지 경로가 충돌하므로, MeloTTS 평가는 digest가 고정된 Python 3.11 Linux 컨테이너에서 실행한다. 컨테이너는 `--rm`으로 실행해 종료 후 남겨두지 않는다. 이 추가 설치 비용과 언어별 모듈이 분리되지 않은 초기화 구조도 운영성 평가에 포함한다.

Dockerfile 전용 ignore 규칙은 빌드 컨텍스트에 평가 요구사항 파일만 포함한다. 소스 코드·환경 파일·로컬 산출물이 이미지 빌더로 전달되지 않도록 경계를 좁힌다.

## 청취 평가 기준

1. 대본 충실도: 누락·반복·원문 밖 발화가 없는가.
2. 한국어 발음: 받침, 조사, 외래어, 숫자 표현이 자연스러운가.
3. 전화 상황 적합성: 통화 음질에서도 의미와 감정이 분명한가.
4. 역할 다양성: 여러 시나리오에 구분 가능한 음색을 배정할 수 있는가.
5. 운영성: 모델 크기, 생성 시간, 실행 장비, 라이선스를 지속해서 관리할 수 있는가.

공식 지표의 CER와 WER는 평가 데이터와 단위가 달라 공급자 사이의 절대 순위로 사용하지 않는다. 최종 음색 배정은 동일 문장 청취 결과와 실제 시나리오 문장 평가를 모두 통과한 뒤 확정한다.

## 시나리오 배역 청취

사용자가 직접 청취해 선택한 `castVersion: 1` 배역은 다음과 같다.

| 카테고리 | 공급자 | 음색 | 시나리오 수 |
|---|---|---|---:|
| 예약 | NVIDIA Magpie | Sofia | 4 |
| 교수님 | Qwen3-TTS | Eric | 3 |
| 배달 | NVIDIA Magpie | Jason | 3 |
| 시청 | NVIDIA Magpie | Sofia | 3 |
| 고객센터 | NVIDIA Magpie | Sofia | 3 |
| 가족 | NVIDIA Magpie | Aria | 3 |
| 친구 | Qwen3-TTS | Serena | 5 |
| 연인 | Qwen3-TTS | Uncle Fu | 4 |
| 회사 | NVIDIA Magpie | Leo | 4 |

`services.tts.casting`은 현재 32개 시나리오 키를 모두 명시한다. 카테고리만 보고 새 시나리오에 음색을 자동 상속하지 않으며, 중앙 LangGraph 레지스트리와 배역 키가 달라지면 테스트가 실패한다.

시나리오별 대사는 해당 상세 그래프의 첫 업무 질문 또는 등록형 역할의 대표 응답으로 작성한다. 공급자 제한이 한쪽 결과를 지우지 않도록 로컬 Qwen 12개와 공식 Space 기반 Magpie 20개를 별도 산출물로 생성한다.

```bash
python -m scripts.generate_scenario_tts_auditions \
  --output-dir artifacts/tts-scenario-auditions/cast-v1/qwen3-tts \
  --provider qwen3-tts \
  --device mps \
  --dtype bfloat16 \
  --seed 42

python -m scripts.generate_scenario_tts_auditions \
  --output-dir artifacts/tts-scenario-auditions/cast-v1/nvidia-magpie \
  --provider nvidia-magpie \
  --allow-network
```

Magpie 생성은 Hugging Face ZeroGPU 사용 한도의 적용을 받는다. 한도가 소진되면 다른 공개 Space나 다른 음색으로 우회하지 않고 공식 한도 복구 후 다시 실행한다.
