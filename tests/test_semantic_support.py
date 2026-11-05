"""Guard the exploratory meaning claims against silent label promotion or drift."""

import json

import pytest

from evals.structured_nlu.semantic_support import CLAIM_SOURCE, load_claims

pytestmark = pytest.mark.unit


def test_previously_reviewed_claim_directions_and_quote_boundaries():
    claims = load_claims()
    assert [claim["id"] for claim in claims] == [f"S{index:02}" for index in range(1, 7)]
    assert [claim["expected"] for claim in claims] == [
        "supported",
        "insufficient",
        "insufficient",
        "insufficient",
        "supported",
        "supported",
    ]
    for claim in claims:
        assert claim["quote"] in claim["utterance"]


def test_exploratory_provenance_cannot_be_promoted(tmp_path):
    source = json.loads(CLAIM_SOURCE.read_text())
    source["not_official_test"] = False
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="exploratory"):
        load_claims(path)


def test_unsupported_claim_cannot_disagree_with_prior_label(tmp_path):
    source = json.loads(CLAIM_SOURCE.read_text())
    source["claims"][0]["expected"] = "insufficient"
    path = tmp_path / "claims.json"
    path.write_text(json.dumps(source))
    with pytest.raises(ValueError, match="blank exploratory label"):
        load_claims(path)
