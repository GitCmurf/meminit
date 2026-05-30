from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "check_all_envelopes.py"
SPEC = importlib.util.spec_from_file_location("check_all_envelopes", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def _successful_envelope():
    return json.dumps(
        {
            "output_schema_version": "3.0",
            "success": True,
            "command": "check",
            "run_id": "123e4567-e89b-12d3-a456-426614174000",
            "data": {},
            "warnings": [],
            "violations": [],
            "advice": [],
            "root": "/tmp/meminit-test",
        }
    )


def test_build_command_targets_checkout_project_and_temp_repo(tmp_path):
    command = MODULE.build_command(["check"], root=tmp_path)

    assert command == [
        "uv",
        "run",
        "meminit",
        "check",
        "--root",
        str(tmp_path),
        "--format",
        "json",
    ]


def test_check_command_runs_from_checkout_root_and_targets_temp_repo(monkeypatch, tmp_path):
    captured = {}

    def fake_run(cmd, env, cwd, capture_output, text, timeout):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        captured["timeout"] = timeout
        return SimpleNamespace(
            returncode=0,
            stdout=_successful_envelope(),
            stderr="",
        )

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    assert MODULE.check_command(["check"], root=tmp_path) is True
    assert captured["cwd"] == MODULE.REPO_ROOT
    assert captured["cmd"] == [
        "uv",
        "run",
        "meminit",
        "check",
        "--root",
        str(tmp_path),
        "--format",
        "json",
    ]
    assert captured["timeout"] == MODULE.TIMEOUT


def test_check_command_keeps_org_install_repo_agnostic(monkeypatch):
    captured = {}

    def fake_run(cmd, env, cwd, capture_output, text, timeout):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "output_schema_version": "3.0",
                    "success": True,
                    "command": "org install",
                    "run_id": "123e4567-e89b-12d3-a456-426614174000",
                    "data": {"installed": []},
                    "warnings": [],
                    "violations": [],
                    "advice": [],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    assert MODULE.check_command(["org", "install", "--dry-run"], root=Path("/tmp/ignored"))
    assert captured["cwd"] == MODULE.REPO_ROOT
    assert "--root" not in captured["cmd"]
