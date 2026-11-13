"""Load already exposed, reviewed development cases without model calls."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from experiments.as_safety_v2.quotes import anchor_span, split_clauses

CASE_IDS = tuple(
    [*(f"RE{i:02}" for i in range(1, 7)), *(f"RE{i:02}" for i in range(8, 12))]
    + [*(f"V{i:02}" for i in range(1, 9)), "V10", "V12", "V14", "V16"]
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def load_development_cases(
    *,
    re_dataset: Path,
    v_dataset: Path,
    labels_path: Path,
    spans_path: Path,
    subject_path: Path,
    owner_review_path: Path,
) -> list[dict]:
    """Verify exact approved references and return 22 development cases.

    E/B/C references are returned for scoring only. The model runner must pass
    only ``user_message`` and ``target`` to its prompt construction function.
    """
    labels = _read(labels_path)
    if (
        set(labels)
        != {
            "kind",
            "provenance",
            "review_status",
            "source_sha256",
            "cases",
            "interpretation_note",
        }
        or labels["kind"] != "as_safety_extraction_v2_development_labels_v1"
        or labels["provenance"] != "ai_authored_already_exposed"
        or labels["review_status"] != "derived_from_user_approved_development_annotations"
        or labels["source_sha256"]
        != {
            "spans": _sha256(spans_path),
            "subject": _sha256(subject_path),
            "owner_review": _sha256(owner_review_path),
        }
    ):
        raise ValueError("development label provenance differs")
    datasets = [_read(re_dataset), _read(v_dataset)]
    for dataset, kind in zip(
        datasets,
        ("as_safety_relation_ai_reviewed_v1", "as_safety_relation_v2_ai_reviewed_v1"),
        strict=True,
    ):
        if (
            dataset.get("kind") != kind
            or dataset.get("provenance") != "ai_authored"
            or dataset.get("review_status") != "owner_approved_for_exploration"
            or not isinstance(dataset.get("cases"), list)
        ):
            raise ValueError("reviewed source dataset differs")
    sources = {case["id"]: case for dataset in datasets for case in dataset["cases"]}
    annotated = labels["cases"]
    if not isinstance(annotated, list) or tuple(row.get("id") for row in annotated) != CASE_IDS:
        raise ValueError("development case count or order differs")
    selected = []
    for row in annotated:
        if set(row) != {
            "id",
            "utterance_sha256",
            "target",
            "event_reference",
            "subject_reference",
            "owner_reference",
            "relation",
            "event_status",
            "owner_referent",
            "subject_interpretation",
        }:
            raise ValueError("development label fields differ")
        source = sources[row["id"]]
        message = source["user_message"]
        if hashlib.sha256(message.encode("utf-8")).hexdigest() != row["utterance_sha256"]:
            raise ValueError("development utterance differs")
        clauses = split_clauses(message)
        for field in ("target", "event_reference", "subject_reference", "owner_reference"):
            anchor_span(row[field], clauses, field=field)
        if row["owner_referent"] is not None:
            anchor_span(row["owner_referent"], clauses, field="owner_referent")
        if row["id"] == "RE02":
            if row["owner_referent"] != {"clause_index": 1, "quote": "공기순환기"}:
                raise ValueError("RE02 referent differs")
        elif row["owner_referent"] is not None:
            raise ValueError("unexpected referent annotation")
        if row["subject_interpretation"] != ("믹서기 바닥" if row["id"] == "V07" else None):
            raise ValueError("subject interpretation differs")
        if row["relation"] not in {"current", "other"} or row["event_status"] not in {
            "observed",
            "uncertain",
        }:
            raise ValueError("development labels contain unsupported value")
        selected.append({"id": row["id"], "user_message": message, **row})
    return selected
