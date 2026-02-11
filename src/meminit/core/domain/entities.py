from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import List, Optional


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

    # Optional context fields
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
    severity: Severity = Severity.ERROR  # 'error' or 'warning'


@dataclass
class FixAction:
    file: str
    action: str
    description: str


@dataclass
class FixReport:
    fixed_violations: List[FixAction] = field(default_factory=list)
    remaining_violations: List[Violation] = field(default_factory=list)
