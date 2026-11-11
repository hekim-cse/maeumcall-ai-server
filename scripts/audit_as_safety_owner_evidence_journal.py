"""Supplement the frozen owner-evidence verifier with strict JSONL parsing.

This audit was added after the model run. It does not change the precommitted
runner, protocol, original verifier, or result journal.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.verify_as_safety_owner_evidence_diagnostic import verify


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate keys at every level of a journal row."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("owner journal has duplicate JSON keys")
        result[key] = value
    return result


def audit(protocol_path: Path, journal_path: Path) -> dict:
    """Check raw row syntax before invoking the independently frozen verifier."""
    for line in journal_path.read_text(encoding="utf-8").splitlines():
        json.loads(line, object_pairs_hook=_unique_object)
    return verify(protocol_path, journal_path)


def main() -> None:
    """Run the supplementary read-only audit against a frozen journal."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.protocol, args.journal)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
