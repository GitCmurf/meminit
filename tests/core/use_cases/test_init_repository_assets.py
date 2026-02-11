from pathlib import Path

import pytest

from meminit.core.use_cases.init_repository import InitRepositoryUseCase


def test_init_repository_writes_agents_from_bundled_template(tmp_path: Path):
    InitRepositoryUseCase(root_dir=str(tmp_path)).execute()
    agents = tmp_path / "AGENTS.md"
    assert agents.exists()
    content = agents.read_text(encoding="utf-8")
    assert tmp_path.name in content


def test_init_repository_falls_back_if_template_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    from importlib import resources

    def _boom(*_args, **_kwargs):
        raise FileNotFoundError("no resource")

    monkeypatch.setattr(resources, "files", _boom)

    InitRepositoryUseCase(root_dir=str(tmp_path)).execute()
    agents = tmp_path / "AGENTS.md"
    assert agents.exists()
    content = agents.read_text(encoding="utf-8")
    assert "This repository uses Meminit DocOps." in content
