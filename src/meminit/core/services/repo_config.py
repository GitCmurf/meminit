from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

import yaml

from meminit.core.services.observability import log_debug

DEFAULT_DOCS_ROOT = "docs"

DEFAULT_TYPE_DIRECTORIES: Dict[str, str] = {
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
    "TESTING": "55-testing",
    "LOG": "58-logs",
    "GUIDE": "60-runbooks",
    "RUNBOOK": "60-runbooks",
    "REF": "70-devex",
    "INDEX": "01-indices",
}


def _derive_repo_prefix(project_name: str) -> str:
    prefix = "".join(c for c in project_name.upper() if "A" <= c <= "Z")
    if len(prefix) < 3:
        return "REPO"
    return prefix[:10]


def _normalize_type_key(doc_type: str) -> str:
    t = str(doc_type).strip().upper()
    if t == "GOVERNANCE":
        return "GOV"
    return t


def _safe_repo_relative_path(root_dir: Path, raw: Any) -> Optional[str]:
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if not raw:
        return None
    p = Path(raw)
    if p.is_absolute():
        return None
    try:
        resolved = (root_dir / p).resolve()
        resolved.relative_to(root_dir.resolve())
    except Exception:
        return None
    return p.as_posix()


def _normalize_type_directories(docs_root: str, raw: Any) -> Dict[str, str]:
    if not isinstance(raw, Mapping):
        return {}

    normalized: Dict[str, str] = {}
    for k, v in raw.items():
        if not isinstance(k, str):
            continue
        if not isinstance(v, str):
            continue
        key = _normalize_type_key(k)
        value = v.strip().replace("\\", "/")
        if not value:
            continue

        value_path = Path(value)
        if value_path.is_absolute():
            continue

        if value.startswith(f"{docs_root}/"):
            value = value[len(docs_root) + 1 :]
        if value.startswith("./"):
            value = value[2:]

        normalized[key] = value

    return normalized


@dataclass(frozen=True)
class RepoConfig:
    root_dir: Path
    namespace: str
    project_name: str
    repo_prefix: str
    docops_version: str
    docs_root: str
    schema_path: str
    excluded_paths: tuple[str, ...]
    excluded_filename_prefixes: tuple[str, ...]
    type_directories: Dict[str, str]
    templates: Dict[str, str]

    @property
    def docs_dir(self) -> Path:
        return self.root_dir / self.docs_root

    @property
    def schema_file(self) -> Path:
        return self.root_dir / self.schema_path

    def is_excluded(self, path: Path) -> bool:
        # Exclude WIP/temporary docs by filename convention (within docs_root only).
        try:
            rel_to_docs = path.relative_to(self.docs_dir)
        except ValueError:
            rel_to_docs = None

        if rel_to_docs is not None:
            for prefix in self.excluded_filename_prefixes:
                prefix_lower = prefix.lower()
                # Exclude if any path component (dir or filename) starts with the prefix, e.g.:
                # docs/05-planning/WIP-foo.md or docs/05-planning/WIP-notes/foo.md
                for part in rel_to_docs.parts:
                    if part.lower().startswith(prefix_lower):
                        return True

        try:
            rel = path.relative_to(self.root_dir)
        except ValueError:
            return False

        rel_parts = rel.parts
        for excluded in self.excluded_paths:
            ex_parts = Path(excluded).parts
            if not ex_parts:
                continue
            if rel_parts[: len(ex_parts)] == ex_parts:
                return True
        return False

    def expected_subdir_for_type(self, doc_type: str) -> Optional[str]:
        key = _normalize_type_key(doc_type)
        return self.type_directories.get(key)


@dataclass(frozen=True)
class RepoLayout:
    root_dir: Path
    project_name: str
    namespaces: tuple[RepoConfig, ...]
    index_path: str

    @property
    def index_file(self) -> Path:
        return self.root_dir / self.index_path

    def get_namespace(self, name: str) -> Optional[RepoConfig]:
        needle = str(name).strip().lower()
        if not needle:
            return None
        for ns in self.namespaces:
            if ns.namespace.lower() == needle:
                return ns
        return None

    def default_namespace(self) -> RepoConfig:
        for ns in self.namespaces:
            if ns.docs_root.strip("/").lower() == DEFAULT_DOCS_ROOT:
                return ns
        return self.namespaces[0]

    def namespace_for_path(self, path: Path) -> Optional[RepoConfig]:
        # Pick the most specific match (longest docs_root) to handle nested docs roots.
        matches: list[tuple[int, RepoConfig]] = []
        for ns in self.namespaces:
            try:
                path.relative_to(ns.docs_dir)
            except ValueError:
                continue
            matches.append((len(Path(ns.docs_root).parts), ns))
        if not matches:
            return None
        matches.sort(key=lambda t: t[0], reverse=True)
        return matches[0][1]


def _normalize_string_list(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append(item.strip())
    return out


def _build_namespace_config(
    *,
    root: Path,
    project_name: str,
    raw_namespace: Mapping[str, Any],
    defaults: Mapping[str, Any],
) -> Optional[RepoConfig]:
    namespace_name = str(raw_namespace.get("name") or "").strip() or str(
        defaults.get("namespace") or "default"
    )

    repo_prefix_raw = raw_namespace.get("repo_prefix", defaults.get("repo_prefix"))
    if isinstance(repo_prefix_raw, str) and repo_prefix_raw.strip():
        repo_prefix_norm = repo_prefix_raw.strip().upper()
    else:
        repo_prefix_norm = _derive_repo_prefix(project_name)

    docops_version_raw = raw_namespace.get("docops_version", defaults.get("docops_version"))
    if isinstance(docops_version_raw, (int, float)) and not isinstance(docops_version_raw, bool):
        docops_version_norm = str(docops_version_raw)
    elif isinstance(docops_version_raw, str) and docops_version_raw.strip():
        docops_version_norm = docops_version_raw.strip()
    else:
        docops_version_norm = "2.0"

    docs_root_raw = raw_namespace.get("docs_root", defaults.get("docs_root"))
    docs_root = (
        _safe_repo_relative_path(root, docs_root_raw)
        if docs_root_raw is not None
        else DEFAULT_DOCS_ROOT
    )
    docs_root_norm = docs_root or DEFAULT_DOCS_ROOT

    schema_path_raw = raw_namespace.get("schema_path", defaults.get("schema_path"))
    schema_path = (
        _safe_repo_relative_path(root, schema_path_raw)
        if schema_path_raw is not None
        else f"{docs_root_norm}/00-governance/metadata.schema.json"
    )
    schema_path_norm = schema_path or f"{docs_root_norm}/00-governance/metadata.schema.json"

    excluded_paths: list[str] = []
    for item in _normalize_string_list(defaults.get("excluded_paths")):
        normalized = _safe_repo_relative_path(root, item)
        if normalized:
            excluded_paths.append(normalized)
    for item in _normalize_string_list(raw_namespace.get("excluded_paths")):
        normalized = _safe_repo_relative_path(root, item)
        if normalized:
            excluded_paths.append(normalized)

    default_excluded = f"{docs_root_norm}/00-governance/templates"
    if default_excluded not in excluded_paths:
        excluded_paths.append(default_excluded)

    excluded_filename_prefixes: list[str] = []
    excluded_filename_prefixes.extend(
        _normalize_string_list(defaults.get("excluded_filename_prefixes"))
    )
    excluded_filename_prefixes.extend(
        _normalize_string_list(raw_namespace.get("excluded_filename_prefixes"))
    )
    if "WIP-" not in excluded_filename_prefixes:
        excluded_filename_prefixes.append("WIP-")

    type_directories = dict(DEFAULT_TYPE_DIRECTORIES)
    type_directories.update(
        _normalize_type_directories(docs_root_norm, defaults.get("type_directories"))
    )
    type_directories.update(
        _normalize_type_directories(docs_root_norm, raw_namespace.get("type_directories"))
    )

    templates: Dict[str, str] = {}
    for raw_templates in (defaults.get("templates"), raw_namespace.get("templates")):
        if not isinstance(raw_templates, Mapping):
            continue
        for k, v in raw_templates.items():
            if not isinstance(k, str):
                continue
            key = _normalize_type_key(k).lower()
            normalized = _safe_repo_relative_path(root, v)
            if normalized:
                templates[key] = normalized

    return RepoConfig(
        root_dir=root,
        namespace=namespace_name,
        project_name=project_name,
        repo_prefix=repo_prefix_norm,
        docops_version=docops_version_norm,
        docs_root=docs_root_norm,
        schema_path=schema_path_norm,
        excluded_paths=tuple(excluded_paths),
        excluded_filename_prefixes=tuple(excluded_filename_prefixes),
        type_directories=type_directories,
        templates=templates,
    )


def load_repo_layout(root_dir: str | Path) -> RepoLayout:
    root = Path(root_dir).resolve()
    config_path = root / "docops.config.yaml"

    data: Dict[str, Any] = {}
    load_error: str | None = None
    if config_path.exists():
        try:
            data = yaml.safe_load(config_path.read_text()) or {}
        except Exception as exc:
            load_error = str(exc)
            data = {}
    log_debug(
        operation="debug.config_loaded",
        details={
            "config_path": str(config_path),
            "exists": config_path.exists(),
            "loaded": config_path.exists() and load_error is None,
            "error": load_error,
        },
    )

    project_name = str(data.get("project_name") or root.name).strip() or root.name

    defaults: Dict[str, Any] = dict(data)
    defaults.setdefault("docs_root", DEFAULT_DOCS_ROOT)
    defaults.setdefault("namespace", "default")

    namespaces: list[RepoConfig] = []
    raw_namespaces = data.get("namespaces")
    if isinstance(raw_namespaces, Sequence) and not isinstance(raw_namespaces, (str, bytes)):
        for i, item in enumerate(raw_namespaces):
            if not isinstance(item, Mapping):
                continue
            ns_defaults = dict(defaults)
            ns_defaults["namespace"] = f"ns{i+1}"
            ns = _build_namespace_config(
                root=root, project_name=project_name, raw_namespace=item, defaults=ns_defaults
            )
            if ns:
                namespaces.append(ns)

    if not namespaces:
        ns = _build_namespace_config(
            root=root,
            project_name=project_name,
            raw_namespace=data,
            defaults=defaults,
        )
        if ns is None:
            raise ValueError("Failed to load repository configuration.")
        namespaces = [ns]

    index_path_raw = data.get("index_path")
    index_path = (
        _safe_repo_relative_path(root, index_path_raw) if index_path_raw is not None else None
    )
    if not index_path:
        chosen = None
        for ns in namespaces:
            if ns.docs_root.strip("/").lower() == DEFAULT_DOCS_ROOT:
                chosen = ns
                break
        if chosen is None:
            chosen = namespaces[0]
        index_path = f"{chosen.docs_root}/01-indices/meminit.index.json"

    return RepoLayout(
        root_dir=root,
        project_name=project_name,
        namespaces=tuple(namespaces),
        index_path=index_path,
    )


def load_repo_config(root_dir: str | Path) -> RepoConfig:
    # Backwards compatible helper: returns the default namespace config.
    return load_repo_layout(root_dir).default_namespace()
