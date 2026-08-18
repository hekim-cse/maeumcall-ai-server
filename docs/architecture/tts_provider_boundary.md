# TTS 배역 계약과 다중 공급자 실행 경계

## 상태

Accepted · 2026-08-18

## 결정

마음콜의 배역 버전 2는 실제 청취로 승인한 Qwen3-TTS CustomVoice, Bark Small, Qwen3-TTS Voice Clone을 역할별로 사용한다. 모델 이름만 저장하지 않고 각 Hugging Face 리비전, 배역 버전, 역할 ID와 음색 ID를 함께 고정한다.

서버는 TTS를 다음 경계로 분리한다.

1. `/chat`은 검증된 텍스트와 LangGraph 상태만 반환한다.
2. 모바일은 인증된 `/tts/scenario/synthesize`에 텍스트·시나리오 키·배역 버전·선택적 가족 역할만 보낸다.
3. 서버는 32개 시나리오 전체를 덮는 승인 배역표에서 공급자와 음색을 결정한다.
4. `/tts/synthesize`와 `/tts/voices`는 개발·청취 비교를 위한 Qwen 직접 경로로 유지한다.
5. `TTSProvider`는 모델별 로딩과 합성을 감추고 API 계약은 특정 모델 내부 타입에 의존하지 않는다.
6. 런타임은 한 번에 모델 하나만 메모리에 유지하며 공급자가 바뀌면 이전 모델을 명시적으로 해제한다.
7. 기능 비활성화, 장치 부재, 자산·리비전 누락, 승인되지 않은 배역, 합성 실패를 각각 타입이 있는 오류로 반환한다.

### 배역 버전 2

| 역할 | 시나리오 범위 | 공급자 | 음색 |
|---|---|---|---|
| 서비스 상담원 | 예약·시청·고객센터 | Qwen3-TTS | `ryan` |
| 교수님 | 교수님 | Qwen3-TTS | `eric` |
| 배달 상담원 | 배달 | Qwen3-TTS | `vivian` |
| 아빠 | 가족 + `personaId=father` | Qwen3-TTS | `aiden` |
| 엄마 | 가족 + `personaId=mother` | Qwen3-TTS Voice Clone | 승인 ICL 프롬프트 |
| 친구 | 친구 | Qwen3-TTS | `serena` |
| 연인 | 연인 | Qwen3-TTS | `uncle_fu` |
| 회사 상사 | 회사 | Bark Small | `v2/ko_speaker_5` |

배역 버전은 앱 버전과 독립적이다. 음색 변경이 필요하면 기존 의미를 조용히 바꾸지 않고 새 배역 버전을 만든다. 모바일은 원시 음색을 저장하지 않으므로 서버 배역 정책을 한곳에서 감사하고 회귀 테스트할 수 있다.

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
- 한 프로세스의 전체 TTS 런타임은 공급자를 가로질러 합성을 직렬화하고 동시 요청은 `429 TTS_BUSY`로 거부해 모델 객체와 메모리를 보호함
- `cold_start`·`warm`·`provider_switch` 상태와 모델 전환·합성·전체 시간을 분리해 측정함
- Prometheus 라벨에는 공급자·모델 상태·결과·고정 단계만 사용하고 발화 원문이나 사용자 식별값은 넣지 않음
- Bark Small: `suno/bark-small` 리비전 `1dbd7a128513b8ae4a4e2130fed57b7ac9da5bcd`
- 엄마 Voice Clone: `Qwen/Qwen3-TTS-12Hz-1.7B-Base` 리비전 `fd4b254389122332181a7c3db7f27e918eec64e3`
- 엄마 음성의 manifest와 `safetensors`는 Git 밖의 운영 자산으로 배치하고 절대 경로로 주입함

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

`castVersion: 2`의 엄마 역할은 청취 평가를 거쳐
`reference_warm_everyday_mature_age_restrained_prosody`로 확정했다. 선정 WAV의 SHA-256은
`a6ffd23a20a9858cd30b0af531b3e5e83786e53ee711797244b806f0fdeabf83`으로 고정한다. 이후 생성한
가공·변형 후보는 평가 이력일 뿐 이 결정을 자동으로 덮어쓰지 않는다. 이번 결정은 배역 음성의
선정 완료를 뜻하며, 운영 합성 연결은 공식 Voice Clone 단계와 별도 검증을 거쳐야 한다.

Voice Clone 검증은 공식 Qwen Voice Design → Voice Clone 절차에 맞춰
`Qwen/Qwen3-TTS-12Hz-1.7B-Base`의 고정 리비전
`fd4b254389122332181a7c3db7f27e918eec64e3`으로 수행한다. 화자 임베딩만 쓰는
`x-vector only` 모드는 품질 손실을 감수하는 경량 경로이므로 사용하지 않는다. 승인된 기준 WAV와
그 WAV를 생성한 정확한 문장을 함께 사용하는 ICL 프롬프트를 만들고, 안전한 `safetensors`
형식으로 저장한다. 프롬프트와 검증 WAV는 로컬 운영 자산이며 Git에는 해시와 manifest만 남긴다.

첫 복제 결과는 어절 끝 억양이 부자연스럽다는 사용자 평가로 거절했다. 당시
`non_streaming_mode=False`여서 전체 문장을 스트리밍 입력처럼 나눠 처리했다. 후속 후보는 최초
프롬프트 SHA `c01d0a8fef64247f5141f034bffd9b3079c33b9e2f6bf330e9a987a7180a9639`를 그대로 재사용하고
`non_streaming_mode=True`만 적용했으나, 단어 경계가 딱딱하게 끊긴다는 청취 평가로 거절했다.
프롬프트를 다시 추출하면 음색 조건도 달라지므로 통제 비교로 인정하지 않는다.

세 번째 후보는 같은 프롬프트·시드·전체 문장 처리 모드를 유지하고 합성 대사의 쉼표와 마침표를
모두 제거했다. 단어 사이는 부드러워졌지만 억양이 부족하다는 청취 평가로 거절했다. 네 번째
후보는 한국어 띄어쓰기를 그대로 유지하면서 두 의미 절 사이에만 쉼표 하나를 뒀다. 연결감은
유지됐지만 억양 강도가 부족하다는 청취 평가로 거절했다. 다섯 번째 후보는 도입부와 공감부 뒤에
쉼표를 하나씩 두고 문장 끝 마침표를 복원했다. 중간 마침표는 사용하지 않아 한 문장으로 이어
읽게 하면서 도입·공감·권유라는 의미 구간에만 억양 변화를 줬지만, 억양 강도를 더 높여 달라는
청취 평가로 거절했다.

Qwen Base Voice Clone에는 별도의 억양 강도 인자가 없다. 여섯 번째 후보는 문장·문장부호·음색·
ICL 프롬프트·시드·보조 화자 온도를 그대로 두고, 공식 음성 코드 생성 인자인 주 화자
`temperature`만 모델 기본값 `0.9`에서 `1.05`로 높인다. 이는 음높이 사후 가공이 아니라 같은
문장에서 생성 가능한 음성 코드의 변화 폭을 넓히는 통제 비교다.

여섯 번째 후보도 억양을 더 높이고 음절 경계의 분절감을 다시 줄여 달라는 청취 평가로 거절했다.
일곱 번째 후보는 주 화자 `temperature`를 `1.05`에서 `1.15`로 한 단계 더 높이고, 짧은 도입부
`그래` 뒤의 쉼표를 제거한다. 공감부 뒤 쉼표와 문장 끝 마침표는 유지해 핵심 억양 경계는
보존하고, 보조 화자 온도는 `0.9`로 고정해 발음 세부의 안정성을 유지한다.

일곱 번째 후보는 사용자 청취에서 최종 승인됐다. 승인 manifest는 주 화자 온도 `1.15`, 보조
화자 온도 `0.9`, 전체 문장 처리 모드, 승인된 ICL 프롬프트 SHA, 검증 문장과 WAV 해시를 함께
고정한다. 이 승인은 Voice Clone 검증 완료를 뜻한다. 모바일 재생 경로와 서버 배역 계약은
연결했으며, 운영 HTTPS 주소·실제 인증 세션·Android 실기기를 함께 사용하는 청취와 지연
검증은 별도로 수행한다.

청취 피드백으로 음높이나 연령감을 조정할 때는 완성 WAV에 단순 피치 시프트를 적용하지 않는다. 기본 음높이와 함께 공명, 억양 폭, 발화 속도를 VoiceDesign 지시문에서 다시 설계하고 원본 후보 ID를 계보로 기록한다. 그래야 인위적인 음질 변화 없이 어떤 결정에서 파생된 음색인지 재현할 수 있다.

지시문에 낮은 음높이를 적었더라도 실제 청취 결과가 높고 가늘게 들리면 해당 후보는 실패로 기록한다. 프롬프트의 의도는 검증 결과가 아니며, 모델이 지시를 따랐다고 간주하거나 이름만 보고 승인하지 않는다. 후속 후보는 실패한 음색의 해시와 사용자 평가를 보존한 상태에서 별도 시드와 더 직접적인 음향 속성으로 생성한다.

50·60대 여성의 음향 범위는 특정 화자를 복제하지 않고 AI Hub 승인 데이터의 다화자 집계로
검증한다. 집계 결과상 기존 196.9 Hz 후보는 가운데 50% 범위 안에 있고, 강제로 낮춘 162.4 Hz
후보는 그 범위 밖이면서 청취상 어색했다. 따라서 후속 설계는 음높이를 더 낮추는 대신 공명,
호흡, 속도, 억양과 생활 대화의 자연스러움을 조정한다. 데이터 선택, 개인정보 보호, 집계 방식과
용어는 [AI Hub 다화자 음향 기준 계약](tts_voice_reference_data.md)에 기록한다.

## 운영 주의사항

- 합성 API는 GPU·메모리 남용을 막기 위해 Firebase 인증을 요구한다.
- 합성 음성은 사용자 발화를 포함할 수 있으므로 응답 캐시를 금지한다.
- 모바일은 텍스트 응답을 먼저 보존하고 TTS 실패를 대화 상태 실패로 취급하지 않는다.
- 모델을 여러 API worker에 각각 적재하면 메모리가 worker 수만큼 증가한다. 로컬 MPS 운영은 단일 worker를 사용한다.
- 후보 WAV는 로컬 평가 산출물로만 보관하고 Git에 커밋하지 않는다. 모델·리비전·시드·파일 해시는 manifest와 선정 명세로 버전 관리한다. 실제 사용자 발화와 운영 합성 WAV도 Git에 커밋하지 않는다.
- 0.6B 음색의 한국어 품질은 각 음색의 원어와 다를 수 있다. 설명만으로 역할을 정하지 않고 실제 청취 결과를 사용한다.
- VoiceDesign 자연어 지시문은 원하는 속성을 표현할 뿐 결과를 보장하지 않는다. 나이·성별·감정 적합성은 생성 음성을 직접 듣고 승인한다.

## 지연 시간 관측

서버는 합성 성공·실패·동시 요청 거부 횟수를
`maeumcall_tts_synthesis_attempts_total`로 기록한다. 단계별 시간은
`maeumcall_tts_synthesis_duration_seconds` 히스토그램에 기록한다.

| 구분 | 의미 |
|---|---|
| `model_state=cold_start` | 프로세스에서 처음 공급자를 활성화한 요청 |
| `model_state=warm` | 이미 활성화된 같은 공급자를 재사용한 요청 |
| `model_state=provider_switch` | 기존 모델을 해제하고 다른 공급자로 전환한 요청 |
| `phase=transition` | 공급자 객체 전환과 이전 모델 해제 시간 |
| `phase=synthesis` | 모델 적재를 포함한 공급자 합성 호출 시간 |
| `phase=total` | 런타임 진입부터 합성 결과 반환까지의 전체 시간 |

`Server-Timing` 헤더는 같은 세 단계의 밀리초 값을 모바일에 전달한다. 모바일이 관측한 HTTP
왕복 시간에서 서버 전체 시간을 빼면 네트워크·프록시·응답 본문 전송 시간을 별도로 볼 수 있다.
두 환경 모두 시스템 날짜 변경의 영향을 받지 않는 단조 시계를 사용한다.

Q. 왜 사용자 ID나 시나리오 키를 Prometheus 라벨에 넣지 않는가?

A. 사용자 식별값은 관측 목적에 필요하지 않고 개인정보 위험을 만든다. 시나리오 키도 계속 늘어날
수 있어 시계열 수를 불필요하게 키운다. 공급자·모델 상태·결과·단계처럼 종류가 고정된 라벨만
사용하고, 시나리오별 실기기 확인은 모바일의 구조화된 디버그 추적으로 수행한다.

### 엄마 역할 Voice Clone 검증 명령

```bash
python -m scripts.build_qwen_mother_voice_clone \
  --reference-manifest artifacts/tts-role-auditions/cast-v2/\
qwen3-voice-design-family-mother-mature-age-restrained-prosody/manifest.json \
  --reuse-prompt-manifest artifacts/tts-clone-prompts/cast-v2/\
family-mother-qwen3-1.7b-base/manifest.json \
  --output-dir artifacts/tts-clone-prompts/cast-v2/\
family-mother-qwen3-1.7b-base-high-prosody-smooth-phrasing-icl \
  --device mps \
  --dtype bfloat16 \
  --temperature 1.15 \
  --subtalker-temperature 0.9 \
  --audition-text "그래 오늘도 수고 많았어, 무슨 일이 있었는지 엄마한테 천천히 말해 봐."
```

첫 실행 전에 Base 모델의 고정 리비전을 내려받아야 한다. 운영에서는 네트워크 다운로드를 허용하지
않고 `local_files_only` 원칙을 유지한다.

## 공급자 재평가 경계

Qwen3-TTS는 현재 기본 공급자로 유지하되 공급자 교체 가능성을 코드 밖의 인상비교로 판단하지 않는다. `experiments/tts_model_eval`에서 동일한 한국어 문장으로 다음 후보를 재현 가능하게 비교한다.

- NVIDIA MagpieTTS v2607: 5개 고정 음성을 NVIDIA 공식 Space에서 평가한다. Space와 모델의 현재 SHA가 기록된 값과 다르면 생성 스크립트가 중단된다. 공개 데모 호출은 평가 전용이며 사용자 발화와 개인정보를 전송하지 않는다.
- MeloTTS Korean: 한국어 단일 음성을 CPU 경량 기준선으로 평가한다. 오래된 Transformers·Librosa 계약과 macOS MeCab 패키지 충돌이 운영 환경을 오염시키지 않도록 digest가 고정된 Python 3.11 Linux 컨테이너에서만 실행한다.
- Chatterbox Multilingual V3: 참조 음성 사용 동의·보관·삭제 정책이 정해진 뒤 음성 복제 후보로 평가한다.

청취 평가가 끝나기 전에는 공급자나 시나리오별 음색을 바꾸지 않는다. 모델 공개 지표는 평가 단위와 데이터셋이 다르므로 직접 순위를 매기는 근거로 사용하지 않는다.
