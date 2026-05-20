import re
from dataclasses import dataclass
from datetime import date
from typing import Optional

import pytest

from meminit.core.domain.entities import (
    Document,
    Frontmatter,
    NewDocumentParams,
    Severity,
    Violation,
)


def test_frontmatter_creation():
    fm = Frontmatter(
        document_id="MEMINIT-ADR-001",
        type="ADR",
        title="Test ADR",
        status="Draft",
        version="0.1",
        last_updated=date(2025, 1, 1),
        docops_version="2.0",
        owner="Me",
    )
    assert fm.document_id == "MEMINIT-ADR-001"
    assert fm.status == "Draft"
    # Test optional field default
    assert fm.area is None


def test_document_creation():
    fm = Frontmatter(
        document_id="MEMINIT-ADR-001",
        type="ADR",
        title="Test ADR",
        status="Draft",
        version="0.1",
        last_updated=date(2025, 1, 1),
        docops_version="2.0",
        owner="Me",
    )
    doc = Document(path="docs/45-adr/adr-001.md", frontmatter=fm, body="# Test\n\nContent.")
    assert doc.path == "docs/45-adr/adr-001.md"
    assert doc.frontmatter.document_id == "MEMINIT-ADR-001"


def test_violation_creation():
    v = Violation(
        file="docs/bad.md", line=1, rule="ID_REGEX", message="Bad ID", severity=Severity.ERROR
    )
    assert v.severity == Severity.ERROR
    assert v.line == 1


def test_violation_accepts_string_severity():
    """String severity is coerced to Severity enum via __post_init__."""
    v = Violation(file="docs/bad.md", line=1, rule="ID_REGEX", message="Bad ID", severity="error")
    assert v.severity == Severity.ERROR
    assert isinstance(v.severity, Severity)


def test_violation_rejects_invalid_severity():
    """Invalid severity string raises ValueError."""
    with pytest.raises(ValueError, match="Invalid severity"):
        Violation(file="x", line=1, rule="R", message="m", severity="info")


def test_violation_rejects_invalid_type():
    """Non-string, non-Severity type raises ValueError."""
    with pytest.raises(ValueError, match="severity"):
        Violation(file="x", line=1, rule="R", message="m", severity=123)


class TestNewDocumentParamsValidation:
    def test_valid_defaults(self):
        """Default Draft status and no related IDs should pass validation."""
        params = NewDocumentParams(doc_type="ADR", title="Test")
        assert params.status == "Draft"

    def test_valid_status(self):
        """All valid statuses should be accepted."""
        for status in ("Draft", "In Review", "Approved", "Superseded"):
            params = NewDocumentParams(doc_type="ADR", title="Test", status=status)
            assert params.status == status

    def test_rejects_invalid_status_at_construction(self):
        """Invalid status raises ValueError at construction time."""
        with pytest.raises(ValueError, match="Invalid status"):
            NewDocumentParams(doc_type="ADR", title="Test", status="Published")

    def test_valid_related_ids(self):
        """Valid related_ids pass validation."""
        params = NewDocumentParams(
            doc_type="ADR",
            title="Test",
            related_ids=["MEMINIT-ADR-001", "MEMINIT-RFC-042"],
        )
        assert params.related_ids == ["MEMINIT-ADR-001", "MEMINIT-RFC-042"]

    def test_valid_superseded_by(self):
        """Valid superseded_by passes validation."""
        params = NewDocumentParams(doc_type="ADR", title="Test", superseded_by="MEMINIT-ADR-099")
        assert params.superseded_by == "MEMINIT-ADR-099"
