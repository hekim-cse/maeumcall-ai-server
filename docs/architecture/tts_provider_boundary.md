# Qwen3-TTS 공급자와 음색 선정 경계

## 상태

Accepted · 2026-08-18

## 결정

마음콜의 한국어 음성 합성 엔진으로 `Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice`를 사용한다. 모델은 `85e237c12c027371202489a0ec509ded67b5e4b5` 리비전으로 고정한다. 모델과 공식 `qwen-tts` 패키지는 Apache-2.0이다.

서버는 TTS를 다음 경계로 분리한다.

1. `/chat`은 검증된 텍스트와 LangGraph 상태만 반환한다.
2. `/tts/voices`는 사용할 수 있는 9개 고정 음색과 모델 리비전을 공개한다.
3. 인증된 `/tts/synthesize`는 허용된 음색과 한국어 텍스트만 받아 24kHz·16비트·모노 WAV를 반환한다.
4. `TTSProvider`는 모델별 로딩과 합성을 감추고, API 계약은 Qwen 내부 타입에 의존하지 않는다.
5. 기능 비활성화, 장치 부재, 리비전 누락, 합성 실패를 각각 타입이 있는 오류로 반환한다.

## 선택 근거

| 후보 | 판단 |
|---|---|
| Qwen3-TTS 0.6B CustomVoice | Apache-2.0, 한국어 포함 10개 언어, 9개 고정 음색, Python 3.11과 Apple MPS 실합성 검증 |
| MeloTTS Korean | MIT와 CPU 실시간 실행은 장점이지만 공개 한국어 화자가 하나라 비교·배역 구성이 제한됨 |
| KaniTTS | 모델 카드의 라이선스 메타데이터와 본문 표기가 일치하지 않아 포트폴리오·배포 기준으로 채택하지 않음 |
| CosyVoice 3 | Apache-2.0과 다국어 품질은 적합하지만 약 9.7GB 배포 파일은 현재 로컬·모바일 연동 검증 범위에 비해 큼 |
| 비공식 브라우저 TTS 호출 | 외부 서비스 약관·인증·가용성을 프로젝트가 통제할 수 없어 제외 |

공식 자료: [Qwen3-TTS GitHub](https://github.com/QwenLM/Qwen3-TTS), [0.6B CustomVoice 모델 카드](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-0.6B-CustomVoice)

## 런타임 계약

- Python: 3.11
- 패키지: `qwen-tts==0.1.1`, `torch==2.8.0`, `torchaudio==2.8.0`
- 시스템 도구: SoX 14.4.2 이상
- 모델 파일: 약 2.5GB, 런타임에는 고정 리비전만 허용
- 로컬 검증 장치: Apple MPS + bfloat16
- attention 구현: Apple MPS에서 지원되는 PyTorch eager 경로
- 기본 운영값: TTS 비활성화, 로컬 파일만 사용
- CPU 사용 시 dtype은 float32만 허용
- 한 프로세스의 공급자는 합성을 직렬화하고 동시 요청은 `429 TTS_BUSY`로 거부해 모델 객체와 메모리를 보호함

Qwen 패키지가 데모용 Gradio도 의존하므로 `requirements-tts.txt`에서 FastAPI와 호환되는 버전을 함께 고정했다. 기본 서버 설치에는 이 무거운 선택 의존성을 넣지 않는다.

## 음색 선정 절차

`scripts.generate_tts_auditions`는 9개 음색에 동일한 한국어 문장과 고정 난수 시드를 입력한다. 출력 디렉터리가 비어 있지 않으면 덮어쓰지 않고 중단하며, manifest에 모델·리비전·장치·dtype·난수 시드·문장·샘플레이트·파일 SHA-256을 기록한다.

```bash
python -m pip install -r requirements-tts.txt
python -m scripts.generate_tts_auditions \
  --output-dir /absolute/path/to/voice-auditions \
  --device mps \
  --dtype bfloat16
```

시나리오별 음색 매핑은 청취 평가 이후 별도 변경으로 확정한다. 0.6B 모델에는 공식 기능 표에서 보장되지 않은 말투 지시나 감정 프롬프트를 넣지 않는다.

### 가족 통화 상대 계약

가족 시나리오는 엄마와 아빠를 하나의 음색으로 자동 통합하지 않는다. 모바일 요청이 허용된 `personaId`를 명시하고 서버가 그 값을 검증해야 한다. 대화 문장, 사용자 이름, 시나리오 제목으로 통화 상대를 추정하지 않는다. `castVersion: 2` 선정에서는 `father`와 `mother`를 독립 배역으로 관리한다.

고정 9개 음색에 적합한 엄마 후보가 없을 때는 `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`을 고정 리비전으로 실행해 오프라인 후보만 만든다. VoiceDesign은 매 통화의 운영 합성에 직접 사용하지 않는다. 사용자가 한 후보를 승인하면 공식 Voice Design → Voice Clone 절차로 음색 기준을 고정하고, 기준 파일의 해시·모델 리비전·생성 지시문을 배역 계약에 기록한다.

청취 피드백으로 음높이나 연령감을 조정할 때는 완성 WAV에 단순 피치 시프트를 적용하지 않는다. 기본 음높이와 함께 공명, 억양 폭, 발화 속도를 VoiceDesign 지시문에서 다시 설계하고 원본 후보 ID를 계보로 기록한다. 그래야 인위적인 음질 변화 없이 어떤 결정에서 파생된 음색인지 재현할 수 있다.

## 운영 주의사항

- 합성 API는 GPU·메모리 남용을 막기 위해 Firebase 인증을 요구한다.
- 합성 음성은 사용자 발화를 포함할 수 있으므로 응답 캐시를 금지한다.
- 모바일은 텍스트 응답을 먼저 보존하고 TTS 실패를 대화 상태 실패로 취급하지 않는다.
- 모델을 여러 API worker에 각각 적재하면 메모리가 worker 수만큼 증가한다. 로컬 MPS 운영은 단일 worker를 사용한다.
- 생성 WAV는 비교 산출물이므로 Git에 커밋하지 않는다. 선택 결과와 생성 명령만 문서와 코드로 관리한다.
- 0.6B 음색의 한국어 품질은 각 음색의 원어와 다를 수 있다. 설명만으로 역할을 정하지 않고 실제 청취 결과를 사용한다.
- VoiceDesign 자연어 지시문은 원하는 속성을 표현할 뿐 결과를 보장하지 않는다. 나이·성별·감정 적합성은 생성 음성을 직접 듣고 승인한다.

## 공급자 재평가 경계

Qwen3-TTS는 현재 기본 공급자로 유지하되 공급자 교체 가능성을 코드 밖의 인상비교로 판단하지 않는다. `experiments/tts_model_eval`에서 동일한 한국어 문장으로 다음 후보를 재현 가능하게 비교한다.

- NVIDIA MagpieTTS v2607: 5개 고정 음성을 NVIDIA 공식 Space에서 평가한다. Space와 모델의 현재 SHA가 기록된 값과 다르면 생성 스크립트가 중단된다. 공개 데모 호출은 평가 전용이며 사용자 발화와 개인정보를 전송하지 않는다.
- MeloTTS Korean: 한국어 단일 음성을 CPU 경량 기준선으로 평가한다. 오래된 Transformers·Librosa 계약과 macOS MeCab 패키지 충돌이 운영 환경을 오염시키지 않도록 digest가 고정된 Python 3.11 Linux 컨테이너에서만 실행한다.
- Chatterbox Multilingual V3: 참조 음성 사용 동의·보관·삭제 정책이 정해진 뒤 음성 복제 후보로 평가한다.

청취 평가가 끝나기 전에는 공급자나 시나리오별 음색을 바꾸지 않는다. 모델 공개 지표는 평가 단위와 데이터셋이 다르므로 직접 순위를 매기는 근거로 사용하지 않는다.
