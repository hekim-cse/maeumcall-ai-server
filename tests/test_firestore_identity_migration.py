from __future__ import annotations

import json

import pytest

from scripts.migrate_firestore_user_documents import (
    classify_documents,
    load_targets,
)


pytestmark = pytest.mark.unit

SECRET = "authentication-test-secret-32-bytes-minimum"


def test_manifest_requires_explicit_unique_subjects(tmp_path):
    manifest = tmp_path / "targets.json"
    manifest.write_text(
        json.dumps({"kakao_subjects": ["123456789", "123456789"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="중복"):
        load_targets(manifest, secret=SECRET)


def test_manifest_creates_pseudonymous_destination_and_safe_audit_id(tmp_path):
    manifest = tmp_path / "targets.json"
    manifest.write_text(
        json.dumps({"kakao_subjects": ["123456789"]}), encoding="utf-8"
    )

    target = load_targets(manifest, secret=SECRET)[0]

    assert target.destination_uid.startswith("user_")
    assert "123456789" not in target.destination_uid
    assert target.audit_fingerprint != "123456789"
    assert len(target.audit_fingerprint) == 12


@pytest.mark.parametrize(
    ("source", "destination", "expected"),
    [
        (None, None, "SOURCE_NOT_FOUND"),
        ({"nickname": "마음"}, None, "READY"),
        ({"nickname": "마음"}, {"nickname": "마음"}, "ALREADY_COPIED"),
        ({"nickname": "마음"}, {"nickname": "다름"}, "DESTINATION_CONFLICT"),
    ],
)
def test_migration_never_overwrites_conflicting_destination(
    source, destination, expected
):
    assert classify_documents(source, destination) == expected
