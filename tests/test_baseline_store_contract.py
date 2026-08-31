import asyncio
from datetime import UTC, datetime
from typing import Any

import pytest

from scripts.migrate_baseline_json import build_parser, load_source, migrate
from services.baseline_store import (
    BaselineIdentityError,
    BaselineMeasurementError,
    calculate_welford,
    validate_imported_baseline,
    validate_pseudonymous_key,
)

pytestmark = pytest.mark.unit


def test_welford_calculation_preserves_count_mean_and_sample_std():
    first = calculate_welford(
        None,
        (100.0, 0.01, 0.02),
        measured_at=datetime(2026, 8, 17, tzinfo=UTC),
    )
    second = calculate_welford(
        first,
        (120.0, 0.03, 0.04),
        measured_at=datetime(2026, 8, 17, tzinfo=UTC),
    )

    assert second["samples"] == 2
    assert second["pitchHz"] == 110.0
    assert second["pitchStdHz"] == pytest.approx(14.142136)
    assert second["jitterLocal"] == 0.02
    assert second["shimmerLocal"] == 0.03


def test_json_import_accepts_only_complete_meaningful_baselines():
    value = validate_imported_baseline(
        {
            "samples": 3,
            "pitchHz": 150,
            "jitterLocal": 0.005,
            "shimmerLocal": 0.01,
        }
    )
    assert value["samples"] == 3

    with pytest.raises(BaselineMeasurementError):
        validate_imported_baseline(
            {
                "samples": 0,
                "pitchHz": 150,
                "jitterLocal": 0.005,
                "shimmerLocal": 0.01,
            }
        )


def test_json_import_rejects_plain_identifiers():
    with pytest.raises(BaselineIdentityError):
        validate_pseudonymous_key("real-user-id")

    key = "user_hmac_sha256:" + "a" * 64
    assert validate_pseudonymous_key(key) == key


def test_json_migration_loads_only_valid_pseudonymous_records(tmp_path):
    key = "user_hmac_sha256:" + "b" * 64
    source = tmp_path / "baseline_db.json"
    source.write_text(
        f'{{"{key}":{{"samples":3,"pitchHz":150,"jitterLocal":0.005,"shimmerLocal":0.01}}}}',
        encoding="utf-8",
    )

    loaded = load_source(source)

    assert loaded[key]["pitchHz"] == 150.0


class BatchImportRepositoryDouble:
    def __init__(self) -> None:
        self.imported: dict[str, dict[str, Any]] | None = None

    async def import_baselines(self, baselines):
        self.imported = {key: dict(value) for key, value in baselines.items()}
        return len(baselines)


def test_json_migration_is_dry_run_by_default(tmp_path):
    key = "user_hmac_sha256:" + "c" * 64
    source = tmp_path / "baseline_db.json"
    source.write_text(
        f'{{"{key}":{{"samples":3,"pitchHz":150,"jitterLocal":0.005,"shimmerLocal":0.01}}}}',
        encoding="utf-8",
    )
    repository = BatchImportRepositoryDouble()

    result = asyncio.run(migrate(source, apply=False, repository=repository))

    assert result.validated_count == 1
    assert result.applied_count == 0
    assert repository.imported is None


def test_json_migration_applies_all_records_as_one_repository_operation(tmp_path):
    first_key = "user_hmac_sha256:" + "d" * 64
    second_key = "user_hmac_sha256:" + "e" * 64
    source = tmp_path / "baseline_db.json"
    source.write_text(
        "{"
        f'"{first_key}":{{"samples":3,"pitchHz":150,"jitterLocal":0.005,"shimmerLocal":0.01}},'
        f'"{second_key}":{{"samples":4,"pitchHz":160,"jitterLocal":0.006,"shimmerLocal":0.02}}'
        "}",
        encoding="utf-8",
    )
    repository = BatchImportRepositoryDouble()

    result = asyncio.run(migrate(source, apply=True, repository=repository))

    assert result.validated_count == 2
    assert result.applied_count == 2
    assert repository.imported is not None
    assert set(repository.imported) == {first_key, second_key}


def test_json_migration_cli_requires_explicit_apply_flag():
    parser = build_parser()

    assert parser.parse_args(["baseline_db.json"]).apply is False
    assert parser.parse_args(["baseline_db.json", "--apply"]).apply is True


@pytest.mark.parametrize(
    "contents",
    [
        "[]",
        "{not-json}",
        '{"real-user-id":{"samples":3,"pitchHz":150,"jitterLocal":0.005,"shimmerLocal":0.01}}',
    ],
)
def test_json_migration_rejects_invalid_documents(tmp_path, contents):
    source = tmp_path / "baseline_db.json"
    source.write_text(contents, encoding="utf-8")

    with pytest.raises((ValueError, BaselineIdentityError)):
        load_source(source)
