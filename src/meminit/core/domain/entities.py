from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Frontmatter:
    document_id: str
    type: str
    title: str
    status: str
    version: str
    last_updated: date
    docops_version: str
    owner: str

    area: Optional[str] = None
    description: Optional[str] = None
    template_type: Optional[str] = None
    template_version: Optional[str] = None
    keywords: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    superseded_by: Optional[str] = None
    related_ids: Optional[List[str]] = None


@dataclass
class Document:
    path: str
    frontmatter: Frontmatter
    body: str


@dataclass
class Violation:
    file: str
    line: int
    rule: str
    message: str
    severity: Severity = Severity.ERROR


@dataclass
class FixAction:
    file: str
    action: str
    description: str


@dataclass
class FixReport:
    fixed_violations: List[FixAction] = field(default_factory=list)
    remaining_violations: List[Violation] = field(default_factory=list)


@dataclass
class NewDocumentParams:
    r"""Parameters for creating a new governed document.

    Attributes:
        doc_type: The document type (e.g., 'ADR', 'RFC', 'GOV'). Used to determine
            the target directory and ID type segment.
        title: The document title. Used for filename generation and frontmatter.
        namespace: Optional namespace override. If not provided, uses the default
            namespace from repo configuration.
        owner: Optional owner override. If not provided, resolved via precedence:
            CLI arg > MEMINIT_DEFAULT_OWNER env var > docops.config.yaml > '__TBD__'.
        area: Optional area/classification for the document (e.g., 'security', 'api').
        description: Optional brief description of the document's purpose.
        status: Document lifecycle status. Defaults to 'Draft'. Valid values:
            'Draft', 'In Review', 'Approved', 'Superseded'.
        keywords: Optional list of keywords for search and categorization.
        related_ids: Optional list of related document IDs (must match pattern
            ^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$).
        document_id: Optional explicit document ID. If provided, must match the
            doc_type in its type segment.
        dry_run: If True, validates and returns result without writing the file.
        verbose: If True, emit decision reasoning for ID allocation and owner resolution.
    """

    doc_type: str
    title: str
    namespace: Optional[str] = None
    owner: Optional[str] = None
    area: Optional[str] = None
    description: Optional[str] = None
    status: str = "Draft"
    keywords: Optional[List[str]] = None
    related_ids: Optional[List[str]] = None
    document_id: Optional[str] = None
    dry_run: bool = False
    verbose: bool = False


@dataclass
class NewDocumentResult:
    """Result of a new document creation request.

    Attributes:
        success: True if the document was created (or would be created in dry_run).
        path: Absolute path where the document was (or would be) written.
        document_id: The generated or provided document ID (e.g., 'MEMINIT-ADR-042').
        doc_type: Normalized document type used for creation.
        title: The document title.
        status: The document's lifecycle status.
        version: Document version string (defaults to '0.1' for new documents).
        owner: Resolved owner value after applying precedence chain.
        area: Optional area/classification, if provided.
        last_updated: ISO date string of the document's last update.
        docops_version: DocOps schema version used for the document.
        description: Optional description, if provided.
        keywords: Optional keywords list, if provided.
        related_ids: Optional related document IDs, if provided.
        dry_run: True if this was a dry_run (no file written).
        content: The full document content (only populated in dry_run mode).
        error: Exception or MeminitError if success is False, None otherwise.
        reasoning: Optional list of decision reasoning entries (F3.3/F2.8).
    """

    success: bool
    path: Optional[Path] = None
    document_id: Optional[str] = None
    doc_type: Optional[str] = None
    title: Optional[str] = None
    status: Optional[str] = None
    version: Optional[str] = None
    owner: Optional[str] = None
    area: Optional[str] = None
    last_updated: Optional[str] = None
    docops_version: Optional[str] = None
    description: Optional[str] = None
    keywords: Optional[List[str]] = None
    related_ids: Optional[List[str]] = None
    dry_run: bool = False
    content: Optional[str] = None
    error: Optional[Any] = None
    reasoning: Optional[List[Dict[str, Any]]] = None


@dataclass
class CheckResult:
    """Result of a repository compliance check.

    Attributes:
        success: True if all checked files passed (no errors). Warnings do not
            affect success status.
        files_checked: Total number of markdown files that were validated.
        files_passed: Number of files with no errors (may have warnings).
        files_failed: Number of files with one or more error-level violations.
        violations: List of error-level violations, grouped by file path.
            Each entry contains 'path' and 'violations' keys.
        warnings: List of warning-level issues, grouped by file path.
            Each entry contains 'path' and 'warnings' keys.
    """

    success: bool
    files_checked: int
    files_passed: int
    files_failed: int
    violations: List[Dict[str, Any]] = field(default_factory=list)
    warnings: List[Dict[str, Any]] = field(default_factory=list)
