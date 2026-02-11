from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from meminit.core.services.org_profiles import (
    OrgProfile,
    global_profile_dir,
    load_packaged_profile,
)


@dataclass(frozen=True)
class OrgInstallReport:
    profile_name: str
    target_dir: str
    dry_run: bool
    installed: bool
    message: str

    def as_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "target_dir": self.target_dir,
            "dry_run": self.dry_run,
            "installed": self.installed,
            "message": self.message,
        }


class InstallOrgProfileUseCase:
    def __init__(self, env: Optional[Mapping[str, str]] = None):
        self._env = env

    def execute(
        self,
        profile_name: str = "default",
        dry_run: bool = True,
        force: bool = False,
    ) -> OrgInstallReport:
        profile: OrgProfile = load_packaged_profile(profile_name=profile_name)
        target_dir = global_profile_dir(profile_name, env=self._env)
        manifest_path = target_dir / "profile.json"

        if manifest_path.exists() and not force:
            return OrgInstallReport(
                profile_name=profile_name,
                target_dir=str(target_dir),
                dry_run=dry_run,
                installed=False,
                message="Profile already installed (use --force to overwrite).",
            )

        if dry_run:
            return OrgInstallReport(
                profile_name=profile_name,
                target_dir=str(target_dir),
                dry_run=True,
                installed=False,
                message=f"Would install profile '{profile_name}' to {target_dir}",
            )

        target_dir.mkdir(parents=True, exist_ok=True)

        # Write all profile files into the global profile directory.
        for rel, content in profile.files.items():
            dest = target_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)

        return OrgInstallReport(
            profile_name=profile_name,
            target_dir=str(target_dir),
            dry_run=False,
            installed=True,
            message=f"Installed profile '{profile_name}' to {target_dir}",
        )
