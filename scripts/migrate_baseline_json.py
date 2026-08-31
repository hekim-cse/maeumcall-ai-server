from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.baseline_store import (
    BaselineRepository,
    get_baseline_repository,
    validate_imported_baseline,
    validate_pseudonymous_key,
)


@dataclass(frozen=True)
class MigrationResult:
    validated_count: int
    applied_count: int


def load_source(path: Path) -> dict[str, dict[str, Any]]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"기준선 JSON을 읽을 수 없습니다: {path}") from exc
    if not isinstance(decoded, dict):
        raise ValueError("기준선 JSON의 최상위 값은 객체여야 합니다.")
    validated: dict[str, dict[str, Any]] = {}
    for user_key, baseline in decoded.items():
        if not isinstance(user_key, str) or not isinstance(baseline, dict):
            raise ValueError("기준선 JSON 항목의 키와 값 형식이 올바르지 않습니다.")
        validated[validate_pseudonymous_key(user_key)] = validate_imported_baseline(baseline)
    return validated


async def migrate(
    path: Path,
    *,
    apply: bool,
    repository: BaselineRepository | None = None,
) -> MigrationResult:
    baselines = load_source(path)
    if not apply:
        return MigrationResult(validated_count=len(baselines), applied_count=0)

    target = repository or get_baseline_repository()
    applied_count = await target.import_baselines(baselines)
    return MigrationResult(
        validated_count=len(baselines),
        applied_count=applied_count,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="HMAC 가명화된 JSON 음성 기준선을 PostgreSQL로 이관합니다."
    )
    parser.add_argument("source", type=Path, help="기존 baseline_db.json 경로")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="검증을 통과한 전체 기준선을 단일 트랜잭션으로 저장합니다.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = asyncio.run(migrate(args.source.resolve(), apply=args.apply))
    if args.apply:
        print(
            f"검증한 {result.validated_count}개 중 {result.applied_count}개의 "
            "음성 기준선을 단일 트랜잭션으로 이관했습니다."
        )
        return
    print(
        f"dry-run 완료: {result.validated_count}개의 음성 기준선을 검증했고 "
        "데이터베이스는 변경하지 않았습니다. 실제 이관에는 --apply를 지정하세요."
    )


if __name__ == "__main__":
    main()
