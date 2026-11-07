"""Recover a partially published reviewed dataset without changing frozen bytes."""

from pathlib import Path

from scripts import materialize_nlu_safety_postfreeze_dataset as module


def test_missing_ledger_is_recreated_without_replacing_dataset(tmp_path: Path, monkeypatch) -> None:
    """An interrupted second write can be resumed from the reviewed input."""
    dataset = tmp_path / "dataset.json"
    ledger = tmp_path / "ledger.json"
    original_dataset = module.OUTPUT.read_bytes()
    dataset.write_bytes(original_dataset)
    monkeypatch.setattr(module, "OUTPUT", dataset)
    monkeypatch.setattr(module, "LEDGER", ledger)

    module.main()

    assert dataset.read_bytes() == original_dataset
    first_ledger = ledger.read_bytes()
    module.main()
    assert ledger.read_bytes() == first_ledger


def test_changed_existing_dataset_blocks_ledger_recovery(tmp_path: Path, monkeypatch) -> None:
    """Do not attach a review ledger to altered case bytes."""
    dataset = tmp_path / "dataset.json"
    dataset.write_bytes(module.OUTPUT.read_bytes() + b" ")
    ledger = tmp_path / "ledger.json"
    monkeypatch.setattr(module, "OUTPUT", dataset)
    monkeypatch.setattr(module, "LEDGER", ledger)

    import pytest

    with pytest.raises(ValueError, match="existing reviewed dataset differs"):
        module.main()
    assert not ledger.exists()
