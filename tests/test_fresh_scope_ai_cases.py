import json

import pytest

from scripts.fresh_scope_ai_cases import FIELD_DRAFT, load_cases
from scripts.probe_gguf_scope_instruction import CASE_SETS


def test_fresh_scope_cases_cover_all_scenarios_with_reviewed_action_directions():
    cases = load_cases()
    assert [case["id"] for case in cases] == [f"F{i:02}" for i in range(1, 33)]
    assert len({case["scenario_key"] for case in cases}) == 16
    assert all(case["labels"]["user_action"] == "unknown" for case in cases[1::2])
    assert all(case["labels"]["user_action"] != "unknown" for case in cases[::2])
    assert cases[16]["labels"]["fields"]["resolution_preference"] == {
        "accepted_values": ["redelivery"]
    }
    assert cases[28]["labels"]["fields"]["date"] is None
    assert CASE_SETS["fresh"][2]() == cases


@pytest.mark.parametrize(
    ("case_id", "field", "value", "expected"),
    [
        ("F03", "inquiry_type", "not-an-option", "not allowed"),
        ("F01", "symptom", "   ", "nonblank strings"),
        ("F01", "unexpected_field", "value", "unknown draft field"),
    ],
)
def test_fresh_scope_cases_reject_invalid_field_drafts(tmp_path, case_id, field, value, expected):
    source = json.loads(FIELD_DRAFT.read_text())
    pair = next(pair for pair in source["pairs"] if pair["positive_id"] == case_id)
    pair["positive_fields"][field] = value
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps(source))
    with pytest.raises(ValueError, match=expected):
        load_cases(fields_path=changed)


def test_fresh_scope_cases_reject_swapped_scenario_assignments(tmp_path):
    source = json.loads(FIELD_DRAFT.read_text())
    first, later = source["pairs"][0], source["pairs"][12]
    for key in ("positive_id", "negative_id"):
        first[key], later[key] = later[key], first[key]
    changed = tmp_path / "swapped.json"
    changed.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="scenario display name differs"):
        load_cases(fields_path=changed)
