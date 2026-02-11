import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from jsonschema import Draft7Validator, FormatChecker

from meminit.core.domain.entities import Severity, Violation


class LinkChecker:
    LINK_REGEX = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir).resolve()
        self.docs_dir = self.root_dir / "docs"

    def _file_exists(self, path: Path) -> bool:
        return path.exists()

    def validate_links(self, source_file: str, body: str) -> List[Violation]:
        violations = []
        source_path = self.root_dir / source_file
        source_dir = source_path.parent

        for match in self.LINK_REGEX.finditer(body):
            _, link_target = match.groups()

            # Ignore external links and anchors
            lower_target = link_target.lower()
            if lower_target.startswith(
                ("http://", "https://", "mailto:")
            ) or link_target.startswith("#"):
                continue

            # Strip fragments: `other.md#section` should validate `other.md` exists
            raw_target = link_target
            if "#" in link_target:
                link_target, _fragment = link_target.split("#", 1)
                if not link_target:
                    # Treat as an anchor-only link
                    continue

            # Resolve path relative to source file
            target_path = (source_dir / link_target).resolve()

            # Ensure target stays within root_dir
            try:
                target_path.relative_to(self.root_dir)
            except ValueError:
                violations.append(
                    Violation(
                        file=source_file,
                        line=0,
                        rule="LINK_BROKEN",
                        message=f"Link target '{raw_target}' resolves outside root directory",
                        severity=Severity.ERROR,
                    )
                )
                continue

            # Use wrapped method for mockability/testing
            if not self._file_exists(target_path):
                violations.append(
                    Violation(
                        file=source_file,
                        line=0,
                        rule="LINK_BROKEN",
                        message=f"Link broken: '{raw_target}' not found",
                        severity=Severity.ERROR,
                    )
                )

        return violations


class SchemaValidator:
    def __init__(self, schema_path: str):
        self.schema_path = schema_path
        self._schema, self._load_error = self._load_schema()
        self._validator = None
        if self._schema is not None:
            try:
                self._validator = Draft7Validator(self._schema, format_checker=FormatChecker())
            except Exception as e:
                # jsonschema can raise if the schema itself is invalid; treat as schema invalid.
                self._schema = None
                self._load_error = (
                    "SCHEMA_INVALID",
                    f"Schema is not a valid Draft 7 JSON Schema: {e}",
                )

    def _load_schema(self) -> Tuple[Optional[Dict[str, Any]], Optional[Tuple[str, str]]]:
        try:
            raw = Path(self.schema_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            return None, ("SCHEMA_MISSING", f"Schema file missing at '{self.schema_path}'")
        except (PermissionError, OSError) as e:
            return None, ("SCHEMA_INVALID", f"Schema file could not be read: {e}")

        try:
            schema = json.loads(raw)
        except json.JSONDecodeError as e:
            return None, ("SCHEMA_INVALID", f"Schema file is invalid JSON: {e}")

        try:
            Draft7Validator.check_schema(schema)
        except Exception as e:
            return None, ("SCHEMA_INVALID", f"Schema is not a valid Draft 7 JSON Schema: {e}")

        return schema, None

    def is_ready(self) -> bool:
        return self._validator is not None

    def repository_violation(self) -> Optional[Violation]:
        """
        Return a repository-level schema issue (missing/invalid), suitable for reporting once.
        """
        if self._load_error is None:
            return None

        rule, message = self._load_error
        return Violation(
            file=str(Path(self.schema_path)),
            line=0,
            rule=rule,
            message=message,
            severity=Severity.ERROR,
        )

    def validate_data(self, data: Dict[str, Any]) -> Optional[Violation]:
        # If the schema is missing/invalid, report once at the repository level via
        # `repository_violation()` and skip per-document schema validation to avoid noisy output.
        if self._validator is None:
            return None

        errors: List[str] = []
        for e in self._validator.iter_errors(data):
            field = ""
            if e.path:
                field = ".".join(str(p) for p in e.path)
            elif e.validator == "required" and isinstance(e.instance, dict):
                missing = sorted(set(e.validator_value) - set(e.instance.keys()))
                if missing:
                    field = ",".join(missing)

            if field:
                errors.append(f"{field}: {e.message}")
            else:
                errors.append(e.message)

        if not errors:
            return None

        return Violation(
            file="Metadata Validation",
            line=0,
            rule="SCHEMA_VALIDATION",
            message=f"Schema validation failed: {'; '.join(errors)}",
            severity=Severity.ERROR,
        )


class IdValidator:
    # REPO(3-10)-TYPE(3-10)-SEQ(3)
    # ^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$
    REGEX = re.compile(r"^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$")

    def validate_format(self, document_id: str) -> Optional[Violation]:
        """Checks if ID matches the regex."""
        if not self.REGEX.match(document_id):
            return Violation(
                file=f"ID:{document_id}",  # Context usually provides file
                line=0,
                rule="ID_REGEX",
                message=f"ID '{document_id}' does not match format 'REPO-TYPE-SEQ'",
                severity=Severity.ERROR,
            )
        return None

    def validate_uniqueness(self, document_id: str, existing_ids: Set[str]) -> Optional[Violation]:
        """Checks if ID already exists."""
        if document_id in existing_ids:
            return Violation(
                file=f"ID:{document_id}",
                line=0,
                rule="ID_UNIQUE",
                message=f"ID '{document_id}' is not unique",
                severity=Severity.ERROR,
            )
        return None
