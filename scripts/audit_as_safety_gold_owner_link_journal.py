"""Post-run strict audit of the frozen gold-owner diagnostic artifacts.

This supplements the precommitted verifier without changing its hash or the
single model run. It checks issues found during PR review on the existing data.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts import verify_as_safety_gold_owner_link_diagnostic as frozen


def _nonblank(value: object) -> bool:
    """Accept only a nonempty string with at least one visible character."""
    return isinstance(value, str) and bool(value.strip())


def audit(protocol_path: Path, journal_path: Path) -> dict:
    """Verify frozen artifacts, then reject blank quotes and inconsistent failures."""
    report = frozen.verify(protocol_path, journal_path)
    spans = frozen._json(frozen.SOURCES["spans_sha256"].read_text(encoding="utf-8"))["cases"]
    owners = frozen._json(frozen.SOURCES["owner_labels_sha256"].read_text(encoding="utf-8"))[
        "cases"
    ]
    for span, owner in zip(spans, owners, strict=True):
        if not _nonblank(span["target_mention"]) or not _nonblank(span["hazard_event_mention"]):
            raise ValueError("blank target or event mention")
        for entry in owner["accepted_owner_spans"]:
            if not _nonblank(entry["mention"]):
                raise ValueError("blank owner mention")
    lines = journal_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        row = frozen._json(line)
        if (
            row.get("event") == "end"
            and row["error_code"] in {"http_error", "transport_error", "response_error"}
            and row["finish_reason"] is not None
        ):
            raise ValueError("response exception has finish reason")
    return {
        "audit_kind": "postrun_strict_review_v1",
        "frozen_verifier_passed": True,
        "reviewed_mentions_nonblank": True,
        "response_exception_finish_reason_consistent": True,
        "journal_rows": len(lines),
        "relation_correct": report["summary"]["all"]["relation_correct"],
        "denominator": report["summary"]["all"]["denominator"],
    }


def main() -> None:
    """Run the post-run audit from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.protocol, args.journal), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
