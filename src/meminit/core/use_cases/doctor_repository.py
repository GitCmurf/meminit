from __future__ import annotations

import json
import re
from pathlib import Path
from typing import List

from jsonschema import Draft7Validator

from meminit.core.domain.entities import Severity, Violation
from meminit.core.services.repo_config import load_repo_layout


class DoctorRepositoryUseCase:
    """
    Lightweight self-check for repo readiness.

    Intended for:
    - humans: "is meminit wired correctly here?"
    - tooling: other packages can shell out and parse JSON output.
    """

    REPO_PREFIX_REGEX = re.compile(r"^[A-Z]{3,10}$")

    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir

    def execute(self) -> List[Violation]:
        issues: List[Violation] = []

        config_path = self._root_dir / "docops.config.yaml"
        if not config_path.exists():
            issues.append(
                Violation(
                    file="docops.config.yaml",
                    line=0,
                    rule="CONFIG_MISSING",
                    message="docops.config.yaml not found; defaults will be used (run `meminit init` to scaffold one).",
                    severity=Severity.WARNING,
                )
            )

        seen_namespace_names: set[str] = set()
        for ns in self._layout.namespaces:
            if ns.namespace.lower() in seen_namespace_names:
                issues.append(
                    Violation(
                        file="docops.config.yaml",
                        line=0,
                        rule="CONFIG_INVALID",
                        message=f"Duplicate namespace name '{ns.namespace}' in configuration.",
                        severity=Severity.ERROR,
                    )
                )
            seen_namespace_names.add(ns.namespace.lower())

            if not self.REPO_PREFIX_REGEX.match(ns.repo_prefix):
                issues.append(
                    Violation(
                        file="docops.config.yaml",
                        line=0,
                        rule="CONFIG_INVALID",
                        message=(
                            f"repo_prefix '{ns.repo_prefix}' is invalid for namespace '{ns.namespace}'; "
                            "expected 3-10 uppercase letters (e.g., MEMINIT)."
                        ),
                        severity=Severity.ERROR,
                    )
                )

            if not ns.docs_dir.exists():
                issues.append(
                    Violation(
                        file=str(Path(ns.docs_root)),
                        line=0,
                        rule="DOCS_ROOT_MISSING",
                        message=(
                            f"Docs root '{ns.docs_root}/' does not exist for namespace '{ns.namespace}' "
                            "(create it or adjust config)."
                        ),
                        severity=Severity.WARNING,
                    )
                )

        seen_schema_paths: set[str] = set()
        for ns in self._layout.namespaces:
            if ns.schema_path in seen_schema_paths:
                continue
            seen_schema_paths.add(ns.schema_path)

            schema_path = ns.schema_file
            if not schema_path.exists():
                issues.append(
                    Violation(
                        file=str(Path(ns.schema_path)),
                        line=0,
                        rule="SCHEMA_MISSING",
                        message=f"Schema file missing at '{ns.schema_path}' (run `meminit init`).",
                        severity=Severity.ERROR,
                    )
                )
            else:
                issues.extend(self._validate_schema(schema_path))

        for ns in self._layout.namespaces:
            for template_key, template_path in sorted(ns.templates.items()):
                p = self._root_dir / template_path
                if not p.exists():
                    issues.append(
                        Violation(
                            file=str(Path(template_path)),
                            line=0,
                            rule="TEMPLATE_MISSING",
                            message=f"Template '{template_key}' not found at '{template_path}'.",
                            severity=Severity.WARNING,
                        )
                    )

        return issues

    def _validate_schema(self, schema_path: Path) -> List[Violation]:
        issues: List[Violation] = []

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            try:
                schema_file = str(schema_path.relative_to(self._root_dir))
            except ValueError:
                schema_file = str(schema_path)
            issues.append(
                Violation(
                    file=schema_file,
                    line=0,
                    rule="SCHEMA_INVALID",
                    message=f"Schema file could not be read/parsed: {e}",
                    severity=Severity.ERROR,
                )
            )
            return issues

        try:
            Draft7Validator.check_schema(schema)
        except Exception as e:
            try:
                schema_file = str(schema_path.relative_to(self._root_dir))
            except ValueError:
                schema_file = str(schema_path)
            issues.append(
                Violation(
                    file=schema_file,
                    line=0,
                    rule="SCHEMA_INVALID",
                    message=f"Schema is not a valid Draft 7 JSON Schema: {e}",
                    severity=Severity.ERROR,
                )
            )

        return issues
