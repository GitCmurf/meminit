from importlib import resources
from pathlib import Path
from dataclasses import dataclass
from typing import List, Mapping, Optional
import logging

import yaml

from meminit.core.services.org_profiles import resolve_org_profile
from meminit.core.services.safe_fs import ensure_safe_write_path

# Agent skill paths
_AGENTS_SKILLS_DIR = Path(".agents") / "skills"
_MEMINIT_DOCOPS_SKILL = "meminit-docops"

_FALLBACK_SCHEMA_JSON = b"""{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://meminit.io/schemas/metadata.schema.json",
  "title": "Meminit Governed Document Frontmatter",
  "type": "object",
  "required": [
    "document_id",
    "type",
    "title",
    "status",
    "version",
    "last_updated",
    "owner",
    "docops_version"
  ],
  "properties": {
    "document_id": {
      "type": "string",
      "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\\\d{3}$"
    },
    "type": { "type": "string" },
    "title": { "type": "string" },
    "status": {
      "type": "string",
      "enum": ["Draft", "In Review", "Approved", "Superseded"]
    },
    "version": { "type": "string", "pattern": "^\\\\d+\\\\.\\\\d+$" },
    "last_updated": { "type": "string", "format": "date" },
    "owner": { "type": "string" },
    "docops_version": { "type": "string" }
  },
  "additionalProperties": false
}
"""

_FALLBACK_TEMPLATES: dict[str, bytes] = {
    "templates/adr.template.md": b"<!-- MEMINIT_METADATA_BLOCK -->\\n\\n> **Document ID:** {{document_id}}\\n> **Owner:** {{owner}}\\n> **Status:** {{status}}\\n> **Version:** 0.1\\n> **Last Updated:** {{date}}\\n> **Type:** {{type}}\\n\\n# {{document_id}}: {{title}}\\n\\n## 1. Context & Problem Statement\\n\\n## 2. Decision Drivers\\n\\n## 3. Options Considered\\n\\n## 4. Decision Outcome\\n\\n## 5. Consequences\\n",
    "templates/fdd.template.md": b"<!-- MEMINIT_METADATA_BLOCK -->\\n\\n> **Document ID:** {{document_id}}\\n> **Owner:** {{owner}}\\n> **Status:** {{status}}\\n> **Version:** 0.1\\n> **Last Updated:** {{date}}\\n> **Type:** {{type}}\\n\\n# {{document_id}}: {{title}}\\n\\n## Feature Description\\n",
    "templates/prd.template.md": b"<!-- MEMINIT_METADATA_BLOCK -->\\n\\n> **Document ID:** {{document_id}}\\n> **Owner:** {{owner}}\\n> **Status:** {{status}}\\n> **Version:** 0.1\\n> **Last Updated:** {{date}}\\n> **Type:** {{type}}\\n\\n# {{document_id}}: {{title}}\\n\\n## Product Requirements\\n",
}


@dataclass(frozen=True)
class InitReport:
    created_paths: List[str]
    skipped_paths: List[str]


class InitRepositoryUseCase:
    def __init__(self, root_dir: str, env: Optional[Mapping[str, str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.docs_dir = self.root_dir / "docs"
        self._env = env

    def execute(self) -> InitReport:
        created_paths: List[str] = []
        skipped_paths: List[str] = []

        def record(path: Path, created: bool) -> None:
            rel = path.relative_to(self.root_dir).as_posix()
            if created:
                created_paths.append(rel)
            else:
                skipped_paths.append(rel)

        # 1. Create Directory Structure
        dirs = [
            "00-governance",
            "00-governance/templates",
            "01-indices",
            "02-strategy",
            "05-planning",
            "05-planning/tasks",
            "08-security",
            "10-prd",
            "12-notes",
            "20-specs",
            "30-design",
            "40-decisions",
            "45-adr",
            "50-fdd",
            "52-api",
            "55-testing",
            "58-logs",
            "60-runbooks",
            "70-devex",
            "96-reference",
            "99-archive",
        ]

        for d in dirs:
            target_dir = self.docs_dir / d
            ensure_safe_write_path(root_dir=self.root_dir, target_path=target_dir)
            created = True
            try:
                target_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                if not target_dir.is_dir():
                    raise
                created = False
            record(target_dir, created=created)

        # 2. Create docops.config.yaml
        config_path = self.root_dir / "docops.config.yaml"
        ensure_safe_write_path(root_dir=self.root_dir, target_path=config_path)
        if not config_path.exists():
            repo_prefix = self._derive_repo_prefix(self.root_dir.name)
            docs_root = "docs"
            config_content = {
                "project_name": self.root_dir.name,
                "repo_prefix": repo_prefix,
                "docops_version": "2.0",
                "docs_root": docs_root,
                "schema_path": f"{docs_root}/00-governance/metadata.schema.json",
                "excluded_paths": [f"{docs_root}/00-governance/templates"],
                "excluded_filename_prefixes": ["WIP-"],
                "document_types": {
                    "GOV": {"directory": "00-governance"},
                    "RFC": {"directory": "00-governance"},
                    "STRAT": {"directory": "02-strategy"},
                    "PRD": {"directory": "10-prd", "template": "docs/00-governance/templates/prd.template.md"},
                    "RESEARCH": {"directory": "10-prd"},
                    "PLAN": {"directory": "05-planning"},
                    "TASK": {"directory": "05-planning/tasks"},
                    "NOTES": {"directory": "12-notes"},
                    "SPEC": {"directory": "20-specs"},
                    "DESIGN": {"directory": "30-design"},
                    "DECISION": {"directory": "40-decisions"},
                    "ADR": {"directory": "45-adr", "template": "docs/00-governance/templates/adr.template.md"},
                    "FDD": {"directory": "50-fdd", "template": "docs/00-governance/templates/fdd.template.md"},
                    "INDEX": {"directory": "01-indices"},
                    "TESTING": {"directory": "55-testing"},
                    "LOG": {"directory": "58-logs"},
                    "GUIDE": {"directory": "60-runbooks"},
                    "RUNBOOK": {"directory": "60-runbooks"},
                    "REF": {"directory": "70-devex"},
                },
            }
            config_path.write_text(
                yaml.safe_dump(config_content, sort_keys=False),
                encoding="utf-8",
            )
            record(config_path, created=True)
        else:
            record(config_path, created=False)

        # 3. Create Templates & Schema
        gov_dir = self.docs_dir / "00-governance"
        template_dir = gov_dir / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)

        # Default to org standards (global profile if installed; otherwise packaged defaults).
        #
        # This must still behave reasonably even if packaged resources are unavailable (e.g., in
        # constrained environments or tests that simulate missing assets).
        try:
            profile = resolve_org_profile(
                profile_name="default", env=self._env, prefer_global=True
            )
            schema_bytes = (
                profile.files.get("metadata.schema.json") or _FALLBACK_SCHEMA_JSON
            )
            template_bytes = {
                rel: (profile.files.get(rel) or _FALLBACK_TEMPLATES[rel])
                for rel in _FALLBACK_TEMPLATES
            }
        except Exception:
            schema_bytes = _FALLBACK_SCHEMA_JSON
            template_bytes = dict(_FALLBACK_TEMPLATES)

        schema_path = gov_dir / "metadata.schema.json"
        ensure_safe_write_path(root_dir=self.root_dir, target_path=schema_path)
        if not schema_path.exists():
            schema_path.write_bytes(schema_bytes)
            record(schema_path, created=True)
        else:
            record(schema_path, created=False)

        for rel, content in template_bytes.items():
            dest = gov_dir / rel
            ensure_safe_write_path(root_dir=self.root_dir, target_path=dest)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                record(dest, created=True)
            else:
                record(dest, created=False)

        # 4. Create AGENTS.md
        repo_prefix = self._load_repo_prefix_from_config()
        agents_path = self.root_dir / "AGENTS.md"
        ensure_safe_write_path(root_dir=self.root_dir, target_path=agents_path)
        if not agents_path.exists():
            agents_content = self._load_agents_template()
            agents_content = agents_content.replace(
                "{{PROJECT_NAME}}", self.root_dir.name
            ).replace("{{REPO_PREFIX}}", repo_prefix)
            agents_path.write_text(agents_content, encoding="utf-8")
            record(agents_path, created=True)
        else:
            record(agents_path, created=False)

        # 5. Create agent skills directory
        # Codex expects .agents/skills/ in latest versions
        agents_skills_dir = self.root_dir / _AGENTS_SKILLS_DIR / _MEMINIT_DOCOPS_SKILL
        ensure_safe_write_path(root_dir=self.root_dir, target_path=agents_skills_dir)
        created = True
        try:
            agents_skills_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            if not agents_skills_dir.is_dir():
                raise
            created = False
        record(agents_skills_dir, created=created)

        # 5a. Install SKILL.md (even if directory already exists)
        self._install_optional_asset(
            target_path=agents_skills_dir / "SKILL.md",
            package_resource_path="meminit-docops-skill.md",
            record_fn=record,
            error_context="meminit-docops SKILL.md",
        )

        # 5b. Install scripts directory and brownfield helper script
        scripts_dir = agents_skills_dir / "scripts"
        ensure_safe_write_path(root_dir=self.root_dir, target_path=scripts_dir)
        created = True
        try:
            scripts_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            if not scripts_dir.is_dir():
                raise
            created = False
        record(scripts_dir, created=created)

        self._install_optional_asset(
            target_path=scripts_dir / "meminit_brownfield_plan.sh",
            package_resource_path="scripts/meminit_brownfield_plan.sh",
            record_fn=record,
            error_context="brownfield helper script",
            make_executable=True,
        )

        # 6. Install gov-001 constitution document
        self._install_optional_asset(
            target_path=self.docs_dir / "00-governance" / "DocOps_Constitution.md",
            package_resource_path="org_profiles/default/org_docs/org-gov-001-constitution.md",
            record_fn=record,
            error_context="gov-001 constitution",
            content_transform=lambda c: c.replace("ORG-", f"{repo_prefix}-"),
        )

        created_paths_sorted = sorted(set(created_paths))
        skipped_paths_sorted = sorted(set(skipped_paths))
        return InitReport(
            created_paths=created_paths_sorted,
            skipped_paths=skipped_paths_sorted,
        )

    def _install_optional_asset(
        self,
        target_path: Path,
        package_resource_path: str,
        record_fn,
        error_context: str,
        content_transform=None,
        make_executable: bool = False,
    ) -> None:
        """
        Install a file from package resources if it doesn't exist.

        Args:
            target_path: Where to install the file
            package_resource_path: Resource path within the package
            record_fn: Function to record creation status
            error_context: Description for error messages
            content_transform: Optional function to transform content before writing
            make_executable: If True, set executable permissions (0o755)
        """
        ensure_safe_write_path(root_dir=self.root_dir, target_path=target_path)

        if target_path.exists():
            if not target_path.is_file():
                raise FileExistsError(f"{target_path} exists and is not a file")
            if make_executable:
                self._set_executable_permission(target_path)
            record_fn(target_path, created=False)
            return

        try:
            content = (
                resources.files("meminit.core.assets")
                .joinpath(package_resource_path)
                .read_text(encoding="utf-8")
            )
            if content_transform:
                content = content_transform(content)
            target_path.write_text(content, encoding="utf-8")
            if make_executable:
                target_path.chmod(0o755)
            record_fn(target_path, created=True)
        except (OSError, FileNotFoundError) as e:
            logging.warning(f"Failed to install {error_context}: {e}")
            record_fn(target_path, created=False)

    def _load_agents_template(self) -> str:
        """
        Load the bundled AGENTS.md template from package resources.

        This must work when meminit is installed from a wheel (assets are not guaranteed to
        exist as plain files on disk).
        """
        try:
            template = (
                resources.files("meminit.core.assets")
                .joinpath("AGENTS.md")
                .read_text(encoding="utf-8")
            )
        except Exception:
            # Conservative fallback: still allow init to proceed with a minimal but valid file.
            template = (
                "# AGENTS.md\n\n"
                "This repository uses Meminit DocOps.\n\n"
                "- Project: {{PROJECT_NAME}}\n"
                "- Repo prefix: {{REPO_PREFIX}}\n"
            )
        return template

    def _derive_repo_prefix(self, project_name: str) -> str:
        prefix = "".join(c for c in project_name.upper() if "A" <= c <= "Z")
        if len(prefix) < 3:
            return "REPO"
        return prefix[:10]

    def _load_repo_prefix_from_config(self) -> str:
        config_path = self.root_dir / "docops.config.yaml"
        if config_path.exists():
            try:
                config = yaml.safe_load(config_path.read_text()) or {}
                configured = config.get("repo_prefix")
                if isinstance(configured, str) and configured.strip():
                    return configured.strip().upper()
            except Exception:
                pass
        return self._derive_repo_prefix(self.root_dir.name)

    def _set_executable_permission(self, path: Path) -> None:
        """Set executable permission bits on a file, preserving existing permissions."""
        try:
            current_mode = path.stat().st_mode
            path.chmod(current_mode | 0o111)
        except OSError as e:
            logging.warning(
                "Failed to set executable permissions on %s: %s",
                path.as_posix(),
                e,
            )
