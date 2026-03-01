import glob
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import frontmatter

from meminit.core.domain.entities import CheckResult, Document
from meminit.core.domain.entities import Frontmatter as FM
from meminit.core.domain.entities import Severity, Violation
from meminit.core.services.error_codes import ErrorCode, MeminitError
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

    def execute_targeted(self, paths: List[str], strict: bool = False) -> CheckResult:
        """Validate specific files with structured result.

        Args:
            paths: List of file paths (relative or absolute, can include globs)
            strict: If True, treat warnings as errors

        Returns:
            CheckResult with per-file violations

        Raises:
            MeminitError: If a path escapes the repository root (PATH_ESCAPE)
                          If single path not found (FILE_NOT_FOUND)
        """
        all_files: List[Path] = []
        not_found_patterns: List[str] = []
        schema_issues_seen: Set[str] = set()
        schema_validators: Dict[str, SchemaValidator] = {}

        root_resolved = self.root_dir.resolve()

        for pattern in paths:
            pattern_path = Path(pattern)
            if pattern_path.is_absolute():
                candidate = pattern_path
            else:
                candidate = self.root_dir / pattern_path
            try:
                candidate.resolve().relative_to(root_resolved)
            except (ValueError, OSError):
                raise MeminitError(
                    code=ErrorCode.PATH_ESCAPE,
                    message=f"Path '{pattern}' is outside repository root",
                    details={"path": pattern},
                )

            if pattern_path.is_absolute():
                matches = glob.glob(pattern, recursive=True)
            else:
                matches = glob.glob(str(self.root_dir / pattern), recursive=True)

            if not matches:
                resolved = Path(pattern)
                if not resolved.is_absolute():
                    resolved = self.root_dir / pattern
                if not resolved.exists():
                    not_found_patterns.append(pattern)

            for match in matches:
                p = Path(match)
                if p.is_dir():
                    for nested in p.rglob("*.md"):
                        if nested.is_file():
                            all_files.append(nested)
                    continue
                if p.is_file() and p.suffix == ".md":
                    all_files.append(p)

        seen = set()
        unique_files = []
        for f in all_files:
            key = str(f.resolve())
            if key not in seen:
                seen.add(key)
                unique_files.append(f)

        if len(paths) == 1 and not unique_files and not_found_patterns:
            pattern = not_found_patterns[0]
            raise MeminitError(
                code=ErrorCode.FILE_NOT_FOUND,
                message=f"File not found: {pattern}",
                details={"path": pattern},
            )

        violations_by_file: Dict[str, Dict[str, Any]] = {}
        warnings_by_file: Dict[str, Dict[str, Any]] = {}
        files_passed = 0
        files_failed = 0
        files_checked = 0
        schema_failures = 0
        files_outside_docs_root_count = 0
        checked_paths: List[str] = []

        existing_ids: Set[str] = set()

        for ns in self._layout.namespaces:
            schema_validator = SchemaValidator(str(ns.schema_file))
            schema_validators[ns.schema_path] = schema_validator
            schema_issue = schema_validator.repository_violation()
            if schema_issue and ns.schema_path not in schema_issues_seen:
                schema_issues_seen.add(ns.schema_path)
                schema_issue.file = ns.schema_path
                path_str = schema_issue.file
                checked_paths.append(path_str)
                violations_by_file[path_str] = {
                    "path": path_str,
                    "violations": [
                        {
                            "code": schema_issue.rule,
                            "message": schema_issue.message,
                            "line": schema_issue.line,
                        }
                    ],
                }
                schema_failures += 1

        for pattern in not_found_patterns:
            path_str = pattern
            checked_paths.append(path_str)
            violations_by_file[path_str] = {
                "path": path_str,
                "violations": [
                    {
                        "code": ErrorCode.FILE_NOT_FOUND.value,
                        "message": f"File not found: {pattern}",
                    }
                ],
            }

        for file_path in unique_files:
            try:
                canonical_path = file_path.resolve()
                canonical_path.relative_to(root_resolved)
            except (ValueError, OSError):
                path_str = str(file_path)
                raise MeminitError(
                    code=ErrorCode.PATH_ESCAPE,
                    message=f"Path '{path_str}' is outside repository root",
                    details={"path": path_str},
                )

            rel_path = canonical_path.relative_to(root_resolved).as_posix()

            ns = self._layout.namespace_for_path(canonical_path)
            if ns is not None and ns.is_excluded(canonical_path):
                continue

            checked_paths.append(rel_path)
            files_checked += 1

            if ns is None:
                files_outside_docs_root_count += 1
                if strict:
                    violations_by_file[rel_path] = {
                        "path": rel_path,
                        "violations": [
                            {
                                "code": ErrorCode.OUTSIDE_DOCS_ROOT.value,
                                "message": f"File '{rel_path}' is outside configured docs root",
                            }
                        ],
                    }
                    files_failed += 1
                else:
                    warnings_by_file[rel_path] = {
                        "path": rel_path,
                        "warnings": [
                            {
                                "code": ErrorCode.OUTSIDE_DOCS_ROOT.value,
                                "message": f"File '{rel_path}' is outside configured docs root",
                            }
                        ],
                    }
                    files_passed += 1
                continue

            schema_validator = schema_validators.get(ns.schema_path) or SchemaValidator(
                str(ns.schema_file)
            )
            file_violations = self._process_document(
                canonical_path, existing_ids, ns, schema_validator
            )

            document_id = self._extract_document_id(canonical_path)

            if file_violations:
                errors = [v for v in file_violations if v.severity == Severity.ERROR]
                warnings = [v for v in file_violations if v.severity == Severity.WARNING]

                if strict and warnings:
                    errors = list(file_violations)
                    warnings = []

                if errors:
                    files_failed += 1
                    file_entry: Dict[str, Any] = {
                        "path": rel_path,
                        "violations": [
                            {"code": v.rule, "message": v.message, "line": v.line} for v in errors
                        ],
                    }
                    if document_id:
                        file_entry["document_id"] = document_id
                    violations_by_file[rel_path] = file_entry
                else:
                    files_passed += 1

                if warnings:
                    warnings_by_file[rel_path] = {
                        "path": rel_path,
                        "warnings": [
                            {"code": v.rule, "message": v.message, "line": v.line} for v in warnings
                        ],
                    }
            else:
                files_passed += 1

        all_violations = sorted(violations_by_file.values(), key=lambda x: x["path"])
        all_warnings = sorted(warnings_by_file.values(), key=lambda x: x["path"])
        warnings_count = self._count_grouped_issues(all_warnings, "warnings")
        violations_count = self._count_grouped_issues(all_violations, "violations")
        checked_paths_sorted = sorted(set(checked_paths))

        success = (
            files_failed == 0
            and len(not_found_patterns) == 0
            and schema_failures == 0
            and not (strict and warnings_count > 0)
        )

        return CheckResult(
            success=success,
            files_checked=files_checked,
            files_passed=files_passed,
            files_failed=files_failed,
            missing_paths_count=len(not_found_patterns),
            schema_failures_count=schema_failures,
            warnings_count=warnings_count,
            violations_count=violations_count,
            files_with_warnings=len(all_warnings),
            files_outside_docs_root_count=files_outside_docs_root_count,
            checked_paths_count=len(checked_paths_sorted),
            violations=all_violations,
            warnings=all_warnings,
            checked_paths=checked_paths_sorted,
        )

    def execute_full_summary(self, strict: bool = False) -> CheckResult:
        """Validate all governed docs and return aggregate counters for JSON reporting."""
        violations_by_file: Dict[str, Dict[str, Any]] = {}
        warnings_by_file: Dict[str, Dict[str, Any]] = {}
        existing_ids: Set[str] = set()
        schema_issues_seen: set[str] = set()
        files_passed = 0
        files_failed = 0
        checked_paths: List[str] = []
        files_checked = 0
        schema_failures = 0
        repo_level_failures = 0

        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                path_str = f"{ns.docs_root}/"
                checked_paths.append(path_str)
                violations_by_file[path_str] = {
                    "path": path_str,
                    "violations": [
                        {
                            "code": "REPO_STRUCTURE",
                            "message": f"Docs root '{ns.docs_root}/' missing for namespace '{ns.namespace}'",
                            "line": 0,
                        }
                    ],
                }
                repo_level_failures += 1
                continue

            schema_validator = SchemaValidator(str(ns.schema_file))
            schema_issue = schema_validator.repository_violation()
            if schema_issue and ns.schema_path not in schema_issues_seen:
                schema_issues_seen.add(ns.schema_path)
                schema_issue.file = ns.schema_path
                path_str = ns.schema_path
                checked_paths.append(path_str)
                violations_by_file[path_str] = {
                    "path": path_str,
                    "violations": [
                        {
                            "code": schema_issue.rule,
                            "message": schema_issue.message,
                            "line": schema_issue.line,
                        }
                    ],
                }
                schema_failures += 1
                repo_level_failures += 1

            for path in ns.docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue

                files_checked += 1
                rel_path = path.relative_to(self.root_dir).as_posix()
                checked_paths.append(rel_path)
                file_violations = self._process_document(path, existing_ids, ns, schema_validator)

                document_id = self._extract_document_id(path)
                errors = [v for v in file_violations if v.severity == Severity.ERROR]
                warnings = [v for v in file_violations if v.severity == Severity.WARNING]
                if strict and warnings:
                    errors = list(file_violations)
                    warnings = []

                if errors:
                    files_failed += 1
                    entry: Dict[str, Any] = {
                        "path": rel_path,
                        "violations": [
                            {"code": v.rule, "message": v.message, "line": v.line} for v in errors
                        ],
                    }
                    if document_id:
                        entry["document_id"] = document_id
                    violations_by_file[rel_path] = entry
                else:
                    files_passed += 1

                if warnings:
                    warnings_by_file[rel_path] = {
                        "path": rel_path,
                        "warnings": [
                            {"code": v.rule, "message": v.message, "line": v.line} for v in warnings
                        ],
                    }

        all_violations = sorted(violations_by_file.values(), key=lambda x: x["path"])
        all_warnings = sorted(warnings_by_file.values(), key=lambda x: x["path"])
        warnings_count = self._count_grouped_issues(all_warnings, "warnings")
        violations_count = self._count_grouped_issues(all_violations, "violations")
        checked_paths_sorted = sorted(set(checked_paths))

        success = (
            files_failed == 0 and repo_level_failures == 0 and not (strict and warnings_count > 0)
        )

        return CheckResult(
            success=success,
            files_checked=files_checked,
            files_passed=files_passed,
            files_failed=files_failed,
            missing_paths_count=0,
            schema_failures_count=schema_failures,
            warnings_count=warnings_count,
            violations_count=violations_count,
            files_with_warnings=len(all_warnings),
            files_outside_docs_root_count=0,
            checked_paths_count=len(checked_paths_sorted),
            violations=all_violations,
            warnings=all_warnings,
            checked_paths=checked_paths_sorted,
        )

    def _count_grouped_issues(self, grouped: List[Dict[str, Any]], key: str) -> int:
        return sum(len(item.get(key, [])) for item in grouped)

    def _extract_document_id(self, path: Path) -> Optional[str]:
        """Extract document_id from a file's frontmatter.

        Args:
            path: Absolute path to the document file.

        Returns:
            The document_id string if present, None otherwise.
        """
        try:
            post = frontmatter.load(str(path))
            if post.metadata:
                doc_id = post.metadata.get("document_id")
                if doc_id:
                    return str(doc_id)
        except Exception:
            pass
        return None

    def _process_document(
        self,
        path: Path,
        existing_ids: Set[str],
        ns: RepoConfig,
        schema_validator: SchemaValidator,
    ) -> List[Violation]:
        """Process a single document and collect all validation violations.

        Validation steps performed:
        1. Filename convention check (lowercase kebab-case, with exceptions)
        2. Frontmatter presence and validity check
        3. JSON Schema validation against namespace metadata schema
        4. Document ID format, prefix, and uniqueness validation
        5. Directory mapping check (type-to-subdirectory alignment)
        6. Link validation (internal and external references)

        Args:
            path: Absolute path to the document file.
            existing_ids: Set of document IDs seen so far (for uniqueness check).
            ns: Namespace configuration for the document's location.
            schema_validator: Validator for the namespace's JSON schema.

        Returns:
            List of violations found for this document. Empty if fully compliant.
        """
        violations: List[Violation] = []
        rel_path = path.relative_to(self.root_dir).as_posix()

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
            post = frontmatter.load(str(path))

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

            if schema_validator.is_ready():
                normalized_for_schema = self._normalize_metadata_for_schema(metadata)
                schema_violation = schema_validator.validate_data(normalized_for_schema)
                if schema_violation:
                    schema_violation.file = rel_path
                    violations.append(schema_violation)

            violations.extend(self._validate_id(post, rel_path, existing_ids))

            violations.extend(self._check_directory_mapping(post, path, rel_path, ns))

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
        """Normalize metadata values to match JSON Schema expectations.

        YAML frontmatter parsing can coerce certain values to native Python types
        that don't match the JSON Schema string expectations:
        - ISO dates (e.g., '2024-01-15') become datetime.date objects
        - Version-like numbers (e.g., '2.0') become float

        This method normalizes only these known problematic fields to avoid
        false-positive schema validation errors while preserving actual type
        mismatches (e.g., 'title: 123' remains as-is).

        Args:
            metadata: Raw metadata dictionary from frontmatter parsing.

        Returns:
            Normalized metadata dictionary suitable for JSON Schema validation.
        """
        return normalize_yaml_scalar_footguns(metadata)

    def _validate_id(self, post: Any, rel_path: str, existing_ids: Set[str]) -> List[Violation]:
        r"""Validate a document's ID for format, prefix, and uniqueness.

        Validation steps:
        1. Format check: ID must match pattern ^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$
        2. Prefix check: ID must start with the namespace's repo_prefix
        3. Uniqueness check: ID must not have been seen in this run

        Args:
            post: python-frontmatter Post object with metadata.
            rel_path: Relative path from repository root (for violation reporting).
            existing_ids: Set of IDs already encountered (mutated to add this ID).

        Returns:
            List of violations found. Empty if ID is valid or absent.
        """
        violations = []
        doc_id = post.metadata.get("document_id")
        if doc_id:
            v_fmt = self.id_validator.validate_format(doc_id)
            if v_fmt:
                v_fmt.file = rel_path
                violations.append(v_fmt)
            else:
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
        """Check that a document is in the expected directory for its type.

        The namespace configuration defines mappings from document types to
        expected subdirectories (e.g., 'ADR' -> 'adr/'). This validates that
        documents are placed in their designated locations.

        The check is skipped if:
        - The document has no 'type' field
        - The type has no configured directory mapping
        - The expected directory is '.' or '' (current directory, i.e., no constraint)
        - The document is outside the docs root

        Args:
            post: python-frontmatter Post object with metadata.
            path: Absolute path to the document file.
            rel_path: Relative path from repository root (for violation reporting).
            ns: Namespace configuration containing type-to-directory mappings.

        Returns:
            List containing a WARNING violation if directory mismatch, else empty.
        """
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
