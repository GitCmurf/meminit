from __future__ import annotations

from pathlib import Path

from meminit.core.services.path_utils import is_safe_cli_output_path


def test_is_safe_cli_output_path_rejects_forbidden_system_paths():
    assert not is_safe_cli_output_path(Path("/etc/meminit-output.json"))


def test_is_safe_cli_output_path_allows_regular_relative_paths():
    assert is_safe_cli_output_path(Path("out/meminit-output.json"))
