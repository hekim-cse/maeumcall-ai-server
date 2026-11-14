"""The exploratory gold must match the user-reviewed tables exactly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.as_safety_v4.cases import CASE_IDS, load_cases

DATA = (
    Path(__file__).resolve().parents[1]
    / "evals/structured_nlu/data/ai_heldout/as-safety-event-source-v4-exploration-reviewed.v1.json"
)


def test_reviewed_dataset_loads_without_model_calls() -> None:
    cases = load_cases(DATA)
    assert tuple(case["id"] for case in cases) == CASE_IDS
    assert sum(len(case["events"]) for case in cases) == 22
    assert [case["id"] for case in cases if len(case["events"]) == 2] == ["ES06", "ES15"]
    assert cases[16]["events"][0]["owner_to_target"] == "unknown"
    assert cases[17]["events"][0]["occurrence"] == "uncertain"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data["cases"].reverse(), "case ID order"),
        (lambda data: data["cases"][0].update(user_message="수정된 발화"), "utterance hash"),
        (lambda data: data["cases"][0]["events"][0].update(owner_to_target="other"),
         "reviewed route"),
        (lambda data: data["cases"][8]["events"][0]["hazard_owner_span"].update(
            quote="탁상 조명"), "reviewed values"),
        (lambda data: data["cases"][5]["events"][1]["event_span"].update(
            quote="다른 기기의 충전기에서 불꽃이 튀었고"), "event spans overlap"),
        (lambda data: data["source_sha256"].update(fields="0" * 64), "review provenance"),
    ],
)
def test_rejects_tampering(tmp_path: Path, change, message: str) -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    change(data)
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        load_cases(path)


def test_gold_mutation_does_not_change_source_data() -> None:
    first = load_cases(DATA)
    first[0]["events"][0]["occurrence"] = "nonoccurring"
    assert load_cases(DATA)[0]["events"][0]["occurrence"] == "observed"
