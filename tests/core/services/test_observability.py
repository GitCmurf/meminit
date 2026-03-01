import os
import re

import pytest

from meminit.core.services.observability import (
    get_current_run_id,
    get_log_format,
    get_run_id,
    log_event,
    log_operation,
)
from meminit.core.services.error_codes import MeminitError, ErrorCode


class TestObservability:
    def test_get_run_id_generates_unique(self, monkeypatch):
        monkeypatch.delenv("MEMINIT_RUN_ID", raising=False)
        id1 = get_run_id()
        id2 = get_run_id()
        assert id1 != id2
        assert len(id1) == 36  # Full UUIDv4

    def test_get_run_id_uses_env(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_RUN_ID", "00000000-0000-4000-8000-000000000000")
        assert get_run_id() == "00000000-0000-4000-8000-000000000000"

    def test_get_run_id_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_RUN_ID", "not-a-uuid")
        run_id = get_run_id()
        assert run_id != "not-a-uuid"
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            run_id,
        )

    def test_get_log_format_default(self, monkeypatch):
        monkeypatch.delenv("MEMINIT_LOG_FORMAT", raising=False)
        assert get_log_format() == "text"

    def test_get_log_format_json(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        assert get_log_format() == "json"

    def test_get_log_format_text(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "text")
        assert get_log_format() == "text"

    def test_get_current_run_id_returns_same_id(self, monkeypatch):
        import meminit.core.services.observability as obs

        monkeypatch.delenv("MEMINIT_RUN_ID", raising=False)
        monkeypatch.setattr(obs, "_current_run_id", None, raising=False)
        id1 = get_current_run_id()
        id2 = get_current_run_id()
        assert id1 == id2

    def test_log_event_json_format(self, monkeypatch, capsys):
        import json

        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        log_event("test_event", True, details={"key": "value"})
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["operation"] == "test_event"
        assert entry["details"]["key"] == "value"
        assert "timestamp" in entry
        assert "run_id" in entry

    def test_log_event_text_format(self, monkeypatch, capsys):
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "text")
        log_event("test_event", True, details={"key": "value"})
        captured = capsys.readouterr()
        assert "test_event" in captured.err
        assert "OK" in captured.err
        assert re.search(r'"key"\s*:\s*"value"', captured.err)

    def test_log_event_without_details(self, monkeypatch, capsys):
        import json

        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        log_event("simple_event", True)
        captured = capsys.readouterr()
        entry = json.loads(captured.err.strip())
        assert entry["operation"] == "simple_event"
        assert "details" not in entry

    def test_log_operation_includes_duration_on_failure(self, monkeypatch, capsys):
        """N5.2: Failure logs must include duration_ms and error_code."""
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "text")
        with pytest.raises(MeminitError):
            with log_operation("test_op"):
                raise MeminitError(code=ErrorCode.INVALID_STATUS, message="Test error")

        captured = capsys.readouterr()
        assert "test_op" in captured.err
        assert "FAILED" in captured.err
        assert "INVALID_STATUS" in captured.err
        assert re.search(r"\(\d+\.\d+ms\)", captured.err)
