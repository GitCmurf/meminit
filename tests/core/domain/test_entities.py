from dataclasses import dataclass
from datetime import date
from typing import Optional

import pytest

from meminit.core.domain.entities import Document, Frontmatter, Violation


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
    v = Violation(file="docs/bad.md", line=1, rule="ID_REGEX", message="Bad ID", severity="error")
    assert v.severity == "error"
    assert v.line == 1
