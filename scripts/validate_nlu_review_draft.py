"""Check the round-two AI review packet without treating it as official test data."""

from __future__ import annotations

import json
import re
from pathlib import Path

from evals.structured_nlu.ai_origin_policy import (
    AI_ORIGIN_TEXT_FINGERPRINTS_V8,
    ai_origin_text_fingerprint_v1,
)
from evals.structured_nlu.contracts import EVALUATION_CONTRACTS

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = ROOT / "docs/portfolio/heldout_nlu_ai_draft_round2.md"
LABELS = ROOT / "docs/portfolio/heldout_nlu_label_draft_round2.md"
EXPOSED_CANDIDATES = ROOT / "docs/portfolio/heldout_nlu_ai_candidates.md"
DEVELOPMENT_CORPUS = ROOT / "evals/structured_nlu/data/compiled/gold-dataset.v2.json"
EXPECTED_SLOTS = {f"H{number:02}" for number in range(1, 37)}


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.split("|")[1:-1]]


def _sentence_rows(path: Path = SENTENCES) -> dict[str, tuple[str, str]]:
    rows = {}
    for line in path.read_text().splitlines():
        if not re.match(r"^\| H\d\d ", line):
            continue
        cells = _cells(line)
        if len(cells) != 6:
            raise ValueError("sentence row must have six columns")
        slot, scenario = cells[0].split(" ", 1)
        if slot in rows:
            raise ValueError(f"duplicate sentence slot: {slot}")
        if "문장 후보 채택" not in cells[4]:
            raise ValueError(f"sentence has not been adopted: {slot}")
        rows[slot] = (scenario.replace("A/S", "a/s"), cells[2])
    return rows


def _label_rows() -> dict[str, list[str]]:
    rows = {}
    for line in LABELS.read_text().splitlines():
        if not re.match(r"^\| H\d\d ", line):
            continue
        cells = _cells(line)
        if len(cells) == 3:  # User decision summary above the label table.
            continue
        if len(cells) != 6:
            raise ValueError("label row must have six columns")
        slot = cells[0]
        if slot in rows:
            raise ValueError(f"duplicate label slot: {slot}")
        rows[slot] = cells
    return rows


def _previous_text_fingerprints() -> set[str]:
    exposed = set(AI_ORIGIN_TEXT_FINGERPRINTS_V8)
    for line in EXPOSED_CANDIDATES.read_text().splitlines():
        if re.match(r"^\| C\d\d ", line):
            exposed.add(ai_origin_text_fingerprint_v1(_cells(line)[2]))
    corpus = json.loads(DEVELOPMENT_CORPUS.read_text())
    exposed.update(ai_origin_text_fingerprint_v1(case["user_message"]) for case in corpus["cases"])
    return exposed


def load_draft_cases(*, sentences_path: Path = SENTENCES) -> list[dict]:
    sentences = _sentence_rows(sentences_path)
    labels = _label_rows()
    if set(sentences) != EXPECTED_SLOTS or set(labels) != EXPECTED_SLOTS:
        raise ValueError("sentence and label slots must both be H01 through H36")

    fingerprints = [ai_origin_text_fingerprint_v1(text) for _, text in sentences.values()]
    if len(set(fingerprints)) != len(fingerprints):
        raise ValueError("draft sentences have exact NFC duplicates")
    if set(fingerprints) & _previous_text_fingerprints():
        raise ValueError("draft sentences exactly overlap previously recorded material")

    cases = []
    for slot in sorted(EXPECTED_SLOTS):
        scenario, user_message = sentences[slot]
        contract = EVALUATION_CONTRACTS[scenario]
        cells = labels[slot]
        state, intent, action = (cell.strip("`") for cell in cells[1:4])
        fields = dict.fromkeys(contract.field_names)
        assignments = re.findall(r"`([^`]+)`", cells[4])
        remainder = re.sub(r"`[^`]+`", "", cells[4])
        if remainder.strip(" ;,") not in ("", "없음") or (assignments and remainder.strip(" ;,")):
            raise ValueError(f"invalid label field text in {slot}: {cells[4]}")
        for assignment in assignments:
            if "=" not in assignment:
                raise ValueError(f"invalid label field assignment in {slot}: {assignment}")
            field, value = assignment.split("=", 1)
            if field not in fields:
                raise ValueError(f"unknown label field in {slot}: {field}")
            fields[field] = value
        contract.validate_prediction(
            intent=intent,
            fields=fields,
            user_action=action,
            change_field=None,
            conversation_state=state,
            current_fields=dict.fromkeys(contract.field_names)
            if contract.uses_current_fields
            else {},
            offered_alternative_times=(),
        )

        cases.append(
            {
                "id": slot,
                "scenario_key": scenario,
                "conversation_state": state,
                "current_fields": dict.fromkeys(contract.field_names)
                if contract.uses_current_fields
                else {},
                "offered_alternative_times": [],
                "user_message": user_message,
                "labels": {
                    "intent": intent,
                    "user_action": action,
                    "change_field": None,
                    "fields": {
                        name: None if value is None else {"accepted_values": [value]}
                        for name, value in fields.items()
                    },
                },
            }
        )
    return cases


def main() -> None:
    cases = load_draft_cases()

    print(
        f"{len(cases)} adopted AI sentence candidates; valid label drafts; no exact prior-text overlap"
    )
    print("Meaning, human authorship, split assignment, and adjudication are not verified")


if __name__ == "__main__":
    main()
