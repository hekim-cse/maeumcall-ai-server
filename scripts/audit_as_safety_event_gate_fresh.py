"""Post-run integrity audit without changing the frozen evaluation verifier."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from scripts.verify_as_safety_event_gate_fresh import verify

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "verifier_sha256": ROOT / "scripts/verify_as_safety_event_gate_fresh.py",
    "gate_sha256": ROOT / "scripts/probe_as_safety_event_gate.py",
    "indexed_probe_sha256": ROOT / "scripts/probe_as_safety_clause_index.py",
    "evidence_probe_sha256": ROOT / "scripts/probe_as_safety_evidence.py",
}


def audit(dataset_path: Path, protocol_path: Path, result_path: Path) -> None:
    """Check frozen implementation and input bounds, then replay the verifier."""
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    for key, path in SOURCES.items():
        if protocol.get(key) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError(f"frozen source differs: {key}")
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    for case in dataset.get("cases", []):
        message = case.get("user_message")
        if not isinstance(message, str) or not message.strip() or len(message) > 1000:
            raise ValueError("reviewed message is empty or too long")
    verify(dataset_path, protocol_path, result_path)


def main() -> None:
    """Run the post-run integrity audit from local artifact paths."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    audit(args.dataset, args.protocol, args.result)
    print("audited frozen A/S event gate exploratory result")


if __name__ == "__main__":
    main()
