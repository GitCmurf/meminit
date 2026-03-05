"""Tests for state_document.py use case."""

import json
from pathlib import Path
from unittest import mock

import pytest
import yaml

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.use_cases.state_document import StateDocumentUseCase


def test_set_new_document_creates_state_file(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress", notes="Testing")

    assert result.document_id == "MEMINIT-ADR-001"
    assert result.action == "set"
    assert result.entry["impl_state"] == "In Progress"
    assert result.entry["notes"] == "Testing"
    assert result.entry["updated_by"] is not None

    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    assert state_file.exists()


def test_set_existing_document_updates_fields(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="In Progress", notes="V1")
    
    # Update state only
    result2 = use_case.set_state("MEMINIT-ADR-001", impl_state="Blocked")
    assert result2.entry["impl_state"] == "Blocked"
    assert result2.entry["notes"] == "V1"  # Retained
    
    # Update notes only
    result3 = use_case.set_state("MEMINIT-ADR-001", notes="V2")
    assert result3.entry["impl_state"] == "Blocked"  # Retained
    assert result3.entry["notes"] == "V2"


def test_set_canonicalizes_impl_state(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="qa required")
    # PRD-007: impl_state is normalized
    assert result.entry["impl_state"] == "QA Required"


def test_set_invalid_impl_state_raises(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    with pytest.raises(MeminitError) as exc_info:
        use_case.set_state("MEMINIT-ADR-001", impl_state="Bogus")
    assert exc_info.value.code == ErrorCode.E_INVALID_FILTER_VALUE


def test_get_document_state(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    result = use_case.get_state("MEMINIT-ADR-001")
    assert result.action == "get"
    assert result.entry["impl_state"] == "Done"


def test_get_missing_document_raises(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("MEMINIT-ADR-001", impl_state="Done")

    with pytest.raises(MeminitError) as exc_info:
        use_case.get_state("MEMINIT-ADR-002")
    assert exc_info.value.code == ErrorCode.FILE_NOT_FOUND


def test_list_states_sorted(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    use_case.set_state("C-002", impl_state="Done")
    use_case.set_state("A-001", impl_state="In Progress")
    use_case.set_state("B-003", impl_state="Blocked")

    result = use_case.list_states()
    assert result.action == "list"
    assert len(result.entries) == 3
    
    ids = [e["document_id"] for e in result.entries]
    assert ids == ["A-001", "B-003", "C-002"]  # Alphabetical 


@mock.patch.dict("os.environ", {"MEMINIT_ACTOR_ID": "ci-bot"})
def test_actor_resolution_env_var(tmp_path):
    use_case = StateDocumentUseCase(str(tmp_path))
    result = use_case.set_state("MEMINIT-ADR-001", impl_state="Done")
    assert result.entry["updated_by"] == "ci-bot"
