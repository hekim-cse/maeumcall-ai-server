"""Synthetic checks for the preregistered 64-case internal test design."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from evals.structured_nlu.ai_reviewed_internal_policy_v1 import _category
from evals.structured_nlu.schema import DifficultyTag
from experiments.internal_test_pair_v1 import qualification as gate
from experiments.internal_test_pair_v1 import verify as pair_verify


def _cases():
    cases = []
    for scenario in (f"scenario_{index:02d}" for index in range(16)):
        for state in ("greeting", "collecting"):
            for scope in ("in", "out"):
                case_id = f"{scenario}-{state}-{scope}"
                cases.append(
                    SimpleNamespace(
                        id=case_id,
                        scenario_key=scenario,
                        conversation_state=state,
                        user_message=f"synthetic {case_id}",
                        labels=SimpleNamespace(
                            user_action="unknown" if scope == "out" else "provide_details"
                        ),
                        tags=(DifficultyTag.HARD_NEGATIVE,) if scope == "out" else (),
                    )
                )
    return cases


def _inputs():
    return {
        "test_dataset": b"synthetic dataset",
        "test_review_ledger": b"synthetic review",
        "test_case_decisions": b"synthetic decisions",
        "validation_dataset": json.dumps({"cases": [{"user_message": "old validation"}]}).encode(),
        "known_corpus_inventory": b"synthetic inventory",
    }


def test_exact_64_slots_pair_balance_and_overlap(monkeypatch, tmp_path: Path):
    cases = _cases()
    assert len(cases) == 64 and all(
        _category(case) in {"in_scope", "out_of_scope_unknown"} for case in cases
    )
    monkeypatch.setattr(gate, "_checked_split", lambda *args: SimpleNamespace(cases=cases))
    monkeypatch.setattr(gate, "_balanced_scenarios", lambda *args: 4)
    monkeypatch.setattr(gate, "_known_inventory", lambda *args: set())
    ids, digests, slots = gate.qualify_test(tmp_path, _inputs())
    assert len(ids) == len(slots) == 64
    assert len(digests) == 5
    pairs = gate.pair_order(slots)
    assert [pair["case_id"] for pair in pairs] == ids
    for scenario in {row[0] for row in slots}:
        for scope in ("in", "out"):
            arms = [
                pair["arms"]
                for slot, pair in zip(slots, pairs, strict=True)
                if slot[0] == scenario and slot[2] == scope
            ]
            assert arms == [["baseline", "candidate"], ["candidate", "baseline"]]
    known = hashlib.sha256(b"synthetic scenario_00-greeting-in").hexdigest()
    monkeypatch.setattr(gate, "_known_inventory", lambda *args: {known})
    with pytest.raises(ValueError, match="known/validation exact exposure"):
        gate.qualify_test(tmp_path, _inputs())
    cases[-1] = SimpleNamespace(**{**vars(cases[-1]), "conversation_state": "greeting"})
    monkeypatch.setattr(gate, "_known_inventory", lambda *args: set())
    with pytest.raises(ValueError, match="duplicate design slot"):
        gate.qualify_test(tmp_path, _inputs())


def test_rejects_unbalanced_or_missing_review(monkeypatch, tmp_path: Path):
    cases = _cases()
    monkeypatch.setattr(gate, "_checked_split", lambda *args: SimpleNamespace(cases=cases))
    monkeypatch.setattr(gate, "_known_inventory", lambda *args: set())
    monkeypatch.setattr(gate, "_balanced_scenarios", lambda *args: 2)
    with pytest.raises(ValueError, match="sampling balance"):
        gate.qualify_test(tmp_path, _inputs())
    bad = _inputs()
    bad.pop("test_case_decisions")
    with pytest.raises(ValueError, match="input set"):
        gate.qualify_test(tmp_path, bad)


def test_paired_bootstrap_reproducible_and_stratified(monkeypatch):
    cases = _cases()

    def fake_score(_case_tuple, prediction_tuple):
        return SimpleNamespace(counts=SimpleNamespace(fully_correct_cases=int(prediction_tuple[0])))

    monkeypatch.setattr(pair_verify, "score_predictions", fake_score)
    predictions = {
        "baseline": [False] * 64,
        "candidate": [False] * 64,
    }
    predictions["candidate"][0] = True
    first = pair_verify.stratified_bootstrap(cases, predictions)
    assert first == pair_verify.stratified_bootstrap(cases, predictions)
    assert first["difference"] == 1 / 64
    assert first["ci95"][0] <= first["difference"] <= first["ci95"][1]
    assert first["resamples"] == 20_000 and first["seed"] == 0


def test_safety16_category_balance_exposure_and_new_miss_gate(monkeypatch, tmp_path: Path):
    cases = [
        SimpleNamespace(
            id=f"ss-{index:02d}",
            scenario_key="고객센터:a/s 접수",
            conversation_state="greeting",
            user_message=f"합성 안전 {index}",
            labels=SimpleNamespace(
                fields={
                    "safety_status": SimpleNamespace(accepted_values=("safety_issue",))
                    if index < 4
                    else None
                }
            ),
        )
        for index in range(16)
    ]
    categories = [
        {"case_id": case.id, "category": gate.SAFETY_CATEGORIES[index // 4]}
        for index, case in enumerate(cases)
    ]
    inputs = {
        "safety_dataset": b"synthetic safety dataset",
        "safety_review_ledger": b"review",
        "safety_case_decisions": b"decisions",
        "safety_category_ledger": json.dumps(
            {
                "kind": "ai_reviewed_internal_safety16_categories_v1",
                "dataset_sha256": hashlib.sha256(b"synthetic safety dataset").hexdigest(),
                "categories": categories,
            }
        ).encode(),
        "test_dataset": json.dumps({"cases": [{"user_message": "prior test"}]}).encode(),
        "validation_dataset": json.dumps(
            {"cases": [{"user_message": "prior validation"}]}
        ).encode(),
        "known_corpus_inventory": b"inventory",
    }
    monkeypatch.setattr(gate, "_checked_split", lambda *args: SimpleNamespace(cases=cases))
    monkeypatch.setattr(gate, "_known_inventory", lambda *args: set())
    ids, _, slots = gate.qualify_safety(tmp_path, inputs)
    assert len(ids) == 16
    arms = gate.safety_pair_order(slots)
    assert sum(pair["arms"] == ["baseline", "candidate"] for pair in arms) == 8
    assert sum(pair["arms"] == ["candidate", "baseline"] for pair in arms) == 8
    modified = dict(inputs)
    category_raw = json.loads(inputs["safety_category_ledger"])
    category_raw["categories"][0]["category"] = "uncertain"
    modified["safety_category_ledger"] = json.dumps(category_raw).encode()
    with pytest.raises(ValueError, match="category balance"):
        gate.qualify_safety(tmp_path, modified)
    cases[0].labels.fields["safety_status"] = None
    with pytest.raises(ValueError, match="category/gold safety_status conflict"):
        gate.qualify_safety(tmp_path, inputs)
    cases[0].labels.fields["safety_status"] = SimpleNamespace(accepted_values=("safety_issue",))
    cases[8].labels.fields["safety_status"] = SimpleNamespace(accepted_values=("safety_issue",))
    with pytest.raises(ValueError, match="category/gold safety_status conflict"):
        gate.qualify_safety(tmp_path, inputs)
    cases[8].labels.fields["safety_status"] = None
    cases[12].labels.fields["safety_status"] = SimpleNamespace(accepted_values=("safety_issue",))
    with pytest.raises(ValueError, match="category/gold safety_status conflict"):
        gate.qualify_safety(tmp_path, inputs)
    cases[12].labels.fields["safety_status"] = SimpleNamespace(accepted_values=("no_safety_issue",))
    gate.qualify_safety(tmp_path, inputs)
    monkeypatch.setattr(
        gate,
        "_known_inventory",
        lambda *args: {hashlib.sha256("합성 안전 0".encode()).hexdigest()},
    )
    with pytest.raises(ValueError, match="exact exposure"):
        gate.qualify_safety(tmp_path, inputs)

    def prediction(guard: bool):
        return SimpleNamespace(
            final_output=SimpleNamespace(fields={"safety_status": "safety_issue"})
            if guard
            else None
        )

    before = [prediction(index == 0) for index in range(16)]
    after = [prediction(False) for _ in range(16)]
    counts = pair_verify.safety_counts(
        cases,
        {"baseline": before, "candidate": after},
        {row["case_id"]: row["category"] for row in categories},
    )
    assert counts["direct_new_misses"] == 1
    assert counts["gate_status"] == "failed_new_direct_miss"
    assert counts["direct_candidate_misses"] == 4
    assert counts["negative_denominator"] == 8
