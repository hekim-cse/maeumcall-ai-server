import pytest

from llm.errors import PromptConfigurationError
from llm.prompt_builder import load_scenario_prompt
from services.flow.registry import FLOW_REGISTRY
from services.prompt_loader import _load_json
from services.prompt_registry import CATEGORY_DIR_MAP, category_dir_path, get_prompt_path


pytestmark = pytest.mark.unit


@pytest.mark.parametrize("registration", list(FLOW_REGISTRY.values()), ids=lambda item: item.key)
def test_product_scenario_prompt_files_exist(registration):
    path = get_prompt_path(registration.category, f"📞 {registration.title}")

    assert path.exists(), f"missing prompt mapping: {registration.key}"


def test_json_dialogue_is_loaded_as_prompt_examples():
    prompt = load_scenario_prompt("친구", "🎉 생일 축하 전화")

    assert prompt["examples"]
    assert any("생일 축하" in line for line in prompt["examples"])


def test_ini_metadata_and_examples_are_merged():
    prompt = load_scenario_prompt("가족", "🗣️ 안부인사")

    assert prompt["gpt_role"] == "엄마"
    assert prompt["tone"]
    assert prompt["examples"]


def test_unregistered_prompt_key_is_rejected():
    with pytest.raises(PromptConfigurationError):
        get_prompt_path("회사", "보고서")


def test_invalid_prompt_json_is_rejected(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"role":"user"}', encoding="utf-8")

    with pytest.raises(PromptConfigurationError):
        _load_json(path)


@pytest.mark.parametrize("category", CATEGORY_DIR_MAP)
def test_category_prompt_defaults_define_real_policy(category):
    path = category_dir_path(category) / "_default.ini"
    content = path.read_text(encoding="utf-8")

    assert "[meta]" in content
    assert "tone" in content
