from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml

from meminit.core.services.repo_config import load_repo_config
from meminit.core.services.safe_fs import ensure_safe_write_path

HOOK_ID = "meminit-check"


@dataclass(frozen=True)
class InstallPrecommitResult:
    config_path: Path
    status: str
    updated: bool


class InstallPrecommitUseCase:
    def __init__(self, root_dir: str):
        self._root_dir = Path(root_dir).resolve()
        self._repo_config = load_repo_config(self._root_dir)

    def execute(self) -> InstallPrecommitResult:
        config_path = self._root_dir / ".pre-commit-config.yaml"
        ensure_safe_write_path(root_dir=self._root_dir, target_path=config_path)
        docs_root = self._repo_config.docs_root

        hook = {
            "id": HOOK_ID,
            "name": "meminit check",
            "entry": f"meminit check --root .",
            "language": "system",
            "pass_filenames": False,
            "files": rf"^{re.escape(docs_root)}/",
        }

        if not config_path.exists():
            data: Dict[str, Any] = {"repos": [{"repo": "local", "hooks": [hook]}]}
            config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
            return InstallPrecommitResult(config_path=config_path, status="created", updated=True)

        data = self._load_config(config_path)
        repos = data.get("repos")
        if not isinstance(repos, list):
            raise ValueError("Invalid .pre-commit-config.yaml: expected top-level 'repos' list.")

        if self._has_meminit_hook(repos):
            return InstallPrecommitResult(
                config_path=config_path, status="already_installed", updated=False
            )

        local_repo = self._find_local_repo(repos)
        if local_repo is None:
            repos.append({"repo": "local", "hooks": [hook]})
        else:
            hooks = local_repo.setdefault("hooks", [])
            if not isinstance(hooks, list):
                raise ValueError(
                    "Invalid .pre-commit-config.yaml: local repo 'hooks' must be a list."
                )
            hooks.append(hook)

        config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        return InstallPrecommitResult(config_path=config_path, status="installed", updated=True)

    def _load_config(self, path: Path) -> Dict[str, Any]:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            raise ValueError("Invalid .pre-commit-config.yaml: unable to parse YAML.") from exc
        if not isinstance(data, dict):
            raise ValueError("Invalid .pre-commit-config.yaml: expected a YAML mapping.")
        return data

    def _find_local_repo(self, repos: List[Any]) -> Dict[str, Any] | None:
        for repo in repos:
            if isinstance(repo, dict) and repo.get("repo") == "local":
                return repo
        return None

    def _has_meminit_hook(self, repos: List[Any]) -> bool:
        for repo in repos:
            if not isinstance(repo, dict):
                continue
            hooks = repo.get("hooks")
            if not isinstance(hooks, list):
                continue
            for hook in hooks:
                if not isinstance(hook, dict):
                    continue
                if hook.get("id") == HOOK_ID:
                    return True
                entry = hook.get("entry")
                if isinstance(entry, str) and "meminit check" in entry:
                    return True
        return False
