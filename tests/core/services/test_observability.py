import os

import pytest

from meminit.core.services.observability import (
    get_current_run_id,
    get_log_format,
    get_run_id,
    is_debug_enabled,
    log_event,
)


class TestObservability:
    def test_get_run_id_generates_unique(self, monkeypatch):
        monkeypatch.delenv("MEMINIT_RUN_ID", raising=False)
        id1 = get_run_id()
        id2 = get_run_id()
        assert id1 != id2
        assert len(id1) == 8

    def test_get_run_id_uses_env(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_RUN_ID", "test1234")
        assert get_run_id() == "test1234"

    def test_get_log_format_default(self, monkeypatch):
        monkeypatch.delenv("MEMINIT_LOG_FORMAT", raising=False)
        assert get_log_format() == "text"

    def test_get_log_format_json(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        assert get_log_format() == "json"

    def test_get_log_format_text(self, monkeypatch):
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "text")
        assert get_log_format() == "text"

    def test_is_debug_enabled_default(self, monkeypatch):
        monkeypatch.delenv("MEMINIT_DEBUG", raising=False)
        assert is_debug_enabled() is False

    def test_is_debug_enabled_true_values(self, monkeypatch):
        for val in ("1", "true", "True", "TRUE", "yes", "Yes", "YES"):
            monkeypatch.setenv("MEMINIT_DEBUG", val)
            assert is_debug_enabled() is True

    def test_is_debug_enabled_false_values(self, monkeypatch):
        for val in ("0", "false", "no", "", "random"):
            monkeypatch.setenv("MEMINIT_DEBUG", val)
            assert is_debug_enabled() is False

    def test_get_current_run_id_returns_same_id(self, monkeypatch):
        import meminit.core.services.observability as obs

        monkeypatch.delenv("MEMINIT_RUN_ID", raising=False)
        monkeypatch.setattr(obs, "_current_run_id", None, raising=False)
        id1 = get_current_run_id()
        id2 = get_current_run_id()
        assert id1 == id2

    def test_log_event_no_output_when_disabled(self, monkeypatch, capsys):
        monkeypatch.delenv("MEMINIT_DEBUG", raising=False)
        log_event("test_event", {"key": "value"})
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_log_event_json_format(self, monkeypatch, capsys):
        import json

        monkeypatch.setenv("MEMINIT_DEBUG", "1")
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        log_event("test_event", {"key": "value"})
        captured = capsys.readouterr()
        entry = json.loads(captured.out.strip())
        assert entry["event"] == "test_event"
        assert entry["data"]["key"] == "value"
        assert "timestamp" in entry
        assert "run_id" in entry

    def test_log_event_text_format(self, monkeypatch, capsys):
        monkeypatch.setenv("MEMINIT_DEBUG", "1")
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "text")
        log_event("test_event", {"key": "value"})
        captured = capsys.readouterr()
        assert "[test_event]:" in captured.out or "test_event:" in captured.out
        assert "key=value" in captured.out

    def test_log_event_without_data(self, monkeypatch, capsys):
        import json

        monkeypatch.setenv("MEMINIT_DEBUG", "1")
        monkeypatch.setenv("MEMINIT_LOG_FORMAT", "json")
        log_event("simple_event")
        captured = capsys.readouterr()
        entry = json.loads(captured.out.strip())
        assert entry["event"] == "simple_event"
        assert "data" not in entry
