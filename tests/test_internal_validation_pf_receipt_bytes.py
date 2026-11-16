"""The PF receipt must identify the bytes actually parsed for verification."""

import hashlib
import json

import pytest

from experiments.internal_validation_pf_sentinel_v1.verify import (
    _read_attested_journal,
    _read_attested_result,
)


def test_attested_bytes_survive_path_replacement(tmp_path):
    journal = tmp_path / "journal.jsonl"
    result = tmp_path / "result.json"
    original_journal = b'{"event":"header"}\n'
    original_result = json.dumps({"kind": "original"}).encode()
    journal.write_bytes(original_journal)
    result.write_bytes(original_result)

    rows, journal_sha256 = _read_attested_journal(journal)
    parsed, result_sha256 = _read_attested_result(result)
    journal.write_bytes(b'{"event":"replacement"}\n')
    result.write_bytes(json.dumps({"kind": "replacement"}).encode())

    assert rows == [{"event": "header"}]
    assert parsed == {"kind": "original"}
    assert journal_sha256 == hashlib.sha256(original_journal).hexdigest()
    assert result_sha256 == hashlib.sha256(original_result).hexdigest()
    assert journal_sha256 != hashlib.sha256(journal.read_bytes()).hexdigest()
    assert result_sha256 != hashlib.sha256(result.read_bytes()).hexdigest()


def test_attested_journal_rejects_partial_final_row(tmp_path):
    journal = tmp_path / "journal.jsonl"
    journal.write_bytes(b'{"event":"header"}')
    with pytest.raises(ValueError, match="incomplete line"):
        _read_attested_journal(journal)
