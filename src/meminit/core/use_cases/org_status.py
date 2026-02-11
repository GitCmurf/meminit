from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from meminit.core.services.org_profiles import global_profile_dir, resolve_org_profile


@dataclass(frozen=True)
class OrgStatusReport:
    profile_name: str
    global_installed: bool
    global_dir: str
    repo_lock_present: bool
    repo_lock_path: str
    repo_lock_digest: Optional[str]
    current_profile_source: str
    current_profile_digest: str
    repo_lock_matches_current: Optional[bool]

    def as_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "global_installed": self.global_installed,
            "global_dir": self.global_dir,
            "repo_lock_present": self.repo_lock_present,
            "repo_lock_path": self.repo_lock_path,
            "repo_lock_digest": self.repo_lock_digest,
            "current_profile_source": self.current_profile_source,
            "current_profile_digest": self.current_profile_digest,
            "repo_lock_matches_current": self.repo_lock_matches_current,
        }


class OrgStatusUseCase:
    def __init__(self, root_dir: str, env: Optional[Mapping[str, str]] = None):
        self._root = Path(root_dir).resolve()
        self._env = env

    def execute(self, profile_name: str = "default") -> OrgStatusReport:
        global_dir = global_profile_dir(profile_name, env=self._env)
        global_installed = (global_dir / "profile.json").exists()

        profile = resolve_org_profile(profile_name=profile_name, env=self._env, prefer_global=True)

        lock_path = self._root / ".meminit" / "org-profile.lock.json"
        repo_lock_present = lock_path.exists()
        lock_digest = None
        matches = None
        if repo_lock_present:
            try:
                data = json.loads(lock_path.read_text(encoding="utf-8"))
                lock_digest = data.get("digest")
                if isinstance(lock_digest, str):
                    matches = lock_digest == profile.digest()
            except Exception:
                lock_digest = None
                matches = None

        return OrgStatusReport(
            profile_name=profile_name,
            global_installed=global_installed,
            global_dir=str(global_dir),
            repo_lock_present=repo_lock_present,
            repo_lock_path=str(lock_path.relative_to(self._root)),
            repo_lock_digest=lock_digest if isinstance(lock_digest, str) else None,
            current_profile_source=profile.source,
            current_profile_digest=profile.digest(),
            repo_lock_matches_current=matches,
        )

