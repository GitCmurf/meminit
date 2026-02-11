import re
from pathlib import Path
from typing import Any, Dict, List, Set

import frontmatter

from meminit.core.domain.entities import Document
from meminit.core.domain.entities import Frontmatter as FM
from meminit.core.domain.entities import Severity, Violation
from meminit.core.services.metadata_normalization import normalize_yaml_scalar_footguns
from meminit.core.services.repo_config import RepoConfig, load_repo_layout
from meminit.core.services.validators import IdValidator, LinkChecker, SchemaValidator


class CheckRepositoryUseCase:
    FILENAME_REGEX = re.compile(r"^[a-z0-9-]+\.md$")
    FILENAME_EXCEPTIONS = {
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "LICENSE.md",
        "LICENCE",
        "LICENCE.md",
        "CODE_OF_CONDUCT.md",
        "CONTRIBUTING.md",
        "SECURITY.md",
        "NOTICE",
        "NOTICE.md",
    }

    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self.root_dir = self._layout.root_dir

        # Initialize Logic Services
        self.id_validator = IdValidator()
        self.link_checker = LinkChecker(str(self.root_dir))

    def execute(self) -> List[Violation]:
        violations: List[Violation] = []
        existing_ids: Set[str] = set()

        schema_issues_seen: set[str] = set()

        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                violations.append(
                    Violation(
                        file=f"{ns.docs_root}/",
                        line=0,
                        rule="REPO_STRUCTURE",
                        message=f"Docs root '{ns.docs_root}/' missing for namespace '{ns.namespace}'",
                        severity=Severity.ERROR,
                    )
                )
                continue

            schema_validator = SchemaValidator(str(ns.schema_file))
            schema_issue = schema_validator.repository_violation()
            if schema_issue and ns.schema_path not in schema_issues_seen:
                schema_issues_seen.add(ns.schema_path)
                schema_issue.file = ns.schema_path
                violations.append(schema_issue)

            for path in ns.docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue
                violations.extend(self._process_document(path, existing_ids, ns, schema_validator))

        return violations

    def _process_document(
        self, path: Path, existing_ids: Set[str], ns: RepoConfig, schema_validator: SchemaValidator
    ) -> List[Violation]:
        violations: List[Violation] = []
        rel_path = str(path.relative_to(self.root_dir))

        # 0. Filename Convention
        if path.name not in self.FILENAME_EXCEPTIONS and not self.FILENAME_REGEX.match(path.name):
            violations.append(
                Violation(
                    file=rel_path,
                    line=0,
                    rule="FILENAME_CONVENTION",
                    message=f"Filename '{path.name}' must be lowercase kebab-case (e.g., my-doc.md)",
                    severity=Severity.WARNING,
                )
            )

        try:
            post = frontmatter.load(path)

            # 1. Frontmatter Check
            if not post.metadata:
                violations.append(
                    Violation(
                        file=rel_path,
                        line=1,
                        rule="FRONTMATTER_MISSING",
                        message="Missing or invalid frontmatter",
                        severity=Severity.ERROR,
                    )
                )
                return violations

            metadata = dict(post.metadata)

            # A. Schema Validation
            if schema_validator.is_ready():
                normalized_for_schema = self._normalize_metadata_for_schema(metadata)
                schema_violation = schema_validator.validate_data(normalized_for_schema)
                if schema_violation:
                    schema_violation.file = rel_path
                    violations.append(schema_violation)

            # B. ID Validation
            violations.extend(self._validate_id(post, rel_path, existing_ids))

            # C. Directory Mapping
            violations.extend(self._check_directory_mapping(post, path, rel_path, ns))

            # D. Link Checking
            violations.extend(self.link_checker.validate_links(rel_path, post.content))

        except Exception as e:
            violations.append(
                Violation(
                    file=rel_path,
                    line=0,
                    rule="UNHANDLED_EXCEPTION",
                    message=str(e),
                    severity=Severity.ERROR,
                )
            )

        return violations

    def _normalize_metadata_for_schema(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        frontmatter+YAML parses some common scalars (e.g. unquoted ISO dates, 2.0) into Python
        types like `datetime.date`/`float`, but our JSON Schema expects strings. Normalize only
        the known YAML-coerced fields (dates and version-like numbers) before validation to
        avoid false positives without masking real type errors (e.g., `title: 123`).
        """
        return normalize_yaml_scalar_footguns(metadata)

    def _validate_id(self, post: Any, rel_path: str, existing_ids: Set[str]) -> List[Violation]:
        violations = []
        doc_id = post.metadata.get("document_id")
        if doc_id:
            v_fmt = self.id_validator.validate_format(doc_id)
            if v_fmt:
                v_fmt.file = rel_path
                violations.append(v_fmt)
            else:
                # Monorepo safety: ensure the ID prefix matches the namespace's configured repo_prefix.
                ns = self._layout.namespace_for_path(self.root_dir / rel_path)
                if ns is not None:
                    expected_prefix = f"{ns.repo_prefix}-"
                    if not str(doc_id).startswith(expected_prefix):
                        violations.append(
                            Violation(
                                file=rel_path,
                                line=0,
                                rule="ID_PREFIX",
                                message=(
                                    f"document_id '{doc_id}' must start with '{ns.repo_prefix}-' for namespace "
                                    f"'{ns.namespace}' ({ns.docs_root}/)"
                                ),
                                severity=Severity.ERROR,
                            )
                        )

            v_uniq = self.id_validator.validate_uniqueness(doc_id, existing_ids)
            if v_uniq:
                v_uniq.file = rel_path
                violations.append(v_uniq)

            existing_ids.add(doc_id)
        return violations

    def _check_directory_mapping(
        self, post: Any, path: Path, rel_path: str, ns: RepoConfig
    ) -> List[Violation]:
        violations = []
        doc_type = post.metadata.get("type")
        if not doc_type:
            return violations

        expected_subdir = ns.expected_subdir_for_type(str(doc_type))
        if not expected_subdir:
            return violations
        if expected_subdir.strip() in {".", ""}:
            return violations

        try:
            rel_to_docs = path.relative_to(ns.docs_dir)
        except ValueError:
            return violations

        expected_parts = Path(expected_subdir).parts
        if rel_to_docs.parts[: len(expected_parts)] != expected_parts:
            violations.append(
                Violation(
                    file=rel_path,
                    line=0,
                    rule="DIRECTORY_MATCH",
                    message=f"Document type '{doc_type}' should be in '{ns.docs_root}/{expected_subdir}'",
                    severity=Severity.WARNING,
                )
            )
        return violations
