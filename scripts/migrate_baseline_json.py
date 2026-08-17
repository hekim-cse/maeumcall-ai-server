from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from services.baseline_store import (
    get_baseline_repository,
    validate_imported_baseline,
    validate_pseudonymous_key,
)


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


async def migrate(path: Path) -> int:
    baselines = load_source(path)
    repository = get_baseline_repository()
    for user_key, baseline in baselines.items():
        await repository.import_baseline(user_key, baseline)
    return len(baselines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="HMAC 가명화된 JSON 음성 기준선을 PostgreSQL로 이관합니다."
    )
    parser.add_argument("source", type=Path, help="기존 baseline_db.json 경로")
    args = parser.parse_args()
    migrated = asyncio.run(migrate(args.source.resolve()))
    print(f"{migrated}개의 음성 기준선을 PostgreSQL로 이관했습니다.")


if __name__ == "__main__":
    main()
