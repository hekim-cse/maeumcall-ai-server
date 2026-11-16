"""Freeze PF01–PF16 against the already committed validation runtime."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from evals.structured_nlu.ai_heldout import load_reviewed_ai_heldout
from experiments.internal_validation_pair_v1 import qualification as q

ROOT = Path(__file__).resolve().parents[2]
DATASET = "evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-reviewed.v1.json"
LEDGER = "evals/structured_nlu/data/ai_heldout/nlu-safety-postfreeze-ledger.v1.json"
HARNESS = "experiments/internal_validation_pf_sentinel_v1"
KIND = "exposed_pf_safety_regression_gate_v1"
IDS = [f"nlu-safety-postfreeze-pf{i:02}" for i in range(1, 17)]


def _manifest(root: Path, commit: str) -> dict[str, str]:
    names = (
        q._git(root, "ls-tree", "-r", "--name-only", commit, "--", HARNESS).decode().splitlines()
    )
    files = sorted(name for name in names if name.endswith(".py"))
    if len(files) < 4 or f"{HARNESS}/gate.py" not in files:
        raise ValueError("PF harness is not committed")
    return {name: q._sha(q._frozen(root, commit, name)) for name in files}


def build(
    *,
    root: Path,
    baseline_root: Path,
    validation_protocol: Path,
    model_path: Path,
    result: Path,
    journal: Path,
    private_dir: Path,
    receipt: Path,
    harness_commit: str | None = None,
) -> dict:
    validation, validation_sha = q.preflight(
        protocol_path=validation_protocol,
        baseline_root=baseline_root,
        candidate_root=root,
        model_path=model_path,
        output=Path(json.loads(validation_protocol.read_bytes())["output_paths"]["result"]),
        journal=Path(json.loads(validation_protocol.read_bytes())["output_paths"]["journal"]),
        private_dir=Path(
            json.loads(validation_protocol.read_bytes())["output_paths"]["private_dir"]
        ),
        receipt=Path(
            json.loads(validation_protocol.read_bytes())["output_paths"]["verified_receipt"]
        ),
    )
    if q._file_sha(model_path) != validation["model_sha256"]:
        raise ValueError("Q5 file differs")
    source = root / DATASET
    ledger = root / LEDGER
    reviewed = load_reviewed_ai_heldout(
        source, ledger, expected_scenario_keys=frozenset({"고객센터:a/s 접수"})
    )
    if [case.id for case in reviewed.dataset.cases] != IDS:
        raise ValueError("PF case order differs")
    for index, case in enumerate(reviewed.dataset.cases):
        expected = case.labels.fields["safety_status"]
        if index < 8:
            if expected is None or "safety_issue" not in expected.accepted_values:
                raise ValueError("PF direct-danger label differs")
        elif expected is not None and "safety_issue" in expected.accepted_values:
            raise ValueError("PF negative label differs")
    for role, arm_root in (("baseline", baseline_root), ("candidate", root)):
        commit = validation["arms"][role]["commit"]
        if q._frozen(arm_root, commit, DATASET) != source.read_bytes():
            raise ValueError(f"{role} PF dataset differs")
        if q._frozen(arm_root, commit, LEDGER) != ledger.read_bytes():
            raise ValueError(f"{role} PF review ledger differs")
    head = q._git(root, "rev-parse", "HEAD").decode().strip()
    harness_commit = harness_commit or head
    q._git(root, "merge-base", "--is-ancestor", harness_commit, head)
    paths = q._output_paths(result, journal, private_dir, receipt, baseline_root, root)
    if any(
        Path(left).is_relative_to(right) or Path(right).is_relative_to(left)
        for left in paths.values()
        for right in validation["output_paths"].values()
    ):
        raise ValueError("PF outputs reuse validation paths")
    return {
        "kind": KIND,
        "scope": "exposed_ai_authored_pf_development_safety_regression_only",
        "validation_protocol_sha256": validation_sha,
        "dataset_sha256": q._file_sha(source),
        "review_ledger_sha256": q._file_sha(ledger),
        "harness_commit": harness_commit,
        "harness_manifest": _manifest(root, harness_commit),
        "pair_order": [
            {
                "case_id": case_id,
                "arms": (["baseline", "candidate"] if i % 2 == 0 else ["candidate", "baseline"]),
            }
            for i, case_id in enumerate(IDS)
        ],
        "output_paths": paths,
    }


def check(
    *,
    protocol_path: Path,
    root: Path,
    baseline_root: Path,
    validation_protocol: Path,
    model_path: Path,
) -> tuple[dict, dict]:
    raw = protocol_path.read_bytes()
    protocol = q._strict_json(raw)
    if type(protocol) is not dict or set(protocol) != {
        "kind",
        "scope",
        "validation_protocol_sha256",
        "dataset_sha256",
        "review_ledger_sha256",
        "harness_commit",
        "harness_manifest",
        "pair_order",
        "output_paths",
    }:
        raise ValueError("PF protocol shape differs")
    output_paths = protocol["output_paths"]
    expected = build(
        root=root,
        baseline_root=baseline_root,
        validation_protocol=validation_protocol,
        model_path=model_path,
        result=Path(output_paths["result"]),
        journal=Path(output_paths["journal"]),
        private_dir=Path(output_paths["private_dir"]),
        receipt=Path(output_paths["verified_receipt"]),
        harness_commit=protocol["harness_commit"],
    )
    if protocol != expected:
        raise ValueError("PF protocol differs from frozen inputs")
    relative = protocol_path.resolve().relative_to(root.resolve()).as_posix()
    if q._git(root, "show", f"HEAD:{relative}") != raw:
        raise ValueError("PF protocol must be committed")
    current_names = {
        name
        for name in q._git(root, "ls-files", "--", HARNESS).decode().splitlines()
        if name.endswith(".py")
    }
    if current_names != set(protocol["harness_manifest"]):
        raise ValueError("PF harness source set changed")
    for name, digest in protocol["harness_manifest"].items():
        if q._file_sha(root / name) != digest:
            raise ValueError(f"PF harness source differs: {name}")
    validation = q._strict_json(validation_protocol.read_bytes())
    return protocol, validation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "check"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--baseline-root", type=Path, required=True)
    parser.add_argument("--validation-protocol", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, required=True)
    parser.add_argument("--result", type=Path)
    parser.add_argument("--journal", type=Path)
    parser.add_argument("--private-dir", type=Path)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    if args.mode == "build":
        if any(
            path is None for path in (args.result, args.journal, args.private_dir, args.receipt)
        ):
            parser.error("build requires all four output paths")
        protocol = build(
            root=args.root,
            baseline_root=args.baseline_root,
            validation_protocol=args.validation_protocol,
            model_path=args.model_path,
            result=args.result,
            journal=args.journal,
            private_dir=args.private_dir,
            receipt=args.receipt,
        )
        with args.protocol.open("x", encoding="utf-8") as stream:
            json.dump(protocol, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
    else:
        protocol, _ = check(
            protocol_path=args.protocol,
            root=args.root,
            baseline_root=args.baseline_root,
            validation_protocol=args.validation_protocol,
            model_path=args.model_path,
        )
        print(json.dumps({"pf_cases": len(protocol["pair_order"]), "model_calls": 0}))


if __name__ == "__main__":
    main()
