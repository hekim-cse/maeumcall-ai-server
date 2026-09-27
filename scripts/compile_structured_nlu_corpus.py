from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path

from evals.structured_nlu.ai_origin_policy import (
    serialize_ai_origin_policy_schema_v3,
    serialize_ai_origin_policy_v1,
    serialize_ai_origin_policy_v2,
    serialize_ai_origin_policy_v3,
)
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
from evals.structured_nlu.coverage_progress import (
    build_development_coverage_progress,
    serialize_development_coverage_progress,
)
from evals.structured_nlu.drafting import (
    AI_COVERAGE_V1_MANIFEST_SHA256,
    build_ai_coverage_candidate_manifest_v1,
    build_ai_coverage_candidate_manifest_v2,
    coverage_candidate_diagnostic_cases,
    render_ai_coverage_candidate_review_packet_v1,
    render_ai_coverage_candidate_review_packet_v2,
    render_ai_draft_human_review_packet_v1,
    render_ai_subagent_human_review_packet_v1,
    serialize_ai_coverage_candidate_manifest_v1,
    serialize_ai_coverage_candidate_manifest_v2,
    serialize_ai_coverage_candidate_schema_v1,
    serialize_ai_coverage_candidate_schema_v2,
    serialize_ai_draft_seed_manifest_v1,
    serialize_ai_draft_seed_schema_v1,
    serialize_ai_subagent_candidate_manifest_v1,
    serialize_ai_subagent_candidate_schema_v1,
)
from evals.structured_nlu.obligations import serialize_official_authoring_obligations
from evals.structured_nlu.review import (
    read_regular_artifact,
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

    coverage_progress_parser = subparsers.add_parser(
        "coverage-progress",
        help="Write an explicitly unqualified development coverage diagnostic.",
    )
    coverage_progress_parser.add_argument("source_dir", type=Path)
    coverage_progress_parser.add_argument("split_assignments", type=Path)
    coverage_progress_parser.add_argument("output", type=Path)

    check_coverage_progress_parser = subparsers.add_parser(
        "check-coverage-progress",
        help="Verify the committed development coverage diagnostic against the sources.",
    )
    check_coverage_progress_parser.add_argument("source_dir", type=Path)
    check_coverage_progress_parser.add_argument("split_assignments", type=Path)
    check_coverage_progress_parser.add_argument("report", type=Path)

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

    draft_seed_parser = subparsers.add_parser(
        "draft-seeds",
        help="Write one unreviewed AI-assisted seed suggestion for every NLU scenario.",
    )
    draft_seed_parser.add_argument("output", type=Path)

    check_draft_seed_parser = subparsers.add_parser(
        "check-draft-seeds",
        help="Verify that committed AI-assisted seed suggestions match the live contract.",
    )
    check_draft_seed_parser.add_argument("manifest", type=Path)

    draft_schema_parser = subparsers.add_parser(
        "draft-schema",
        help="Write the editor-facing AI draft seed JSON Schema.",
    )
    draft_schema_parser.add_argument("output", type=Path)

    check_draft_schema_parser = subparsers.add_parser(
        "check-draft-schema",
        help="Verify that the committed AI draft seed schema matches the code contract.",
    )
    check_draft_schema_parser.add_argument("schema", type=Path)

    draft_review_packet_parser = subparsers.add_parser(
        "draft-review-packet",
        help="Write the human authoring worksheet for all AI draft seed suggestions.",
    )
    draft_review_packet_parser.add_argument("output", type=Path)

    check_draft_review_packet_parser = subparsers.add_parser(
        "check-draft-review-packet",
        help="Verify that the committed human worksheet matches all AI draft seeds.",
    )
    check_draft_review_packet_parser.add_argument("packet", type=Path)

    subagent_candidate_parser = subparsers.add_parser(
        "draft-subagent-candidates",
        help="Write one unreviewed subagent alternative for every NLU scenario.",
    )
    subagent_candidate_parser.add_argument("output", type=Path)

    check_subagent_candidate_parser = subparsers.add_parser(
        "check-draft-subagent-candidates",
        help="Verify committed subagent alternatives against the live contract.",
    )
    check_subagent_candidate_parser.add_argument("manifest", type=Path)

    subagent_schema_parser = subparsers.add_parser(
        "draft-subagent-schema",
        help="Write the editor-facing subagent candidate JSON Schema.",
    )
    subagent_schema_parser.add_argument("output", type=Path)

    check_subagent_schema_parser = subparsers.add_parser(
        "check-draft-subagent-schema",
        help="Verify the committed subagent candidate JSON Schema.",
    )
    check_subagent_schema_parser.add_argument("schema", type=Path)

    subagent_review_packet_parser = subparsers.add_parser(
        "draft-subagent-review-packet",
        help="Write the human worksheet for all subagent candidate suggestions.",
    )
    subagent_review_packet_parser.add_argument("output", type=Path)

    check_subagent_review_packet_parser = subparsers.add_parser(
        "check-draft-subagent-review-packet",
        help="Verify the committed subagent worksheet against the candidates.",
    )
    check_subagent_review_packet_parser.add_argument("packet", type=Path)

    coverage_candidate_parser = subparsers.add_parser(
        "draft-coverage-candidates",
        help="Write 24 unreviewed AI proposals for exact development coverage gaps.",
    )
    coverage_candidate_parser.add_argument("output", type=Path)

    check_coverage_candidate_parser = subparsers.add_parser(
        "check-draft-coverage-candidates",
        help="Verify committed coverage-gap candidates against the V1 policy.",
    )
    check_coverage_candidate_parser.add_argument("manifest", type=Path)

    coverage_candidate_schema_parser = subparsers.add_parser(
        "draft-coverage-schema",
        help="Write the editor-facing coverage candidate JSON Schema.",
    )
    coverage_candidate_schema_parser.add_argument("output", type=Path)

    check_coverage_candidate_schema_parser = subparsers.add_parser(
        "check-draft-coverage-schema",
        help="Verify the committed coverage candidate JSON Schema.",
    )
    check_coverage_candidate_schema_parser.add_argument("schema", type=Path)

    coverage_candidate_review_parser = subparsers.add_parser(
        "draft-coverage-review-packet",
        help="Write the approve/edit/reject worksheet for coverage candidates.",
    )
    coverage_candidate_review_parser.add_argument("output", type=Path)

    check_coverage_candidate_review_parser = subparsers.add_parser(
        "check-draft-coverage-review-packet",
        help="Verify the committed coverage candidate review worksheet.",
    )
    check_coverage_candidate_review_parser.add_argument("packet", type=Path)

    coverage_candidate_v2_parser = subparsers.add_parser(
        "draft-coverage-candidates-v2",
        help="Write the second unreviewed AI coverage-gap candidate batch.",
    )
    coverage_candidate_v2_parser.add_argument("output", type=Path)

    check_coverage_candidate_v2_parser = subparsers.add_parser(
        "check-draft-coverage-candidates-v2",
        help="Verify the committed second coverage-gap candidate batch.",
    )
    check_coverage_candidate_v2_parser.add_argument("source_dir", type=Path)
    check_coverage_candidate_v2_parser.add_argument("split_assignments", type=Path)
    check_coverage_candidate_v2_parser.add_argument("predecessor_manifest", type=Path)
    check_coverage_candidate_v2_parser.add_argument("manifest", type=Path)

    coverage_candidate_schema_v2_parser = subparsers.add_parser(
        "draft-coverage-schema-v2",
        help="Write the editor-facing second coverage candidate JSON Schema.",
    )
    coverage_candidate_schema_v2_parser.add_argument("output", type=Path)

    check_coverage_candidate_schema_v2_parser = subparsers.add_parser(
        "check-draft-coverage-schema-v2",
        help="Verify the committed second coverage candidate JSON Schema.",
    )
    check_coverage_candidate_schema_v2_parser.add_argument("schema", type=Path)

    coverage_candidate_review_v2_parser = subparsers.add_parser(
        "draft-coverage-review-packet-v2",
        help="Write the approve/edit/reject worksheet for the second candidate batch.",
    )
    coverage_candidate_review_v2_parser.add_argument("output", type=Path)

    check_coverage_candidate_review_v2_parser = subparsers.add_parser(
        "check-draft-coverage-review-packet-v2",
        help="Verify the committed second coverage candidate review worksheet.",
    )
    check_coverage_candidate_review_v2_parser.add_argument("packet", type=Path)

    ai_origin_policy_parser = subparsers.add_parser(
        "ai-origin-policy",
        help="Write the immutable NFC fingerprint registry for all V1 AI-origin text.",
    )
    ai_origin_policy_parser.add_argument("output", type=Path)

    check_ai_origin_policy_parser = subparsers.add_parser(
        "check-ai-origin-policy",
        help="Verify the committed V1 AI-origin policy registry.",
    )
    check_ai_origin_policy_parser.add_argument("manifest", type=Path)

    ai_origin_policy_v2_parser = subparsers.add_parser(
        "ai-origin-policy-v2",
        help="Write the additive V2 NFC registry including coverage candidates.",
    )
    ai_origin_policy_v2_parser.add_argument("output", type=Path)

    check_ai_origin_policy_v2_parser = subparsers.add_parser(
        "check-ai-origin-policy-v2",
        help="Verify the committed additive V2 AI-origin registry.",
    )
    check_ai_origin_policy_v2_parser.add_argument("manifest", type=Path)

    ai_origin_policy_v3_parser = subparsers.add_parser(
        "ai-origin-policy-v3",
        help="Write the additive V3 NFC registry including both coverage batches.",
    )
    ai_origin_policy_v3_parser.add_argument("output", type=Path)

    check_ai_origin_policy_v3_parser = subparsers.add_parser(
        "check-ai-origin-policy-v3",
        help="Verify the committed additive V3 AI-origin registry.",
    )
    check_ai_origin_policy_v3_parser.add_argument("manifest", type=Path)

    ai_origin_policy_schema_v3_parser = subparsers.add_parser(
        "ai-origin-policy-schema-v3",
        help="Write the editor-facing additive V3 AI-origin policy JSON Schema.",
    )
    ai_origin_policy_schema_v3_parser.add_argument("output", type=Path)

    check_ai_origin_policy_schema_v3_parser = subparsers.add_parser(
        "check-ai-origin-policy-schema-v3",
        help="Verify the committed additive V3 AI-origin policy JSON Schema.",
    )
    check_ai_origin_policy_schema_v3_parser.add_argument("schema", type=Path)
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
    if args.command == "coverage-progress":
        ensure_output_outside_source(args.source_dir, args.output)
        ensure_output_does_not_replace_manifest(args.split_assignments, args.output)
        dataset = compile_authoring_directory(args.source_dir, args.split_assignments)
        _write_text(args.output, serialize_development_coverage_progress(dataset))
        return 0
    if args.command == "check-coverage-progress":
        ensure_output_outside_source(args.source_dir, args.report)
        ensure_output_does_not_replace_manifest(args.split_assignments, args.report)
        if not args.report.is_file():
            raise SystemExit(f"development coverage report does not exist: {args.report}")
        dataset = compile_authoring_directory(args.source_dir, args.split_assignments)
        expected = serialize_development_coverage_progress(dataset)
        if args.report.read_text(encoding="utf-8") != expected:
            raise SystemExit("development coverage report differs from the authoring sources")
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
    if args.command == "draft-seeds":
        _write_text(args.output, serialize_ai_draft_seed_manifest_v1())
        return 0
    if args.command == "check-draft-seeds":
        if not args.manifest.is_file():
            raise SystemExit(f"AI draft seed manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != serialize_ai_draft_seed_manifest_v1():
            raise SystemExit("AI draft seed manifest differs from the live contract")
        return 0
    if args.command == "draft-schema":
        _write_text(args.output, serialize_ai_draft_seed_schema_v1())
        return 0
    if args.command == "check-draft-schema":
        if not args.schema.is_file():
            raise SystemExit(f"AI draft seed schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_ai_draft_seed_schema_v1():
            raise SystemExit("AI draft seed schema differs from the code contract")
        return 0
    if args.command == "draft-review-packet":
        _write_text(args.output, render_ai_draft_human_review_packet_v1())
        return 0
    if args.command == "check-draft-review-packet":
        if not args.packet.is_file():
            raise SystemExit(f"AI draft human review packet does not exist: {args.packet}")
        if args.packet.read_text(encoding="utf-8") != render_ai_draft_human_review_packet_v1():
            raise SystemExit("AI draft human review packet differs from the draft seeds")
        return 0
    if args.command == "draft-subagent-candidates":
        _write_text(args.output, serialize_ai_subagent_candidate_manifest_v1())
        return 0
    if args.command == "check-draft-subagent-candidates":
        if not args.manifest.is_file():
            raise SystemExit(f"AI subagent candidate manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != (
            serialize_ai_subagent_candidate_manifest_v1()
        ):
            raise SystemExit("AI subagent candidate manifest differs from the live contract")
        return 0
    if args.command == "draft-subagent-schema":
        _write_text(args.output, serialize_ai_subagent_candidate_schema_v1())
        return 0
    if args.command == "check-draft-subagent-schema":
        if not args.schema.is_file():
            raise SystemExit(f"AI subagent candidate schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != (serialize_ai_subagent_candidate_schema_v1()):
            raise SystemExit("AI subagent candidate schema differs from the code contract")
        return 0
    if args.command == "draft-subagent-review-packet":
        _write_text(args.output, render_ai_subagent_human_review_packet_v1())
        return 0
    if args.command == "check-draft-subagent-review-packet":
        if not args.packet.is_file():
            raise SystemExit(f"AI subagent review packet does not exist: {args.packet}")
        if args.packet.read_text(encoding="utf-8") != (render_ai_subagent_human_review_packet_v1()):
            raise SystemExit("AI subagent review packet differs from the candidates")
        return 0
    if args.command == "draft-coverage-candidates":
        _write_text(args.output, serialize_ai_coverage_candidate_manifest_v1())
        return 0
    if args.command == "check-draft-coverage-candidates":
        if not args.manifest.is_file():
            raise SystemExit(f"AI coverage candidate manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != (
            serialize_ai_coverage_candidate_manifest_v1()
        ):
            raise SystemExit("AI coverage candidate manifest differs from the V1 policy")
        return 0
    if args.command == "draft-coverage-schema":
        _write_text(args.output, serialize_ai_coverage_candidate_schema_v1())
        return 0
    if args.command == "check-draft-coverage-schema":
        if not args.schema.is_file():
            raise SystemExit(f"AI coverage candidate schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != (serialize_ai_coverage_candidate_schema_v1()):
            raise SystemExit("AI coverage candidate schema differs from the code contract")
        return 0
    if args.command == "draft-coverage-review-packet":
        _write_text(args.output, render_ai_coverage_candidate_review_packet_v1())
        return 0
    if args.command == "check-draft-coverage-review-packet":
        if not args.packet.is_file():
            raise SystemExit(f"AI coverage review packet does not exist: {args.packet}")
        if args.packet.read_text(encoding="utf-8") != (
            render_ai_coverage_candidate_review_packet_v1()
        ):
            raise SystemExit("AI coverage review packet differs from the candidates")
        return 0
    if args.command == "draft-coverage-candidates-v2":
        _write_new_text(args.output, serialize_ai_coverage_candidate_manifest_v2())
        return 0
    if args.command == "check-draft-coverage-candidates-v2":
        _verify_coverage_candidate_v2_chain(
            source_dir=args.source_dir,
            split_assignments=args.split_assignments,
            predecessor_manifest=args.predecessor_manifest,
            manifest=args.manifest,
        )
        return 0
    if args.command == "draft-coverage-schema-v2":
        _write_new_text(args.output, serialize_ai_coverage_candidate_schema_v2())
        return 0
    if args.command == "check-draft-coverage-schema-v2":
        if not args.schema.is_file():
            raise SystemExit(f"AI coverage V2 schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_ai_coverage_candidate_schema_v2():
            raise SystemExit("AI coverage candidate V2 schema differs from the code contract")
        return 0
    if args.command == "draft-coverage-review-packet-v2":
        _write_new_text(args.output, render_ai_coverage_candidate_review_packet_v2())
        return 0
    if args.command == "check-draft-coverage-review-packet-v2":
        if not args.packet.is_file():
            raise SystemExit(f"AI coverage V2 review packet does not exist: {args.packet}")
        if args.packet.read_text(encoding="utf-8") != (
            render_ai_coverage_candidate_review_packet_v2()
        ):
            raise SystemExit("AI coverage V2 review packet differs from the candidates")
        return 0
    if args.command == "ai-origin-policy":
        _write_text(args.output, serialize_ai_origin_policy_v1())
        return 0
    if args.command == "check-ai-origin-policy":
        if not args.manifest.is_file():
            raise SystemExit(f"AI-origin policy manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != serialize_ai_origin_policy_v1():
            raise SystemExit("AI-origin policy manifest differs from immutable V1")
        return 0
    if args.command == "ai-origin-policy-v2":
        _write_text(args.output, serialize_ai_origin_policy_v2())
        return 0
    if args.command == "check-ai-origin-policy-v2":
        if not args.manifest.is_file():
            raise SystemExit(f"AI-origin policy V2 manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != serialize_ai_origin_policy_v2():
            raise SystemExit("AI-origin policy manifest differs from immutable V2")
        return 0
    if args.command == "ai-origin-policy-v3":
        _write_new_text(args.output, serialize_ai_origin_policy_v3())
        return 0
    if args.command == "check-ai-origin-policy-v3":
        if not args.manifest.is_file():
            raise SystemExit(f"AI-origin policy V3 manifest does not exist: {args.manifest}")
        if args.manifest.read_text(encoding="utf-8") != serialize_ai_origin_policy_v3():
            raise SystemExit("AI-origin policy manifest differs from immutable V3")
        return 0
    if args.command == "ai-origin-policy-schema-v3":
        _write_new_text(args.output, serialize_ai_origin_policy_schema_v3())
        return 0
    if args.command == "check-ai-origin-policy-schema-v3":
        if not args.schema.is_file():
            raise SystemExit(f"AI-origin policy V3 schema does not exist: {args.schema}")
        if args.schema.read_text(encoding="utf-8") != serialize_ai_origin_policy_schema_v3():
            raise SystemExit("AI-origin policy V3 schema differs from the code contract")
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


def _verify_coverage_candidate_v2_chain(
    *,
    source_dir: Path,
    split_assignments: Path,
    predecessor_manifest: Path,
    manifest: Path,
) -> None:
    predecessor_bytes = read_regular_artifact(
        predecessor_manifest,
        label="AI coverage V1 predecessor manifest",
    )
    if hashlib.sha256(predecessor_bytes).hexdigest() != AI_COVERAGE_V1_MANIFEST_SHA256:
        raise SystemExit("AI coverage V1 predecessor manifest fingerprint differs")
    if predecessor_bytes.decode("utf-8") != serialize_ai_coverage_candidate_manifest_v1():
        raise SystemExit("AI coverage V1 predecessor manifest differs from the immutable policy")

    manifest_bytes = read_regular_artifact(manifest, label="AI coverage V2 manifest")
    if manifest_bytes.decode("utf-8") != serialize_ai_coverage_candidate_manifest_v2():
        raise SystemExit("AI coverage candidate manifest differs from the V2 policy")

    dataset = compile_authoring_directory(source_dir, split_assignments)
    v1 = build_ai_coverage_candidate_manifest_v1()
    v2 = build_ai_coverage_candidate_manifest_v2()
    baseline = build_development_coverage_progress(
        dataset,
        diagnostic_cases=coverage_candidate_diagnostic_cases(v1),
    )
    projected = build_development_coverage_progress(
        dataset,
        diagnostic_cases=coverage_candidate_diagnostic_cases(v1, v2),
    )
    if (
        baseline.corpus_fingerprint != v2.baseline_corpus_fingerprint
        or baseline.covered_obligation_count != v2.baseline_covered_obligation_count
        or baseline.missing_obligation_count != v2.baseline_missing_obligation_count
    ):
        raise SystemExit("AI coverage V2 baseline differs from source plus V1 diagnostics")
    if (
        projected.covered_obligation_count != v2.projected_covered_obligation_count
        or projected.missing_obligation_count != v2.projected_missing_obligation_count
        or projected.covered_obligation_count - baseline.covered_obligation_count
        != v2.projected_marginal_gain
    ):
        raise SystemExit("AI coverage V2 projection differs from the declared gain")


def _write_new_text(path: Path, content: str) -> None:
    """Create a new versioned artifact and refuse every overwrite or symlink alias."""
    resolved_parent = path.parent.resolve(strict=False)
    current = path.parent
    while current != current.parent:
        if current.is_symlink():
            raise SystemExit(f"versioned artifact output must not contain symlinks: {path}")
        current = current.parent
    resolved_parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise SystemExit(f"versioned artifact output already exists: {path}")
    try:
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise SystemExit(f"versioned artifact output already exists: {path}") from exc


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
