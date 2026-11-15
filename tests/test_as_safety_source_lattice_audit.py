"""Keep reported exposed-development candidate coverage reproducible."""

from scripts.audit_as_safety_source_lattice import audit


def test_exposed_es_owner_coverage_is_candidate_availability_only():
    result = audit()
    assert result["kind"] == "as_safety_source_lattice_coverage_development_v1"
    assert result["denominator"] == 18
    assert (result["selected"], result["truncated"], result["not_generated"]) == (
        18,
        0,
        0,
    )
    assert all(row["selected_candidates"] == row["generated_candidates"] for row in result["rows"])
    assert len({(row["case_id"], row["event_index"]) for row in result["rows"]}) == 18
