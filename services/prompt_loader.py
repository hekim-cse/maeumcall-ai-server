# services/prompt_loader.py
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from functools import lru_cache
from typing import List, Dict
import configparser
import os

from .prompt_registry import get_prompt_path, category_dir_path
from core.config import PROMPT_CACHE

def _norm_lines(v: str | None) -> List[str]:
    if not v:
        return []
    lines = [s.strip() for s in v.splitlines() if s.strip()]
    if len(lines) == 1 and "," in lines[0]:
        return [s.strip() for s in lines[0].split(",") if s.strip()]
    return lines

@dataclass
class PromptConfig:
    meta: Dict[str, str] = field(default_factory=dict)
    prefer: List[str] = field(default_factory=list)
    avoid: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)

    def merge_from(self, other: "PromptConfig") -> "PromptConfig":
        return PromptConfig(
            meta={**self.meta, **other.meta},
            prefer=[*dict.fromkeys([*self.prefer, *other.prefer])],
            avoid=[*dict.fromkeys([*self.avoid, *other.avoid])],
            examples=[*dict.fromkeys([*self.examples, *other.examples])],
        )

def _load_ini(path: Path) -> PromptConfig:
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.optionxform = str
    if not path or not path.exists():
        return PromptConfig()
    cfg.read(path, encoding="utf-8")

    pc = PromptConfig()
    if cfg.has_section("meta"):
        for k, v in cfg.items("meta"):
            pc.meta[k] = v.strip()
    if cfg.has_section("prefer"):
        pc.prefer = _norm_lines(cfg.get("prefer", "lines", fallback=""))
    if cfg.has_section("avoid"):
        pc.avoid = _norm_lines(cfg.get("avoid", "lines", fallback=""))
    if cfg.has_section("examples"):
        pc.examples = _norm_lines(cfg.get("examples", "lines", fallback=""))
    return pc

def load_prompt_config(category: str, scenario_key: str) -> PromptConfig:
    return _load_prompt_config_cached(category, scenario_key) if PROMPT_CACHE else _load_prompt_config_nocache(category, scenario_key)

@lru_cache(maxsize=256)
def _load_prompt_config_cached(category: str, scenario_key: str) -> PromptConfig:
    return _load_prompt_config_nocache(category, scenario_key)

def _load_prompt_config_nocache(category: str, scenario_key: str) -> PromptConfig:
    scenario_path = get_prompt_path(category, scenario_key)
    default_ini = (category_dir_path(category) / "_default.ini")
    base = _load_ini(default_ini)
    spec = _load_ini(scenario_path)
    return base.merge_from(spec)