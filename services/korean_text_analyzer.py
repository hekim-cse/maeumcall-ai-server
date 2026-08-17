from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import threading
from typing import Protocol, Sequence
import unicodedata


CONTENT_POS_TAGS = frozenset(
    {
        "NNG",  # 일반 명사
        "NNP",  # 고유 명사
        "NNB",  # 의존 명사
        "NR",   # 수사
        "NP",   # 대명사
        "VV",   # 동사
        "VA",   # 형용사
        "VX",   # 보조 용언
        "MM",   # 관형사
        "MAG",  # 일반 부사
        "MAJ",  # 접속 부사
        "XR",   # 어근
        "SL",   # 외국어
        "SH",   # 한자
        "SN",   # 숫자
    }
)
FILLER_POS_TAGS = frozenset({"IC"})  # 감탄사


class KoreanToken(Protocol):
    form: str
    tag: str


class KoreanTokenizer(Protocol):
    def tokenize(self, text: str, *, normalize_coda: bool) -> Sequence[KoreanToken]: ...


class KoreanTextAnalyzerError(RuntimeError):
    def __init__(
        self,
        code: str,
        public_message: str,
        *,
        status_code: int = 503,
    ) -> None:
        super().__init__(public_message)
        self.code = code
        self.public_message = public_message
        self.status_code = status_code


@dataclass(frozen=True)
class KoreanTextAnalysis:
    total_words: int
    words: Counter[str]
    fillers: Counter[str]


class KoreanTextAnalyzer:
    """Kiwi의 형태소·품사 결과를 제품의 단어 빈도 계약으로 변환한다."""

    def __init__(self, tokenizer: KoreanTokenizer | None = None) -> None:
        self._tokenizer = tokenizer
        self._initialization_lock = threading.Lock()

    def is_ready(self) -> bool:
        try:
            self._get_tokenizer()
        except KoreanTextAnalyzerError:
            return False
        return True

    def analyze(self, messages: Sequence[str]) -> KoreanTextAnalysis:
        tokenizer = self._get_tokenizer()
        words: Counter[str] = Counter()
        fillers: Counter[str] = Counter()

        try:
            for message in messages:
                normalized = unicodedata.normalize("NFKC", message).strip()
                if not normalized:
                    continue
                for token in tokenizer.tokenize(normalized, normalize_coda=True):
                    tag = token.tag.split("-", maxsplit=1)[0]
                    form = unicodedata.normalize("NFKC", token.form).casefold().strip()
                    if not form:
                        continue
                    if tag in FILLER_POS_TAGS:
                        fillers[form] += 1
                    elif tag in CONTENT_POS_TAGS:
                        words[form] += 1
        except KoreanTextAnalyzerError:
            raise
        except Exception as exc:
            raise KoreanTextAnalyzerError(
                "KOREAN_TEXT_ANALYSIS_FAILED",
                "한국어 형태소 분석을 완료하지 못했습니다.",
            ) from exc

        return KoreanTextAnalysis(
            total_words=sum(words.values()) + sum(fillers.values()),
            words=words,
            fillers=fillers,
        )

    def _get_tokenizer(self) -> KoreanTokenizer:
        if self._tokenizer is not None:
            return self._tokenizer

        with self._initialization_lock:
            if self._tokenizer is not None:
                return self._tokenizer
            try:
                from kiwipiepy import Kiwi

                # 웹 서버 프로세스가 요청마다 별도 작업자 풀을 만들지 않도록 한다.
                self._tokenizer = Kiwi(num_workers=-1)
            except Exception as exc:
                raise KoreanTextAnalyzerError(
                    "KOREAN_TEXT_ANALYZER_UNAVAILABLE",
                    "한국어 형태소 분석기를 사용할 수 없습니다.",
                ) from exc
        return self._tokenizer


korean_text_analyzer = KoreanTextAnalyzer()
