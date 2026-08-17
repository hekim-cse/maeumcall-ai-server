from datetime import UTC, datetime

import pytest

from scripts.migrate_baseline_json import load_source
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
