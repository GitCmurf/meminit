from __future__ import annotations

import re


def normalize_document_type_for_id(doc_type: str) -> str:
    """Normalize a document type for ID validation and generation."""

    normalized = str(doc_type).strip().upper()
    if normalized == "GOVERNANCE":
        return "GOV"
    return normalized


def document_id_type_segment(doc_type: str) -> str:
    """Return the document-ID type segment derived from *doc_type*."""

    doc_type_upper = normalize_document_type_for_id(doc_type)
    if doc_type_upper == "GOV":
        return "GOV"
    if 3 <= len(doc_type_upper) <= 10 and doc_type_upper.isalpha():
        return doc_type_upper
    segment = re.sub(r"[^A-Z]", "", doc_type_upper)[:10]
    return segment if len(segment) >= 3 else "DOC"
