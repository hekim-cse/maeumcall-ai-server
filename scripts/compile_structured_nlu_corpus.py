from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from evals.structured_nlu.authoring import (
    compile_authoring_directory,
    ensure_output_does_not_replace_manifest,
    ensure_output_outside_source,
    serialize_authoring_group_schema,
    serialize_gold_dataset,
    serialize_split_assignment_schema,
    verify_compiled_authoring_corpus,
)
from evals.structured_nlu.contrast import (
    serialize_contrast_manifest_schema,
    verify_contrast_manifest,
)
from evals.structured_nlu.obligations import serialize_official_authoring_obligations
from evals.structured_nlu.review import (
    serialize_review_ledger_schema,
    verify_review_ledger,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile group-owned structured NLU authoring files deterministically.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile", help="Write the compiled V2 corpus.")
    compile_parser.add_argument("source_dir", type=Path)
    compile_parser.add_argument("split_assignments", type=Path)
    compile_parser.add_argument("output", type=Path)

    check_parser = subparsers.add_parser(
        "check",
        help="Verify that a committed compiled corpus matches its authoring sources.",
    )
    check_parser.add_argument("source_dir", type=Path)
    check_parser.add_argument("split_assignments", type=Path)
    check_parser.add_argument("compiled", type=Path)

    obligations_parser = subparsers.add_parser(
        "obligations",
        help="Write the contract-derived authoring checklist.",
    )
    obligations_parser.add_argument("output", type=Path)

    check_obligations_parser = subparsers.add_parser(
        "check-obligations",
        help="Verify that the committed authoring inventory matches the live contract.",
    )
    check_obligations_parser.add_argument("manifest", type=Path)

    schema_parser = subparsers.add_parser(
        "schema",
        help="Write the editor-facing AuthoringGroup JSON Schema.",
    )
    schema_parser.add_argument("output", type=Path)

    check_schema_parser = subparsers.add_parser(
        "check-schema",
        help="Verify that the committed AuthoringGroup schema matches the code contract.",
    )
    check_schema_parser.add_argument("schema", type=Path)

    split_schema_parser = subparsers.add_parser(
        "split-schema",
        help="Write the editor-facing split assignment JSON Schema.",
    )
    split_schema_parser.add_argument("output", type=Path)

    check_split_schema_parser = subparsers.add_parser(
        "check-split-schema",
        help="Verify that the committed split assignment schema matches the code contract.",
    )
    check_split_schema_parser.add_argument("schema", type=Path)

    review_schema_parser = subparsers.add_parser(
        "review-schema",
        help="Write the editor-facing adjudication review ledger JSON Schema.",
    )
    review_schema_parser.add_argument("output", type=Path)

    check_review_schema_parser = subparsers.add_parser(
        "check-review-schema",
        help="Verify that the committed review ledger schema matches the code contract.",
    )
    check_review_schema_parser.add_argument("schema", type=Path)

    check_review_parser = subparsers.add_parser(
        "check-review",
        help="Verify exact adjudication records for compiled validation and test cases.",
    )
    check_review_parser.add_argument("source_dir", type=Path)
    check_review_parser.add_argument("split_assignments", type=Path)
    check_review_parser.add_argument("compiled", type=Path)
    check_review_parser.add_argument("guideline", type=Path)
    check_review_parser.add_argument("ledger", type=Path)

    contrast_schema_parser = subparsers.add_parser(
        "contrast-schema",
        help="Write the editor-facing contrast manifest JSON Schema.",
    )
    contrast_schema_parser.add_argument("output", type=Path)

    check_contrast_schema_parser = subparsers.add_parser(
        "check-contrast-schema",
        help="Verify that the committed contrast manifest schema matches the code contract.",
    )
    check_contrast_schema_parser.add_argument("schema", type=Path)

    check_contrast_parser = subparsers.add_parser(
        "check-contrast",
        help="Verify contrast roles against the source-owned compiled corpus.",
    )
    check_contrast_parser.add_argument("source_dir", type=Path)
    check_contrast_parser.add_argument("split_assignments", type=Path)
    check_contrast_parser.add_argument("compiled", type=Path)
    check_contrast_parser.add_argument("manifest", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "obligations":
        _write_text(args.output, serialize_official_authoring_obligations())
        return 0
    if args.command == "check-obligations":
        if not args.manifest.is_file():
            raise SystemExit(f"obligation manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != (
            serialize_official_authoring_obligations()
        ):
            raise SystemExit("obligation manifest differs from the live contract")
        return 0
    if args.command == "schema":
        _write_text(args.output, serialize_authoring_group_schema())
        return 0
    if args.command == "check-schema":
        if not args.schema.is_file():
            raise SystemExit(f"authoring schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_authoring_group_schema():
            raise SystemExit("authoring schema differs from the code contract")
        return 0
    if args.command == "split-schema":
        _write_text(args.output, serialize_split_assignment_schema())
        return 0
    if args.command == "check-split-schema":
        if not args.schema.is_file():
            raise SystemExit(f"split assignment schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_split_assignment_schema():
            raise SystemExit("split assignment schema differs from the code contract")
        return 0
    if args.command == "review-schema":
        _write_text(args.output, serialize_review_ledger_schema())
        return 0
    if args.command == "check-review-schema":
        if not args.schema.is_file():
            raise SystemExit(f"review ledger schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_review_ledger_schema():
            raise SystemExit("review ledger schema differs from the code contract")
        return 0
    if args.command == "check-review":
        dataset, _, _ = verify_compiled_authoring_corpus(
            args.source_dir,
            args.split_assignments,
            args.compiled,
        )
        verify_review_ledger(
            dataset,
            args.guideline,
            args.ledger,
        )
        return 0
    if args.command == "contrast-schema":
        _write_text(args.output, serialize_contrast_manifest_schema())
        return 0
    if args.command == "check-contrast-schema":
        if not args.schema.is_file():
            raise SystemExit(f"contrast manifest schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_contrast_manifest_schema():
            raise SystemExit("contrast manifest schema differs from the code contract")
        return 0
    if args.command == "check-contrast":
        dataset, _, _ = verify_compiled_authoring_corpus(
            args.source_dir,
            args.split_assignments,
            args.compiled,
        )
        verify_contrast_manifest(dataset, args.manifest)
        return 0

    if args.command == "compile":
        ensure_output_outside_source(args.source_dir, args.output)
        ensure_output_does_not_replace_manifest(args.split_assignments, args.output)
        compiled_text = serialize_gold_dataset(
            compile_authoring_directory(args.source_dir, args.split_assignments)
        )
        _write_text(args.output, compiled_text)
        return 0

    verify_compiled_authoring_corpus(
        args.source_dir,
        args.split_assignments,
        args.compiled,
    )
    return 0


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".writing",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
