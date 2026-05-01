# llm/prompt_builder.py
from __future__ import annotations
from typing import List, Dict, Any, Optional, Set
import re, configparser
from collections import Counter, deque

from schemas.chat_models import ChatRequest
from services.prompt_registry import get_prompt_path, category_dir_path
from llm.system_prompts import build_system_prompt

# ─────────────────────────────────────────
# 공통 가드레일(상수)
# ─────────────────────────────────────────
CLOSING_TRIGGERS = [
    "네 감사합니다","감사합니다","고맙습니다","넵","네 수고하셨습니다","수고하세요",
    "그럼 이만","다음에 뵙겠습니다","들어가세요","연락드릴게요","여기까지","끝","종료",
    "끊어","끊을게","끊겠습니다","끊는다"
]

GUARDRAILS = f"""
[대화 규칙 - 공통]
- 너는 **상대역**만 연기한다. AI/상담사/내레이터 같은 메타 발화 금지.
- 응답은 **1~2문장**. 불필요한 군더더기/이모지 금지.
- **과한 공감 금지**: 형식적 공감어 남발하지 말 것.
- **반복 질문 금지**: 이미 물은 질문/주제를 다시 묻지 말 것.
- 한 번에 **하나만**: 질문 최대 1개 또는 제안 1개.
- 질문은 **필수 아님**. 질문 없이 진술/피드백/제안으로 끝나도 됨.
- 마무리 신호({", ".join(CLOSING_TRIGGERS)}) 감지 시 **질문 없이 짧게 마무리**.
- **역할 고정**: 너는 시나리오의 상대역(예: 교수님)이다. 
  **'교수님께 문의하세요/담당자에게 요청하세요'처럼 제3자에게 떠넘기는 표현 금지.** 
  항상 **본인이 판단/지시/승인/거절**한다.
- **결정 미루기 금지**: 사용자가 연장/승인 등 **결정형 요청**을 하면,
  정보가 충분하면 즉시 **승인/거절/조건부 승인** 중 하나로 **결론**을 내린다.
  부족하면 **단 하나의 핵심 추가 정보**만 물은 뒤, 다음 턴에 결론을 낸다.
- **통화 목적 추측 금지**: (이하 동일)
- 마무리 멘트는 **고정 문구 금지**. 사용자의 마지막 말투/뉘앙스(감사/작별/사과/확인)에 맞춰 **짧은 한 문장**으로 다양하게 응답한다.
  예) "넵 감사합니다" → "네, 수고하세요." / "네, 감사합니다."
      "그럼 끊겠습니다" → "네, 들어가세요." / "네, 여기서 마무리하죠."
      "죄송합니다" → "네, 다음엔 일정만 미리 알려주세요."
...
""".strip()

# ─────────────────────────────────────────
# 유틸: 질문/주제 추출
# ─────────────────────────────────────────
_QUESTION_RE = re.compile(r"(.+?\?)")

def _normalize_line(s: str) -> str:
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s

def _extract_questions(turns: List[Dict[str, str]]) -> Set[str]:
    asked: Set[str] = set()
    for t in turns or []:
        if (t.get("role") or "").lower() in {"assistant", "system"}:
            text = t.get("text") or t.get("content") or ""
            for m in _QUESTION_RE.findall(text):
                asked.add(_normalize_line(m))
    return asked

_TOPIC_GROUPS = {
    "근황": ["오늘", "하루", "어땠", "뭐 했", "지내", "요즘"],
    "식사": ["밥", "식사", "저녁", "점심", "아침", "먹었", "배달", "요리", "메뉴"],
    "수면": ["잠", "자", "피곤", "밤샘", "새벽", "졸"],
    "날씨": ["날씨", "춥", "덥", "쌀쌀", "비", "눈"],
    "공부": ["과제", "공부", "시험", "레포트"],
    "건강": ["건강", "컨디션", "감기", "운동", "아프"],
    "돈": ["돈", "용돈", "지출", "비용", "값", "가격"],
    "가족": ["엄마", "아빠", "가족", "동생", "집"],
}

def _guess_topic(text: str) -> Optional[str]:
    txt = (text or "").strip()
    if not txt:
        return None
    for topic, kws in _TOPIC_GROUPS.items():
        if any(kw in txt for kw in kws):
            return topic
    return None

def _extract_topics(turns: List[Dict[str, str]]) -> Set[str]:
    seen: Set[str] = set()
    for t in turns or []:
        txt = t.get("text") or t.get("content") or ""
        topic = _guess_topic(txt)
        if topic:
            seen.add(topic)
    return seen

def _last_assistant_question(turns: List[Dict[str, str]]) -> Dict[str, str]:
    for t in reversed(turns or []):
        if (t.get("role") or "").lower() == "assistant":
            txt = t.get("text") or t.get("content") or ""
            if "?" in txt:
                return {"text": txt, "topic": _guess_topic(txt) or ""}
    return {}

def _recent_topic_counts(turns: List[Dict[str, str]], window: int = 3) -> Counter:
    q = deque([], maxlen=window)
    for t in reversed(turns or []):
        txt = t.get("text") or t.get("content") or ""
        if not txt:
            continue
        q.appendleft(txt)
        if len(q) == window:
            break
    c = Counter()
    for txt in q:
        topic = _guess_topic(txt)
        if topic:
            c[topic] += 1
    return c

def _recent_topics_list(turns: List[Dict[str, str]], window: int = 3) -> List[str]:
    q = deque([], maxlen=window)
    for t in reversed(turns or []):
        txt = t.get("text") or t.get("content") or ""
        if not txt:
            continue
        q.appendleft(txt)
        if len(q) == window:
            break
    out: List[str] = []
    for txt in q:
        tp = _guess_topic(txt)
        if tp:
            out.append(tp)
    return out

# ─────────────────────────────────────────
# INI 로더 + 머지
# ─────────────────────────────────────────
def _load_ini_as_prompt(path) -> Dict[str, Any]:
    cfg = configparser.ConfigParser(interpolation=None)
    if not path or not path.exists():
        return {}
    cfg.read(path, encoding="utf-8")

    def _lines(section: str) -> List[str]:
        if section in cfg and "lines" in cfg[section]:
            raw = cfg[section]["lines"].strip().splitlines()
            return [l.strip(" \t-•") for l in raw if l.strip()]
        return []

    meta = cfg["meta"] if "meta" in cfg else {}
    return {
        "gpt_role":     meta.get("gpt_role", ""),
        "user_role":    meta.get("user_role", ""),
        "address_user": meta.get("address_user", ""),
        "tone":         meta.get("tone", ""),
        "prefer":       _lines("prefer"),
        "avoid":        _lines("avoid"),
        "openers":      _lines("openers"),
        "closers":      _lines("closers"),
        "topic_hints":  _lines("topic_hints"),
    }

def _merge_prompt(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, list):
            out[k] = list(dict.fromkeys([*(out.get(k) or []), *v]))
        else:
            out[k] = v or out.get(k, "")
    return out

def load_scenario_prompt(category: str, title: str) -> Dict[str, Any]:
    scenario_path = get_prompt_path(category, title)
    cat_dir = category_dir_path(category)
    default_path = cat_dir / "_default.ini"
    default_cfg = _load_ini_as_prompt(default_path)
    scenario_cfg = _load_ini_as_prompt(scenario_path)
    if not default_cfg and not scenario_cfg:
        return {}
    return _merge_prompt(default_cfg, scenario_cfg)

# ─────────────────────────────────────────
# 최종 프롬프트 생성
# ─────────────────────────────────────────
def generate_prompts(req: ChatRequest) -> tuple[str, str]:
    """
    (system_prompt, user_prompt)
    - system: 역할/캐릭터/톤/첫 멘트 정책(닉네임 포함)
    - user  : 가드레일·반복방지·피벗 규칙 + 상황/turns
    """
    system_prompt = build_system_prompt(
        category=getattr(req, "category", None),
        nickname=getattr(req, "nickname", None),
    )
    user_prompt = _build_user_prompt(req)
    return system_prompt, user_prompt

def _build_user_prompt(req: ChatRequest) -> str:
    sc = load_scenario_prompt(req.category, req.title)

    # turns/history 통합
    turns: List[Dict[str, str]] = getattr(req, "turns", None) or getattr(req, "history", None) or []

    # 요약 정보 생성
    asked_q = sorted(_extract_questions(turns))[:12]
    asked_block = "\n".join(f"- {q}" for q in asked_q) if asked_q else "- (없음)"

    seen_topic = sorted(_extract_topics(turns))[:12]
    topic_block = ", ".join(seen_topic) if seen_topic else "(없음)"

    last_q = _last_assistant_question(turns)
    last_q_topic = last_q.get("topic", "")

    PIVOT_WINDOW = 3
    recent_counts = _recent_topic_counts(turns, window=PIVOT_WINDOW)
    recent_topics_list = _recent_topics_list(turns, window=PIVOT_WINDOW)
    recent_block = ", ".join(f"{k}×{v}" for k, v in recent_counts.items()) or "(없음)"
    recent_seq   = " → ".join(recent_topics_list) or "(없음)"

    user_last_topic = _guess_topic(getattr(req, "userMessage", "") or "") or ""

    prefer  = ", ".join(sc.get("prefer", [])) or "맥락에 맞는 자연스러운 연결어"
    avoid   = ", ".join(sc.get("avoid",  [])) or "과도한 형식체/반말 혼용/이모지 남발"
    address = sc.get("address_user") or "자연스럽게, 과하지 않게"

    topic_hints: List[str] = sc.get("topic_hints", []) or []
    hint_block = "\n".join(f"- {h}" for h in topic_hints) if topic_hints else "- (상황에 맞게)"

    used_topics = set(seen_topic)
    if user_last_topic:
        used_topics.add(user_last_topic)
    pivot_targets = [t for t in (topic_hints or ["밥","잠","날씨","루틴","돈","가족"]) if t not in used_topics]
    pivot_str = ", ".join(pivot_targets) if pivot_targets else "아직 안 다룬 일상 토픽"

    no_repeat_rule = f"""
    [질문/재질문 제약]
    - **같은 주제 캐묻기 금지**. 이미 다룬 주제는 변형 포함 **재질문 금지**: {topic_block}.
    - 직전 어시스턴트 질문 주제: {last_q_topic or "(없음)"} / 방금 사용자 답변 주제: {user_last_topic or "(없음)"}.
    - 두 주제가 같다면(= 방금 답을 들었으면) **이번 턴은 질문 절대 금지**. **진술/피드백/짧은 제안**으로 마무리하거나 **다른 주제로 바로 전환**.
    - 전환 시 추천 피벗: {pivot_str}.
    """.strip()

    selector_rule = """
    [선택 규칙(내부 의도만)]
    - 공감(A) / 피드백(F) / 제안(S) 중 **의도 하나만 선택**.
    - 출력에는 (A/F/S) 같은 표기는 **절대 넣지 말 것**.
    - 1문장으로 충분하면 1문장으로 끝내라.
    """.strip()

    anti_pattern = f"""
    [반복/상투어 금지]
    - 예문 베끼기·문장구조 복붙 금지(표현 변주 필수).
    - “요즘 어때/괜찮아/밥 먹었어?” 류 상투어 금지.
    - 이미 다룬 주제({topic_block}) 재등장 금지.
    - ***같은 질문을 형식만 바꿔 되묻지 말 것***.
    """.strip()

    pivot_hardline = f"""
    [주제 피벗 규칙]
    - 최근 {PIVOT_WINDOW}턴 시퀀스: {recent_seq}
    - 최근 {PIVOT_WINDOW}턴 카운트: {recent_block}
    - 위 주제는 이번 턴 **재질문/재권유 금지**.
    - '밥/날씨/건강/바쁨' 관련 멘트는 반복 1회만 허용.
    - 걱정/권유 1회 후에는 **한 줄 요약 + 다른 주제 전환**.
    """.strip()

    # 🔒 회사/교수 전용 금지/요구 규칙
    extra_rules = ""
    if getattr(req, "category", "") == "회사" and "보고서 제출" in getattr(req, "title", ""):
        extra_rules = """
        [특수 하드 룰: 회사/보고서 제출]
        - **절대 수긍 금지**: '좋습니다/괜찮습니다/알겠습니다' 등 금지.
        - 사용자의 말 뒤에는 **반박/지적 1개 + 구체값 요청 1개** 조합으로 끝낸다.
        - 다음 중 최소 1개를 포함:
          • "지난주에 이미 요청드렸는데 왜 오늘 말씀하십니까?"
          • "그 사유로는 일정 지연을 정당화하기 어렵습니다."
          • "지금 막힌 블로커가 정확히 뭡니까? 데이터? 결재선? 리소스?"
          • "ETA를 정확히 몇 시로 확정합니까?"
          • "미제출 시 결재 일정 전체가 밀립니다. 책임 계획 있습니까?"
        - **사적 대화 금지**, 간결 단문 유지.
        """.strip()

    return f"""
{GUARDRAILS}

{no_repeat_rule}
{pivot_hardline}
{selector_rule}
{anti_pattern}
{extra_rules}

[역할]
- 너(모델): {sc.get('gpt_role','상대역')}
- 사용자: {sc.get('user_role','사용자')}
- 호칭: {address}

[상황]
- 카테고리: {getattr(req,'category','')}
- 제목: {getattr(req,'title','')}
- 설명: {getattr(req,'description','')}

[사용자 최근 발화]
{getattr(req,'userMessage','')}

[대화 히스토리 요약 정보]
- 이미 물어본 질문(반복 금지):
{asked_block}
- 이미 다룬 주제 키워드(재질문 금지): {topic_block}

[카테고리 권장 전환 주제]
{hint_block}

[톤/어휘]
- 톤: {sc.get('tone','자연스러운 한국어 구어체')}
- 권장 표현: {prefer}
- 금지 표현: {avoid}

[출력 형식]
- 1~2문장. 생활감 요소는 1개만 가볍게.
- 문장 끝은 너무 매끈하게 닫지 말고, 자연스러운 여운 허용.
""".strip()
