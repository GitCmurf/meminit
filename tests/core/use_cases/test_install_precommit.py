from pathlib import Path

import pytest
import yaml

from meminit.core.use_cases.install_precommit import HOOK_ID, InstallPrecommitUseCase


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_install_precommit_creates_file(tmp_path):
    use_case = InstallPrecommitUseCase(str(tmp_path))
    result = use_case.execute()

    config_path = tmp_path / ".pre-commit-config.yaml"
    assert result.status == "created"
    assert config_path.exists()

    data = _load_yaml(config_path)
    repos = data["repos"]
    assert repos[0]["repo"] == "local"
    hook = repos[0]["hooks"][0]
    assert hook["id"] == HOOK_ID
    assert hook["entry"].startswith("meminit check")
    assert "always_run" not in hook


def test_install_precommit_appends_to_existing_config(tmp_path):
    config_path = tmp_path / ".pre-commit-config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "repos": [
                    {"repo": "https://example.com/other", "rev": "v1", "hooks": []}
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    use_case = InstallPrecommitUseCase(str(tmp_path))
    result = use_case.execute()
    assert result.status == "installed"

    data = _load_yaml(config_path)
    repos = data["repos"]
    assert len(repos) == 2
    assert any(repo.get("repo") == "local" for repo in repos)


def test_install_precommit_respects_existing_hook(tmp_path):
    config_path = tmp_path / ".pre-commit-config.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "repos": [
                    {
                        "repo": "local",
                        "hooks": [
                            {
                                "id": HOOK_ID,
                                "entry": "meminit check --root .",
                                "language": "system",
                            }
                        ],
                    }
                ]
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    use_case = InstallPrecommitUseCase(str(tmp_path))
    result = use_case.execute()
    assert result.status == "already_installed"
    assert result.updated is False


def test_install_precommit_uses_custom_docs_root(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "docs_root: documentation\n", encoding="utf-8"
    )
    use_case = InstallPrecommitUseCase(str(tmp_path))
    result = use_case.execute()
    assert result.status == "created"

    data = _load_yaml(tmp_path / ".pre-commit-config.yaml")
    hook = data["repos"][0]["hooks"][0]
    assert hook["files"] == r"^documentation/"


def test_install_precommit_refuses_symlink_escape(tmp_path: Path):
    from meminit.core.services.error_codes import ErrorCode, MeminitError

    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)

    outside = tmp_path / "outside.yaml"
    outside.write_text(yaml.safe_dump({"repos": []}, sort_keys=False), encoding="utf-8")

    (repo_root / ".pre-commit-config.yaml").symlink_to(outside)

    use_case = InstallPrecommitUseCase(str(repo_root))
    with pytest.raises(MeminitError) as exc_info:
        use_case.execute()
    assert exc_info.value.code == ErrorCode.PATH_ESCAPE
