# services/prompt_loader.py
from __future__ import annotations

import configparser
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from core.config import PROMPT_CACHE
from llm.errors import PromptConfigurationError

from .prompt_registry import category_dir_path, get_prompt_path


def _norm_lines(v: str | None) -> list[str]:
    if not v:
        return []
    lines = [s.strip() for s in v.splitlines() if s.strip()]
    if len(lines) == 1 and "," in lines[0]:
        return [s.strip() for s in lines[0].split(",") if s.strip()]
    return lines


def _read_lines_option(cfg: configparser.ConfigParser, section: str) -> list[str]:
    if not cfg.has_option(section, "lines"):
        return []
    return _norm_lines(cfg.get(section, "lines"))


@dataclass
class PromptConfig:
    meta: dict[str, str] = field(default_factory=dict)
    prefer: list[str] = field(default_factory=list)
    avoid: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    openers: list[str] = field(default_factory=list)
    closers: list[str] = field(default_factory=list)
    topic_hints: list[str] = field(default_factory=list)

    def merge_from(self, other: PromptConfig) -> PromptConfig:
        return PromptConfig(
            meta={**self.meta, **other.meta},
            prefer=[*dict.fromkeys([*self.prefer, *other.prefer])],
            avoid=[*dict.fromkeys([*self.avoid, *other.avoid])],
            examples=[*dict.fromkeys([*self.examples, *other.examples])],
            openers=[*dict.fromkeys([*self.openers, *other.openers])],
            closers=[*dict.fromkeys([*self.closers, *other.closers])],
            topic_hints=[*dict.fromkeys([*self.topic_hints, *other.topic_hints])],
        )


def _load_ini(path: Path) -> PromptConfig:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    if not path.exists():
        raise PromptConfigurationError(f"Prompt file does not exist: {path}")
    try:
        loaded = cfg.read(path, encoding="utf-8")
    except (OSError, configparser.Error) as exc:
        raise PromptConfigurationError(f"Prompt INI is invalid: {path}") from exc
    if not loaded:
        raise PromptConfigurationError(f"Prompt INI could not be read: {path}")

    pc = PromptConfig()
    if cfg.has_section("meta"):
        for k, v in cfg.items("meta"):
            pc.meta[k] = v.strip()
    if cfg.has_section("prefer"):
        pc.prefer = _read_lines_option(cfg, "prefer")
    if cfg.has_section("avoid"):
        pc.avoid = _read_lines_option(cfg, "avoid")
    if cfg.has_section("examples"):
        pc.examples = _read_lines_option(cfg, "examples")
    if cfg.has_section("openers"):
        pc.openers = _read_lines_option(cfg, "openers")
    if cfg.has_section("closers"):
        pc.closers = _read_lines_option(cfg, "closers")
    if cfg.has_section("topic_hints"):
        pc.topic_hints = _read_lines_option(cfg, "topic_hints")
    return pc


def _load_json(path: Path) -> PromptConfig:
    if not path.exists():
        raise PromptConfigurationError(f"Prompt file does not exist: {path}")
    try:
        data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PromptConfigurationError(f"Prompt JSON is invalid: {path}") from exc
    if not isinstance(data, list):
        raise PromptConfigurationError(f"Prompt JSON must be a list: {path}")
    examples: list[str] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise PromptConfigurationError(f"Prompt item {index} must be an object: {path}")
        role = str(item.get("role") or "").lower()
        text = str(item.get("text") or item.get("content") or "").strip()
        if role not in {"user", "system", "assistant"}:
            raise PromptConfigurationError(f"Prompt item {index} has an invalid role: {path}")
        if not text:
            raise PromptConfigurationError(f"Prompt item {index} has empty text: {path}")
        speaker = "사용자" if role == "user" else "상대역"
        examples.append(f"{speaker}: {text}")
    return PromptConfig(examples=examples)


def _load_prompt_file(path: Path) -> PromptConfig:
    return _load_json(path) if path.suffix.lower() == ".json" else _load_ini(path)


def load_prompt_config(category: str, scenario_key: str) -> PromptConfig:
    return (
        _load_prompt_config_cached(category, scenario_key)
        if PROMPT_CACHE
        else _load_prompt_config_nocache(category, scenario_key)
    )


@lru_cache(maxsize=256)
def _load_prompt_config_cached(category: str, scenario_key: str) -> PromptConfig:
    return _load_prompt_config_nocache(category, scenario_key)


def _load_prompt_config_nocache(category: str, scenario_key: str) -> PromptConfig:
    scenario_path = get_prompt_path(category, scenario_key)
    default_ini = category_dir_path(category) / "_default.ini"
    base = _load_prompt_file(default_ini)
    spec = _load_prompt_file(scenario_path)
    return base.merge_from(spec)
