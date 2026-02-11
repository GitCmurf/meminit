from importlib import resources
from pathlib import Path
from typing import Mapping, Optional

import yaml

from meminit.core.services.org_profiles import resolve_org_profile

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
    "templates/template-001-adr.md": b"# <REPO>-ADR-<SEQ>: <Decision Title>\\n\\n"
    b"## 1. Context & Problem Statement\\n\\n"
    b"## 2. Decision Drivers\\n\\n"
    b"## 3. Options Considered\\n\\n"
    b"## 4. Decision Outcome\\n\\n"
    b"## 5. Consequences\\n",
    "templates/template-001-fdd.md": b"# FDD: {title}\\n\\n## Feature Description\\n",
    "templates/template-001-prd.md": b"# PRD: {title}\\n\\n## Product Requirements\\n",
}


class InitRepositoryUseCase:
    def __init__(self, root_dir: str, env: Optional[Mapping[str, str]] = None):
        self.root_dir = Path(root_dir).resolve()
        self.docs_dir = self.root_dir / "docs"
        self._env = env

    def execute(self):
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
            (self.docs_dir / d).mkdir(parents=True, exist_ok=True)

        # 2. Create docops.config.yaml
        config_path = self.root_dir / "docops.config.yaml"
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
                "type_directories": {
                    "GOV": "00-governance",
                    "RFC": "00-governance",
                    "STRAT": "02-strategy",
                    "PRD": "10-prd",
                    "RESEARCH": "10-prd",
                    "PLAN": "05-planning",
                    "TASK": "05-planning/tasks",
                    "SPEC": "20-specs",
                    "DESIGN": "30-design",
                    "DECISION": "40-decisions",
                    "ADR": "45-adr",
                    "FDD": "50-fdd",
                    "INDEX": "01-indices",
                    "TESTING": "55-testing",
                    "LOG": "58-logs",
                    "GUIDE": "60-runbooks",
                    "RUNBOOK": "60-runbooks",
                    "REF": "70-devex",
                },
                "templates": {
                    "adr": "docs/00-governance/templates/template-001-adr.md",
                    "fdd": "docs/00-governance/templates/template-001-fdd.md",
                    "prd": "docs/00-governance/templates/template-001-prd.md",
                },
            }
            config_path.write_text(
                yaml.safe_dump(config_content, sort_keys=False),
                encoding="utf-8",
            )

        # 3. Create Templates & Schema
        gov_dir = self.docs_dir / "00-governance"
        template_dir = gov_dir / "templates"
        template_dir.mkdir(parents=True, exist_ok=True)

        # Default to org standards (global profile if installed; otherwise packaged defaults).
        #
        # This must still behave reasonably even if packaged resources are unavailable (e.g., in
        # constrained environments or tests that simulate missing assets).
        try:
            profile = resolve_org_profile(profile_name="default", env=self._env, prefer_global=True)
            schema_bytes = profile.files.get("metadata.schema.json") or _FALLBACK_SCHEMA_JSON
            template_bytes = {
                rel: (profile.files.get(rel) or _FALLBACK_TEMPLATES[rel])
                for rel in _FALLBACK_TEMPLATES
            }
        except Exception:
            schema_bytes = _FALLBACK_SCHEMA_JSON
            template_bytes = dict(_FALLBACK_TEMPLATES)

        schema_path = gov_dir / "metadata.schema.json"
        if not schema_path.exists():
            schema_path.write_bytes(schema_bytes)

        for rel, content in template_bytes.items():
            dest = gov_dir / rel
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)

        # 4. Create AGENTS.md
        agents_path = self.root_dir / "AGENTS.md"
        if not agents_path.exists():
            repo_prefix = self._load_repo_prefix_from_config()
            agents_content = self._load_agents_template()
            agents_content = agents_content.replace("{{PROJECT_NAME}}", self.root_dir.name).replace(
                "{{REPO_PREFIX}}", repo_prefix
            )
            agents_path.write_text(agents_content, encoding="utf-8")

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
