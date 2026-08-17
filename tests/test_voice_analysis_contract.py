from __future__ import annotations

import math

import pytest

from praat_voice_analysis import VoiceAnalysisError, _require_measurement
from services.analysis_service import build_payload
from services.baseline_store import BaselineMeasurementError, pct, z

pytestmark = pytest.mark.unit


def _analysis() -> dict:
    return {
        "pitch": {"mean": 150.0, "comment": "음높이"},
        "jitter": {"value": 0.005, "comment": "주파수 변동"},
        "shimmer": {"value": 0.01, "comment": "진폭 변동"},
    }


def _baseline() -> dict:
    return {
        "pitchHz": 140.0,
        "pitchStdHz": 10.0,
        "jitterLocal": 0.004,
        "jitterStd": 0.001,
        "shimmerLocal": 0.008,
        "shimmerStd": 0.002,
        "samples": 3,
        "ts": 1,
    }


def test_non_finite_praat_measurement_is_not_replaced_with_zero():
    with pytest.raises(VoiceAnalysisError) as exc_info:
        _require_measurement(math.nan, name="음높이", positive=True)

    assert exc_info.value.code == "VOICE_MEASUREMENT_UNAVAILABLE"


def test_incomplete_baseline_is_rejected_instead_of_filling_missing_values():
    baseline = _baseline()
    baseline.pop("jitterStd")

    with pytest.raises(BaselineMeasurementError):
        build_payload(_analysis(), baseline)


def test_zero_variance_omits_undefined_z_score():
    baseline = _baseline()
    baseline["pitchStdHz"] = 0.0

    payload = build_payload(_analysis(), baseline)

    assert "z" not in payload
    assert "deltaPct" in payload


def test_zero_baseline_omits_undefined_percentage_delta():
    baseline = _baseline()
    baseline["jitterLocal"] = 0.0

    payload = build_payload(_analysis(), baseline)

    assert "deltaPct" not in payload
    assert "z" in payload


def test_undefined_derived_statistics_raise_contract_errors():
    with pytest.raises(BaselineMeasurementError):
        pct(1.0, 0.0)
    with pytest.raises(BaselineMeasurementError):
        z(1.0, 1.0, 0.0)
