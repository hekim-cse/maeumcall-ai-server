from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path

from evals.structured_nlu.freeze import (
    FreezeArtifactPathsV1,
    create_freeze_record_file,
    serialize_freeze_record_schema,
    verify_freeze_record,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create or verify an explicit structured-NLU benchmark freeze record.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema_parser = subparsers.add_parser(
        "schema",
        help="Write the editor-facing freeze record JSON Schema.",
    )
    schema_parser.add_argument("output", type=Path)

    check_schema_parser = subparsers.add_parser(
        "check-schema",
        help="Verify that the committed freeze record schema matches the code contract.",
    )
    check_schema_parser.add_argument("schema", type=Path)

    create_parser = subparsers.add_parser(
        "create",
        help="Create a new immutable record from one committed input snapshot.",
    )
    _add_common_artifact_arguments(create_parser)
    create_parser.add_argument("--output", type=Path, required=True)
    create_parser.add_argument("--freeze-id", required=True)
    create_parser.add_argument("--freeze-revision", type=int, required=True)
    create_parser.add_argument("--previous-record", type=Path, action="append", default=[])
    create_parser.add_argument("--input-git-revision", required=True)

    verify_parser = subparsers.add_parser(
        "verify",
        help="Recompute every governed value from one explicitly named record.",
    )
    verify_parser.add_argument("--repo-root", type=Path, required=True)
    verify_parser.add_argument("--record", type=Path, required=True)
    verify_parser.add_argument("--previous-record", type=Path, action="append", default=[])
    return parser


def _add_common_artifact_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--group-source-root", required=True)
    parser.add_argument("--split-assignment-path", required=True)
    parser.add_argument("--compiled-corpus-path", required=True)
    parser.add_argument("--annotation-guideline-path", required=True)
    parser.add_argument("--review-ledger-path", required=True)
    parser.add_argument("--contrast-manifest-path", required=True)
    parser.add_argument("--obligation-manifest-path", required=True)


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "schema":
        _write_text(args.output, serialize_freeze_record_schema())
        return 0
    if args.command == "check-schema":
        if not args.schema.is_file():
            raise SystemExit(f"freeze record schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_freeze_record_schema():
            raise SystemExit("freeze record schema differs from the code contract")
        return 0
    if args.command == "verify":
        verified = verify_freeze_record(
            repo_root=args.repo_root,
            record_path=args.record,
            previous_record_paths=tuple(args.previous_record),
        )
        print(verified.record.record_fingerprint)
        return 0

    paths = FreezeArtifactPathsV1(
        group_source_root=args.group_source_root,
        split_assignment_path=args.split_assignment_path,
        compiled_corpus_path=args.compiled_corpus_path,
        annotation_guideline_path=args.annotation_guideline_path,
        review_ledger_path=args.review_ledger_path,
        contrast_manifest_path=args.contrast_manifest_path,
        obligation_manifest_path=args.obligation_manifest_path,
    )
    record = create_freeze_record_file(
        repo_root=args.repo_root,
        output_path=args.output,
        freeze_id=args.freeze_id,
        freeze_revision=args.freeze_revision,
        previous_record_paths=tuple(args.previous_record),
        input_git_revision=args.input_git_revision,
        paths=paths,
    )
    print(record.record_fingerprint)
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
