from pathlib import Path

import pytest

from scripts import validate_nlu_review_draft

pytestmark = pytest.mark.unit


def test_label_loader_rejects_unquoted_field_assignment(tmp_path: Path, monkeypatch):
    original = validate_nlu_review_draft.LABELS.read_text()
    changed = original.replace("`product_type=태블릿`;", "product_type=태블릿;", 1)
    assert changed != original
    labels = tmp_path / "labels.md"
    labels.write_text(changed)
    monkeypatch.setattr(validate_nlu_review_draft, "LABELS", labels)

    with pytest.raises(ValueError, match="invalid label field text in H01"):
        validate_nlu_review_draft.load_draft_cases()
