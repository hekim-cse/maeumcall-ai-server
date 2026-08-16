from __future__ import annotations

import re
import unicodedata
from typing import Any


def canonicalize_scenario_label(value: Any) -> str:
    """Remove a leading display icon and normalize spacing for exact routing."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    while text and not text[0].isalnum():
        text = text[1:]
    return re.sub(r"\s+", " ", text).strip()


def scenario_matches(
    category: Any,
    title: Any,
    *,
    expected_category: str,
    expected_title: str,
) -> bool:
    return (
        canonicalize_scenario_label(category) == canonicalize_scenario_label(expected_category)
        and canonicalize_scenario_label(title) == canonicalize_scenario_label(expected_title)
    )
