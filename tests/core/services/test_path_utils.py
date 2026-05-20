from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from meminit.core.services.path_utils import (
    is_safe_cli_output_path,
    load_index_documents,
)


def test_is_safe_cli_output_path_rejects_forbidden_system_paths():
    assert not is_safe_cli_output_path(Path("/etc/meminit-output.json"))


def test_is_safe_cli_output_path_allows_regular_relative_paths():
    assert is_safe_cli_output_path(Path("out/meminit-output.json"))


class TestLoadIndexDocuments:
    """Tests for load_index_documents (Finding #7)."""

    def test_happy_path_nodes_list(self, tmp_path):
        """Valid 'nodes' list returns documents."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {"nodes": [{"id": "doc1"}]}}))
        result = load_index_documents(idx)
        assert result == [{"id": "doc1"}]

    def test_happy_path_documents_under_data(self, tmp_path):
        """Valid 'documents' list under data returns documents."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {"documents": [{"id": "doc1"}]}}))
        result = load_index_documents(idx)
        assert result == [{"id": "doc1"}]

    def test_happy_path_top_level_documents(self, tmp_path):
        """Valid top-level 'documents' list returns documents."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"documents": [{"id": "doc1"}]}))
        result = load_index_documents(idx)
        assert result == [{"id": "doc1"}]

    def test_missing_payload_returns_empty_list(self, tmp_path):
        """No nodes/documents keys returns empty list (correct)."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {"other": "stuff"}}))
        with pytest.raises(ValueError, match="Malformed"):
            load_index_documents(idx)

    def test_empty_envelope_returns_empty_list(self, tmp_path):
        """Empty data dict returns empty list."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {}}))
        with pytest.raises(ValueError, match="Malformed"):
            load_index_documents(idx)

    def test_truly_absent_envelope_returns_empty_list(self, tmp_path):
        """No data field at all returns empty list."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"version": "1.0"}))
        result = load_index_documents(idx)
        assert result == []

    def test_nodes_as_dict_raises_value_error(self, tmp_path):
        """'nodes' key with non-list type raises ValueError."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {"nodes": {"a": 1}}}))
        with pytest.raises(ValueError, match="nodes.*must be a list"):
            load_index_documents(idx)

    def test_documents_as_dict_under_data_raises(self, tmp_path):
        """'documents' key under data with non-list raises ValueError."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"data": {"documents": {"a": 1}}}))
        with pytest.raises(ValueError, match="documents.*must be a list"):
            load_index_documents(idx)

    def test_top_level_documents_as_dict_raises(self, tmp_path):
        """Top-level 'documents' with non-list raises ValueError."""
        idx = tmp_path / "index.json"
        idx.write_text(json.dumps({"documents": {"a": 1}}))
        with pytest.raises(ValueError, match="documents.*must be a list"):
            load_index_documents(idx)
