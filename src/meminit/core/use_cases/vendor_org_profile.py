from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional

import yaml

from meminit.core.services.org_profiles import OrgProfile, resolve_org_profile
from meminit.core.services.repo_config import load_repo_layout
from meminit.core.services.safe_fs import ensure_safe_write_path


@dataclass(frozen=True)
class OrgVendorReport:
    profile_name: str
    profile_version: str
    source: str
    digest: str
    dry_run: bool
    updated_files: int
    created_files: int
    unchanged_files: int
    lock_path: str
    message: str

    def as_dict(self) -> dict:
        return {
            "profile_name": self.profile_name,
            "profile_version": self.profile_version,
            "source": self.source,
            "digest": self.digest,
            "dry_run": self.dry_run,
            "updated_files": self.updated_files,
            "created_files": self.created_files,
            "unchanged_files": self.unchanged_files,
            "lock_path": self.lock_path,
            "message": self.message,
        }


class VendorOrgProfileUseCase:
    """
    Copy an org profile into a repository (vendoring) so compliance rules do not drift.

    We vendor:
    - `metadata.schema.json` -> `docs/00-governance/metadata.schema.json`
    - templates -> `docs/00-governance/templates/`
    - org docs -> `docs/00-governance/org/` (optional but recommended)
    - lock file -> `.meminit/org-profile.lock.json` (pins digest + metadata)

    Safety:
    - dry-run by default
    - refuses to overwrite an existing lock file unless `force=True`
    """

    def __init__(self, root_dir: str, env: Optional[Mapping[str, str]] = None):
        self._root = Path(root_dir).resolve()
        self._env = env

    def execute(
        self,
        profile_name: str = "default",
        dry_run: bool = True,
        force: bool = False,
        include_org_docs: bool = True,
    ) -> OrgVendorReport:
        profile = resolve_org_profile(profile_name=profile_name, env=self._env, prefer_global=True)
        layout = load_repo_layout(self._root)
        repo_docs_root = layout.default_namespace().docs_root.strip("/").replace("\\", "/") or "docs"

        lock_path = self._root / ".meminit" / "org-profile.lock.json"
        if lock_path.exists() and not force:
            return OrgVendorReport(
                profile_name=profile.name,
                profile_version=profile.version,
                source=profile.source,
                digest=profile.digest(),
                dry_run=dry_run,
                updated_files=0,
                created_files=0,
                unchanged_files=0,
                lock_path=str(lock_path.relative_to(self._root)),
                message="Lock file exists; refusing to overwrite (use --force to update).",
            )

        mapping: Dict[str, str] = {
            "metadata.schema.json": f"{repo_docs_root}/00-governance/metadata.schema.json",
            "templates/template-001-adr.md": f"{repo_docs_root}/00-governance/templates/template-001-adr.md",
            "templates/template-001-fdd.md": f"{repo_docs_root}/00-governance/templates/template-001-fdd.md",
            "templates/template-001-prd.md": f"{repo_docs_root}/00-governance/templates/template-001-prd.md",
        }
        if include_org_docs:
            mapping.update(
                {
                    "org_docs/org-gov-001-constitution.md": f"{repo_docs_root}/00-governance/org/org-gov-001-constitution.md",
                    "org_docs/org-gov-002-metadata-schema.md": f"{repo_docs_root}/00-governance/org/org-gov-002-metadata-schema.md",
                }
            )

        created = updated = same = 0
        for src_rel, dest_rel in mapping.items():
            dest = self._root / dest_rel
            content = profile.files.get(src_rel, b"")
            if not dest.exists():
                created += 1
            else:
                try:
                    existing = dest.read_bytes()
                except OSError:
                    updated += 1
                else:
                    if existing == content:
                        same += 1
                    else:
                        updated += 1

        if dry_run:
            return OrgVendorReport(
                profile_name=profile.name,
                profile_version=profile.version,
                source=profile.source,
                digest=profile.digest(),
                dry_run=True,
                updated_files=updated,
                created_files=created,
                unchanged_files=same,
                lock_path=str(lock_path.relative_to(self._root)),
                message="Dry run complete.",
            )

        # Write files
        for src_rel, dest_rel in mapping.items():
            dest = self._root / dest_rel
            ensure_safe_write_path(root_dir=self._root, target_path=dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(profile.files[src_rel])

        # Update docops.config.yaml (do not overwrite; merge).
        self._ensure_repo_config_for_org(profile, repo_docs_root=repo_docs_root, include_org_docs=include_org_docs)

        lock_path.parent.mkdir(parents=True, exist_ok=True)
        ensure_safe_write_path(root_dir=self._root, target_path=lock_path)
        lock_payload = {
            "lock_schema_version": "1.0",
            "profile_name": profile.name,
            "profile_version": profile.version,
            "source": profile.source,
            "digest": profile.digest(),
            "vendored_at": datetime.now(timezone.utc).isoformat(),
        }
        lock_path.write_text(json.dumps(lock_payload, indent=2), encoding="utf-8")

        return OrgVendorReport(
            profile_name=profile.name,
            profile_version=profile.version,
            source=profile.source,
            digest=profile.digest(),
            dry_run=False,
            updated_files=updated,
            created_files=created,
            unchanged_files=same,
            lock_path=str(lock_path.relative_to(self._root)),
            message="Vendored org profile into repository.",
        )

    def _ensure_repo_config_for_org(
        self, profile: OrgProfile, repo_docs_root: str, include_org_docs: bool
    ) -> None:
        config_path = self._root / "docops.config.yaml"
        ensure_safe_write_path(root_dir=self._root, target_path=config_path)
        data: dict = {}
        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except Exception:
                data = {}
        if not isinstance(data, dict):
            data = {}

        # Ensure schema_path points at the vendored schema.
        data.setdefault("schema_path", f"{repo_docs_root}/00-governance/metadata.schema.json")

        # If org docs are vendored, ensure namespace config exists so ORG-* IDs are valid.
        if include_org_docs:
            namespaces = data.get("namespaces")
            if not isinstance(namespaces, list):
                namespaces = []
            # Make sure there's a "repo" namespace.
            if not any(isinstance(n, dict) and n.get("repo_prefix") for n in namespaces):
                repo_prefix = data.get("repo_prefix") or "REPO"
                namespaces.append({"name": "repo", "repo_prefix": str(repo_prefix), "docs_root": repo_docs_root})

            if not any(isinstance(n, dict) and n.get("repo_prefix") == "ORG" for n in namespaces):
                namespaces.append(
                    {
                        "name": "org",
                        "repo_prefix": "ORG",
                        "docs_root": f"{repo_docs_root}/00-governance/org",
                        "type_directories": {"GOV": "."},
                    }
                )
            data["namespaces"] = namespaces

        config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
