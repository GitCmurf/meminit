"""Build or update the repository index with optional state merge, views, and filtering.

Enhancements:
- Merge ``project-state.yaml`` into per-document records (additive only).
- Generate ``catalogue.md`` — table view with composite grouping and activity-recency sort.
- Generate ``kanban.md`` — pure Markdown fallback + HTML kanban board (with CSS hiding).
- Generate ``kanban.css`` — companion stylesheet.
- Filter by ``--status`` and ``--impl-state``.
- Sanitize all user-controlled fields in rendered output.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from queue import Empty, Queue
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, cast

import frontmatter
import yaml

from meminit.core.domain.entities import Severity
from meminit.core.services import graph
from meminit.core.services.diagnostics import canonicalize_advice_list, canonicalize_warning_list
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.index_helpers import build_index_output_data, filter_index_edges
from meminit.core.services.index_cache import CachePlan, IndexCache
from meminit.core.services.index_view import IndexViewService

# Create a singleton instance for use in the module
_index_view_service = IndexViewService()
from meminit.core.services.output_contracts import OUTPUT_SCHEMA_VERSION_V2
from meminit.core.services.path_utils import relative_path_string
from meminit.core.services.project_state import (
    VALID_PRIORITIES,
    ImplState,
    ProjectState,
    get_state_file_rel_path,
    load_project_state,
    validate_project_state,
)
from meminit.core.services.repo_config import DEFAULT_CATALOG_NAME, load_repo_layout
from meminit.core.services.safe_fs import atomic_write, ensure_safe_write_path
from meminit.core.services.safe_yaml import safe_frontmatter_loads
from meminit.core.services.sanitization import (
    MAX_NOTES_LENGTH,
    escape_markdown_table,
    sanitize_field,
    sanitize_html,
    validate_actor,
)
from meminit.core.services.stream_events import (
    StreamingResult,
    StreamItem,
    StreamSummary,
    summary_data,
)
from meminit.core.services.versioning import get_cli_version
from meminit.core.services.warning_codes import WarningCode

MAX_STREAM_QUEUE_SIZE = 500


def _repo_relative_path(path: Path, root_dir: Path) -> str:
    path_text = str(path)
    root_text = str(root_dir).rstrip(os.sep) + os.sep
    if path_text.startswith(root_text):
        return path_text[len(root_text) :].replace(os.sep, "/")
    return relative_path_string(path, root_dir)


def _is_excluded_for_index(path: Path, namespace: Any) -> bool:
    return bool(namespace.is_excluded(path))


def _namespace_for_index_path(
    layout: Any,
    path: Path,
    document_id: str | None,
    *,
    single_namespace: Any | None = None,
) -> Any | None:
    """Resolve the owning namespace and reject namespace-specific exclusions."""
    if single_namespace is not None:
        try:
            path.relative_to(single_namespace.docs_dir)
        except ValueError:
            return None
        if _is_excluded_for_index(path, single_namespace):
            return None
        return single_namespace

    ns = layout.namespace_for_path_and_document_id(path, document_id)
    if ns is None:
        return None
    if _is_excluded_for_index(path, ns):
        return None
    return ns


def _emit_index_stream_items(
    report: Any,
    stream_item_emitter: Callable[[StreamItem], None],
) -> None:
    """Emit index nodes and edges in the same order as the JSON envelope."""
    visible_ids = {node["document_id"] for node in report.documents}
    stream_edges = [
        edge
        for edge in report.edges
        if edge.get("source") in visible_ids and edge.get("target") in visible_ids
    ]
    for node in report.documents:
        stream_item_emitter(StreamItem("node", node))
    for edge in stream_edges:
        stream_item_emitter(StreamItem("edge", edge))


def _json_default(obj: Any) -> str:
    """JSON serializer for date/datetime objects from frontmatter."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _index_cache_context(root_dir: Path) -> Dict[str, Any]:
    state_file_rel = get_state_file_rel_path(root_dir)
    return {
        "meminit_version": get_cli_version(),
        "index_version": "1.0",
        "config_sha256": _optional_sha256(root_dir / "docops.config.yaml"),
        "schema_sha256": _optional_sha256(
            root_dir / "docs" / "00-governance" / "metadata.schema.json"
        ),
        "state_sha256": _optional_sha256(root_dir / state_file_rel),
    }


def _optional_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _normalize_related_ids(value: Any) -> Optional[List[str]]:
    """Ensure related_ids is always a list of strings or None."""
    if value is None:
        return None
    if isinstance(value, str):
        return [value] if value.strip() else None
    if isinstance(value, (list, tuple)):
        return [v.strip() for v in value if isinstance(v, str) and v.strip()]
    return None


def _invalid_priority_doc_ids(state: ProjectState) -> Set[str]:
    """Return state entries that read-query surfaces reject as corrupted."""
    return {
        doc_id
        for doc_id, entry in state.entries.items()
        if entry.priority is not None and entry.priority not in VALID_PRIORITIES
    }


def _state_excluding_invalid_priority_entries(state: ProjectState) -> ProjectState:
    """Return a derivation view that omits entries rejected by read queries."""
    skip_doc_ids = _invalid_priority_doc_ids(state)
    if not skip_doc_ids:
        return state
    return ProjectState(
        entries={
            doc_id: entry for doc_id, entry in state.entries.items() if doc_id not in skip_doc_ids
        },
        schema_violations=state.schema_violations,
        schema_version=state.schema_version,
    )


def _read_warning_severity(severity: str) -> str:
    """Project mutation fatals are warnings on successful read/index paths."""
    return "warning" if severity == "fatal" else severity


def _generated_marker_in_header(contents: str, marker: str) -> bool:
    """Return True when a generated marker is the first non-empty header line.

    Generated index-side Markdown views may include YAML frontmatter. We only
    treat a file as Meminit-generated when the marker appears immediately after
    the optional frontmatter block, before any substantive body content.
    """
    try:
        post = safe_frontmatter_loads(contents)
    except Exception:
        return False

    for line in post.content.splitlines():
        if not line.strip():
            continue
        return line.strip() == marker
    return False


def _remove_stale_artifacts(
    index_dir: Path,
    catalog_name: Optional[str] = None,
    *,
    remove_index: bool = False,
) -> None:
    """Best-effort removal of generated index-side artifacts.

    Only removes Meminit-generated files so that user-managed files
    (e.g. ``README.md``) in the index directory are never touched.
    Filesystem errors are silently swallowed so the caller's structured
    graph diagnostic is never masked.
    """
    known: set[Path] = set()
    if remove_index:
        known.add(index_dir / "meminit.index.json")

    # Fixed generated view files.
    known.add(index_dir / "kanban.md")
    known.add(index_dir / "kanban.css")
    if catalog_name:
        known.add(index_dir / Path(catalog_name).name)

    # Transitional cleanup: discover the catalog filename from a previous
    # successful run that still persisted legacy catalog_path metadata.
    old_index = index_dir / "meminit.index.json"
    try:
        old_data = json.loads(old_index.read_text(encoding="utf-8")).get("data", {})
        old_catalog = old_data.get("catalog_path")
        if isinstance(old_catalog, str) and old_catalog.strip():
            known.add(index_dir / Path(old_catalog).name)
    except (OSError, json.JSONDecodeError, AttributeError):
        pass

    # Marker-based discovery for Meminit-generated Markdown views. This
    # catches historical custom catalog names without touching user files.
    for candidate in index_dir.glob("*.md"):
        try:
            contents = candidate.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(
            _generated_marker_in_header(contents, marker)
            for marker in (
                "<!-- MEMINIT_GENERATED: catalog -->",
                "<!-- MEMINIT_GENERATED: kanban -->",
            )
        ):
            known.add(candidate)

    for path in known:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass


def _build_persisted_index_payload(
    *,
    layout_namespaces: Sequence[Any],
    document_count: int,
    nodes: List[Dict[str, Any]],
    edges: List[Dict[str, Any]],
    warnings: List[Dict[str, Any]],
    advice: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build the stable on-disk index artifact.

    Persisted index files are committed and consumed across environments, so
    runtime-only correlation metadata belongs in CLI JSON output, not here.
    """
    return {
        "output_schema_version": OUTPUT_SCHEMA_VERSION_V2,
        "success": True,
        "command": "index",
        "data": {
            "index_version": "1.0",
            "graph_schema_version": "1.0",
            "node_count": len(nodes),
            "edge_count": len(edges),
            "namespaces": [
                {
                    "namespace": ns.namespace,
                    "docs_root": ns.docs_root,
                    "repo_prefix": ns.repo_prefix,
                }
                for ns in layout_namespaces
            ],
            "document_count": document_count,
            "nodes": nodes,
            "edges": edges,
        },
        "warnings": warnings,
        "violations": [],
        "advice": advice,
    }


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexBuildReport:
    index_path: Path
    document_count: int
    catalog_path: Optional[Path] = None
    kanban_path: Optional[Path] = None
    kanban_css_path: Optional[Path] = None
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    advice: List[Dict[str, Any]] = field(default_factory=list)
    rebuild: Dict[str, Any] = field(default_factory=lambda: {"mode": "full"})


@dataclass(frozen=True)
class _IndexBuildArtifacts:
    """Internal index build artifacts shared by JSON and streaming output."""

    index_path: Path
    document_count: int
    catalog_path: Optional[Path] = None
    kanban_path: Optional[Path] = None
    kanban_css_path: Optional[Path] = None
    warnings: List[Dict[str, Any]] = field(default_factory=list)
    documents: List[Dict[str, Any]] = field(default_factory=list)
    edges: List[Dict[str, Any]] = field(default_factory=list)
    advice: List[Dict[str, Any]] = field(default_factory=list)
    rebuild: Dict[str, Any] = field(default_factory=lambda: {"mode": "full"})

    def to_report(self) -> IndexBuildReport:
        return IndexBuildReport(
            index_path=self.index_path,
            document_count=self.document_count,
            catalog_path=self.catalog_path,
            kanban_path=self.kanban_path,
            kanban_css_path=self.kanban_css_path,
            warnings=self.warnings,
            documents=self.documents,
            edges=self.edges,
            advice=self.advice,
            rebuild=self.rebuild,
        )


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


def _canonicalize_filter(
    raw_values: Optional[str],
    valid_values: Sequence[str],
    flag_name: str,
) -> Optional[List[str]]:
    """Parse and canonicalize a comma-separated filter string.

    Returns None if *raw_values* is None (no filter applied).
    Raises ``MeminitError`` with ``STATE_INVALID_FILTER_VALUE`` for unknown values.
    """
    if not raw_values:
        return None
    result: List[str] = []
    seen: set[str] = set()
    for part in raw_values.split(","):
        part = part.strip()
        if not part:
            continue

        # Normalize underscores to spaces for matching (e.g. IN_PROGRESS -> In Progress)
        normalized_part = part.replace("_", " ").lower()

        matched = None
        for valid in valid_values:
            if valid.lower() == normalized_part:
                matched = valid
                break

        if matched is None:
            raise MeminitError(
                code=ErrorCode.STATE_INVALID_FILTER_VALUE,
                message=f"Unknown {flag_name} value: '{part}'",
                details={
                    "value": part,
                    "valid_values": list(valid_values),
                },
            )

        if matched not in seen:
            result.append(matched)
            seen.add(matched)

    return result or None


VALID_DOC_STATUSES = ["Draft", "In Review", "Approved", "Superseded"]


def _apply_filters(
    entries: List[Dict[str, Any]],
    status_filter: Optional[List[str]],
    impl_state_filter: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Filter entries by governance status and/or impl_state (AND semantics)."""
    result = entries
    if status_filter:
        result = [e for e in result if e.get("status") in status_filter]
    if impl_state_filter:
        result = [e for e in result if e.get("impl_state") in impl_state_filter]
    return result


# ---------------------------------------------------------------------------
# Catalog (table view) generation
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Kanban (board view) generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------


class IndexRepositoryUseCase:
    def __init__(
        self,
        root_dir: str,
        *,
        output_catalog: bool = False,
        catalog_name: Optional[str] = None,
        output_kanban: bool = False,
        status_filter: Optional[str] = None,
        impl_state_filter: Optional[str] = None,
    ):
        self._layout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir
        self._output_catalog = output_catalog
        self._catalog_name = catalog_name or getattr(
            self._layout, "catalog_name", DEFAULT_CATALOG_NAME
        )
        self._output_kanban = output_kanban

        valid_statuses: set[str] = set()
        valid_impl_states: set[str] = set()
        for ns in self._layout.namespaces:
            valid_statuses.update(ns.valid_doc_statuses)
            valid_impl_states.update(ns.valid_impl_states)
        self._valid_statuses = list(valid_statuses)
        self._valid_impl_states = list(valid_impl_states)

        # Parse and canonicalize filters upfront (raises on invalid values).
        self._status_filter = _canonicalize_filter(status_filter, self._valid_statuses, "--status")
        self._impl_state_filter = _canonicalize_filter(
            impl_state_filter, self._valid_impl_states, "--impl-state"
        )

    def execute(self, *, use_cache: bool = True, clear_cache: bool = False) -> IndexBuildReport:
        return self._build_index_artifacts(
            use_cache=use_cache,
            clear_cache=clear_cache,
        ).to_report()

    def _build_index_artifacts(
        self,
        *,
        use_cache: bool = True,
        clear_cache: bool = False,
        stream_item_emitter: Callable[[StreamItem], None] | None = None,
    ) -> _IndexBuildArtifacts:
        any_docs = any(ns.docs_dir.exists() for ns in self._layout.namespaces)
        if not any_docs:
            raise FileNotFoundError("No configured docs roots exist on disk; cannot build index.")

        index_path = self._layout.index_file
        ensure_safe_write_path(root_dir=self._root_dir, target_path=index_path)
        index_path.parent.mkdir(parents=True, exist_ok=True)
        catalog_out_name: Optional[str] = None
        if self._output_catalog:
            if self._catalog_name is None:
                raise RuntimeError("Catalog name was not initialized")
            catalog_out_name = Path(self._catalog_name).name

        index_cache = IndexCache(self._root_dir)
        lock_context = index_cache.acquire_lock() if use_cache or clear_cache else nullcontext()
        try:
            with lock_context:
                return self._execute_locked(
                    index_cache=index_cache,
                    index_path=index_path,
                    catalog_out_name=catalog_out_name,
                    use_cache=use_cache,
                    clear_cache=clear_cache,
                    initial_warnings=[],
                    stream_item_emitter=stream_item_emitter,
                )
        except MeminitError as exc:
            if (
                exc.code not in {ErrorCode.CACHE_LOCK_HELD, ErrorCode.CACHE_WRITE_FAILED}
                or clear_cache
                or not use_cache
            ):
                raise
            warning_code = exc.code.value
            fallback_path = (
                exc.details.get("cache_path") or exc.details.get("lock_path")
                if isinstance(exc.details, dict)
                else ".meminit/cache/index/.lock"
            ) or ".meminit/cache/index/.lock"
            return self._execute_locked(
                index_cache=index_cache,
                index_path=index_path,
                catalog_out_name=catalog_out_name,
                use_cache=False,
                clear_cache=False,
                initial_warnings=[
                    {
                        "code": warning_code,
                        "message": (
                            "Index cache is unavailable; using a full rebuild " "without cache."
                        ),
                        "severity": Severity.WARNING.value,
                        "path": fallback_path,
                    }
                ],
                stream_item_emitter=stream_item_emitter,
            )

    def iter_stream(self, *, use_cache: bool = True, clear_cache: bool = False) -> StreamingResult:
        """Return a core-owned streaming producer for index output."""
        summary = StreamSummary()
        records_queue: Queue[Any] = Queue(maxsize=MAX_STREAM_QUEUE_SIZE)
        build_error: list[BaseException] = []
        sentinel = object()
        cancel_event = threading.Event()

        def emit_stream_item(item: StreamItem) -> None:
            if cancel_event.is_set():
                return
            records_queue.put(item)

        def build_stream_payload() -> None:
            try:
                report = self._build_index_artifacts(
                    use_cache=use_cache,
                    clear_cache=clear_cache,
                    stream_item_emitter=emit_stream_item,
                )
                summary.data = summary_data(
                    build_index_output_data(
                        report,
                        self._root_dir,
                        status_filter=self._status_filter,
                        impl_state_filter=self._impl_state_filter,
                    ),
                    "nodes",
                    "edges",
                )
                summary.warnings = report.warnings
                summary.advice = getattr(report, "advice", [])
            except Exception as exc:  # pragma: no cover - propagated below
                build_error.append(exc)
            finally:
                records_queue.put(sentinel)

        def records():
            thread = threading.Thread(target=build_stream_payload, daemon=True)
            thread.start()
            try:
                while True:
                    record = records_queue.get()
                    if record is sentinel:
                        break
                    yield record
                thread.join()
                if build_error:
                    raise build_error[0]
            finally:
                cancel_event.set()
                if thread.is_alive():
                    try:
                        while True:
                            records_queue.get_nowait()
                    except Empty:
                        pass
                    thread.join()

        return StreamingResult(records=records(), summary=summary)

    def _execute_locked(
        self,
        *,
        index_cache: IndexCache,
        index_path: Path,
        catalog_out_name: Optional[str],
        use_cache: bool,
        clear_cache: bool,
        initial_warnings: List[Dict[str, Any]],
        stream_item_emitter: Callable[[StreamItem], None] | None = None,
    ) -> _IndexBuildArtifacts:
        if clear_cache:
            index_cache.clear()
        _remove_stale_artifacts(
            index_path.parent,
            catalog_name=catalog_out_name,
            remove_index=False,
        )
        warnings_list: List[Dict[str, Any]] = list(initial_warnings)
        cache_context = _index_cache_context(self._root_dir)
        doc_paths = self._discover_document_paths()
        if use_cache:
            cache_plan = index_cache.build_plan(
                doc_paths=doc_paths,
                context=cache_context,
                use_cache=True,
            )
        else:
            cache_plan = CachePlan(mode="disabled")
        if cache_plan.manifest_warning:
            warnings_list.append(cache_plan.manifest_warning)
        cached_report, force_full_rebuild = self._cached_no_change_report(
            index_path, cache_plan, warnings_list
        )
        if cached_report is not None:
            if stream_item_emitter is not None:
                _emit_index_stream_items(cached_report, stream_item_emitter)
            return cached_report
        return self._execute_with_cache_plan(
            cache=index_cache,
            cache_context=cache_context,
            cache_plan=cache_plan,
            cache_rewrites=set(cache_plan.added | cache_plan.changed),
            use_cache=use_cache,
            rebuild_mode="full" if force_full_rebuild else None,
            index_path=index_path,
            catalog_out_name=catalog_out_name,
            warnings_list=warnings_list,
            doc_paths=doc_paths,
            stream_item_emitter=stream_item_emitter,
        )

    def _execute_with_cache_plan(
        self,
        *,
        cache: IndexCache,
        cache_context: Dict[str, Any],
        cache_plan: CachePlan,
        cache_rewrites: set[str],
        use_cache: bool,
        rebuild_mode: str | None,
        index_path: Path,
        catalog_out_name: Optional[str],
        warnings_list: List[Dict[str, Any]],
        doc_paths: Sequence[Path],
        stream_item_emitter: Callable[[StreamItem], None] | None = None,
    ) -> _IndexBuildArtifacts:
        # Load project state (gracefully optional).
        try:
            project_state = load_project_state(self._root_dir)
        except MeminitError as exc:
            project_state = None
            warnings_list.append(
                {
                    "code": exc.code.value,
                    "message": exc.message,
                    "severity": Severity.ERROR.value,
                    "path": get_state_file_rel_path(self._root_dir),
                }
            )

        # Scan governed documents.
        entries: List[Dict[str, Any]] = []
        known_doc_ids: set[str] = set()
        doc_id_paths: Dict[str, List[str]] = {}  # for duplicate detection
        single_namespace = self._layout.namespaces[0] if len(self._layout.namespaces) == 1 else None
        for path in doc_paths:
            cached = self._cached_entry(
                cache,
                cache_plan,
                path,
                warnings_list,
                cache_rewrites,
                single_namespace=single_namespace,
            )
            if cached is not None:
                entries.append(cached)
                doc_id = str(cached.get("document_id", "")).strip()
                rel_path = str(cached.get("path", ""))
                if doc_id:
                    known_doc_ids.add(doc_id)
                    doc_id_paths.setdefault(doc_id, []).append(rel_path)
                continue
            try:
                post = frontmatter.load(path)
            except (
                yaml.YAMLError,
                FileNotFoundError,
                PermissionError,
                IsADirectoryError,
                UnicodeDecodeError,
                OSError,
            ) as err:
                logging.warning("Failed to parse document %s: %s", path, err)
                continue

            doc_id_raw = post.metadata.get("document_id")
            if not isinstance(doc_id_raw, str) or not doc_id_raw.strip():
                continue
            doc_id = doc_id_raw.strip()
            ns = _namespace_for_index_path(
                self._layout,
                path,
                doc_id,
                single_namespace=single_namespace,
            )
            if ns is None:
                continue
            known_doc_ids.add(doc_id)
            rel_path = _repo_relative_path(path, self._root_dir)
            doc_id_paths.setdefault(doc_id, []).append(rel_path)

            entry: Dict[str, Any] = {
                "document_id": doc_id,
                "path": rel_path,
                "namespace": ns.namespace,
                "repo_prefix": ns.repo_prefix,
                "type": post.metadata.get("type"),
                "title": sanitize_field(
                    post.metadata.get("title"), max_length=None, html_escape=True
                ),
                "_raw_title": post.metadata.get("title"),
                "status": post.metadata.get("status"),
                "owner": sanitize_field(
                    post.metadata.get("owner"), max_length=None, html_escape=True
                ),
                "last_updated": post.metadata.get("last_updated"),
                "area": post.metadata.get("area"),
                "description": post.metadata.get("description"),
                "keywords": post.metadata.get("keywords"),
                "superseded_by": post.metadata.get("superseded_by"),
                "related_ids": _normalize_related_ids(post.metadata.get("related_ids")),
            }

            # Merge state (additive — new optional fields).
            state_updated: Optional[datetime] = None
            if project_state:
                state_entry = project_state.get(doc_id)
                if state_entry:
                    resolved_state = ImplState.from_string(state_entry.impl_state)
                    if resolved_state is not None:
                        entry["impl_state"] = resolved_state.value
                    else:
                        entry["impl_state"] = state_entry.impl_state

                    entry["updated"] = state_entry.updated.isoformat()

                    if state_entry.updated_by and validate_actor(state_entry.updated_by):
                        entry["updated_by"] = state_entry.updated_by
                    elif state_entry.updated_by == "":
                        entry[
                            "updated_by"
                        ] = ""  # preserve explicitly empty string if originally there

                    if state_entry.notes is not None:
                        sanitized_notes = sanitize_field(
                            state_entry.notes,
                            max_length=MAX_NOTES_LENGTH,
                            html_escape=True,
                        )
                        if sanitized_notes:
                            entry["notes"] = sanitized_notes
                            entry["_raw_notes"] = state_entry.notes

                    if state_entry.priority is not None:
                        # Intentionally dropped: validate_project_state (called
                        # upstream) emits STATE_INVALID_PRIORITY for invalid
                        # values; we silently omit them from the index entry.
                        if state_entry.priority in VALID_PRIORITIES:
                            entry["priority"] = state_entry.priority
                    if state_entry.depends_on:
                        entry["depends_on"] = list(state_entry.depends_on)
                    if state_entry.blocked_by:
                        entry["blocked_by"] = list(state_entry.blocked_by)
                    if state_entry.assignee is not None:
                        entry["assignee"] = state_entry.assignee
                    if state_entry.next_action is not None:
                        entry["next_action"] = state_entry.next_action

                    state_updated = state_entry.updated

            # Capture body for reference edge extraction (stripped before JSON output).
            entry["_body"] = post.content

            # Compute activity recency (used for sorting, not stored in JSON) - always calculate
            entry["_recency"] = _index_view_service._activity_recency(
                entry.get("last_updated"),
                state_updated,
            )

            entries.append(entry)

        # --- Graph pipeline ---

        # Build path → doc_id map and extract edges.
        path_to_doc_id = {e["path"]: e["document_id"] for e in entries}
        all_edges = graph.build_edge_set(entries, path_to_doc_id, self._root_dir)

        # Run graph integrity validation (checks duplicates, cycles, dangling refs, etc.).
        graph_warnings, graph_advice, graph_fatal = graph.validate_graph_integrity(
            entries,
            all_edges,
            known_doc_ids,
            doc_id_paths,
        )
        if graph_fatal:
            # Invalidate all stale generated artifacts so downstream
            # commands and human readers don't see outputs from a
            # previous successful run while the repo is unindexable.
            index_dir = self._layout.index_file.parent
            _remove_stale_artifacts(
                index_dir,
                catalog_name=catalog_out_name,
                remove_index=True,
            )

            fatal_code_str = graph_fatal[0].get("code", "GRAPH_DUPLICATE_DOCUMENT_ID")
            try:
                fatal_code = ErrorCode(fatal_code_str)
            except ValueError:
                fatal_code = ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID
            raise MeminitError(
                code=fatal_code,
                message=graph_fatal[0]["message"],
                details={"errors": graph_fatal},
            )

        warnings_list.extend(graph_warnings)

        # Validate project state (advisory warnings).
        if project_state:
            validation_issues = validate_project_state(
                project_state, known_doc_ids, self._root_dir, self._valid_impl_states
            )
            for issue in validation_issues:
                w: Dict[str, Any] = {
                    "code": issue.rule,
                    "message": issue.message,
                    "severity": issue.severity.value,
                    "path": issue.file,
                }
                if issue.line:
                    w["line"] = issue.line
                warnings_list.append(w)

            from meminit.core.services.state_derived import (
                check_dependency_cycle,
                check_status_conflicts,
                validate_planning_fields,
            )

            state_path = get_state_file_rel_path(self._root_dir)
            _COVERED_BY_ENTRY_VALIDATORS = {"STATE_INVALID_PRIORITY", "STATE_FIELD_TOO_LONG"}
            for doc_id, ps_entry in project_state.entries.items():
                planning_issues = validate_planning_fields(
                    ps_entry,
                    known_doc_ids,
                )
                for pi in planning_issues:
                    if pi.code in _COVERED_BY_ENTRY_VALIDATORS:
                        continue
                    warnings_list.append(
                        {
                            "code": pi.code,
                            "message": pi.message,
                            "severity": _read_warning_severity(pi.severity),
                            "path": state_path,
                        }
                    )
            cycle_issues = check_dependency_cycle(project_state.entries)
            for ci in cycle_issues:
                warnings_list.append(
                    {
                        "code": ci.code,
                        "message": ci.message,
                        "severity": _read_warning_severity(ci.severity),
                        "path": state_path,
                    }
                )

            for si in check_status_conflicts(project_state.entries):
                graph_advice.append(
                    {
                        "code": si.code,
                        "message": si.message,
                        "severity": si.severity,
                        "path": state_path,
                    }
                )

        # Compute derived fields (ready, open_blockers, unblocks) from state.
        # Spec (PLAN-013 §3.4.1): ready, open_blockers, unblocks are always emitted.
        if project_state and project_state.entries:
            from meminit.core.services.state_derived import compute_derived_fields

            derivation_state = _state_excluding_invalid_priority_entries(project_state)
            invalid_priority_doc_ids = _invalid_priority_doc_ids(project_state)
            derived = compute_derived_fields(derivation_state, known_doc_ids)
            for entry in entries:
                doc_id = str(entry.get("document_id", ""))
                if doc_id in derived:
                    d = derived[doc_id]
                    entry["ready"] = False if doc_id in invalid_priority_doc_ids else d.ready
                    entry["open_blockers"] = list(d.open_blockers)
                    entry["unblocks"] = list(d.unblocks)
                else:
                    entry["ready"] = False
                    entry["open_blockers"] = []
                    entry["unblocks"] = []
        else:
            for entry in entries:
                entry["ready"] = False
                entry["open_blockers"] = []
                entry["unblocks"] = []

        # Apply filters.
        filtered = _apply_filters(entries, self._status_filter, self._impl_state_filter)

        # Write main index JSON (recency/body fields stripped — internal only).
        # Keep canonical JSON unfiltered for downstream commands that depend on
        # full repository inventory (resolve/identify/link). Filters are for
        # command output and generated views only.
        sorted_entries = sorted(entries, key=lambda e: e.get("document_id", ""))
        json_nodes = [{k: v for k, v in e.items() if not k.startswith("_")} for e in sorted_entries]
        json_edges = [e.to_dict() for e in all_edges]

        if use_cache:
            try:
                cache.write(
                    context=cache_context,
                    fingerprints=cache_plan.fingerprints,
                    entries=entries,
                    rewrite_paths=None if cache_plan.mode == "full" else cache_rewrites,
                )
            except MeminitError as cache_exc:
                if cache_exc.code != ErrorCode.CACHE_WRITE_FAILED:
                    raise
                warnings_list.append(
                    {
                        "code": cache_exc.code.value,
                        "message": "Index was built successfully but cache write failed.",
                        "severity": Severity.WARNING.value,
                        "path": (
                            cache_exc.details.get("cache_path", ".meminit/cache/index/")
                            if isinstance(cache_exc.details, dict)
                            else ".meminit/cache/index/"
                        ),
                    }
                )

        canonical_warnings = canonicalize_warning_list(warnings_list)
        canonical_advice = canonicalize_advice_list(graph_advice)

        payload = _build_persisted_index_payload(
            layout_namespaces=self._layout.namespaces,
            document_count=len(json_nodes),
            nodes=json_nodes,
            edges=json_edges,
            warnings=canonical_warnings,
            advice=canonical_advice,
        )
        atomic_write(
            index_path,
            json.dumps(payload, indent=2, default=_json_default, sort_keys=True) + "\n",
            encoding="utf-8",
        )

        generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Generate catalog view (FR-3).
        catalog_path: Optional[Path] = None
        if self._output_catalog:
            if catalog_out_name is None:
                raise RuntimeError("Catalog output name was not initialized")
            catalog_path = index_path.parent / catalog_out_name
            ensure_safe_write_path(root_dir=self._root_dir, target_path=catalog_path)
            catalog_content = _index_view_service.generate_catalog(
                filtered,
                generated_at,
                repo_prefix=self._layout.default_namespace().repo_prefix,
                status_filter=self._status_filter,
                impl_state_filter=self._impl_state_filter,
            )
            atomic_write(catalog_path, catalog_content, encoding="utf-8")

        # Generate kanban.md + kanban.css (FR-4).
        kanban_path: Optional[Path] = None
        kanban_css_path: Optional[Path] = None
        if self._output_kanban:
            kanban_path = index_path.parent / "kanban.md"
            ensure_safe_write_path(root_dir=self._root_dir, target_path=kanban_path)
            kanban_content = _index_view_service.generate_kanban(
                filtered,
                generated_at,
                project_name=self._layout.project_name,
                root_dir=self._root_dir,
                index_dir=index_path.parent,
            )
            atomic_write(kanban_path, kanban_content, encoding="utf-8")

            kanban_css_path = index_path.parent / "kanban.css"
            ensure_safe_write_path(root_dir=self._root_dir, target_path=kanban_css_path)
            atomic_write(kanban_css_path, _index_view_service.get_kanban_css(), encoding="utf-8")

        # Prepare filtered JSON entries for the report/stdout output
        sorted_filtered = sorted(filtered, key=lambda e: e.get("document_id", ""))
        sorted_filtered.sort(
            key=lambda e: e.get("_recency", datetime.min.replace(tzinfo=timezone.utc)),
            reverse=True,
        )
        json_filtered = [
            {k: v for k, v in e.items() if not k.startswith("_")} for e in sorted_filtered
        ]

        rebuild = cache_plan.summary()
        if rebuild_mode is not None:
            rebuild["mode"] = rebuild_mode

        report = _IndexBuildArtifacts(
            index_path=index_path,
            document_count=len(filtered),
            catalog_path=catalog_path,
            kanban_path=kanban_path,
            kanban_css_path=kanban_css_path,
            warnings=canonical_warnings,
            documents=json_filtered,
            edges=json_edges,
            advice=canonical_advice,
            rebuild=rebuild,
        )

        if stream_item_emitter is not None:
            _emit_index_stream_items(report, stream_item_emitter)

        return report

    def _discover_document_paths(self) -> List[Path]:
        paths: set[Path] = set()
        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                continue
            for path in ns.docs_dir.rglob("*.md"):
                if not _is_excluded_for_index(path, ns):
                    paths.add(path)
        return sorted(paths, key=lambda path: _repo_relative_path(path, self._root_dir))

    def _cached_entry(
        self,
        cache: IndexCache,
        cache_plan: CachePlan,
        path: Path,
        warnings_list: List[Dict[str, Any]],
        cache_rewrites: set[str],
        *,
        single_namespace: Any | None = None,
    ) -> Dict[str, Any] | None:
        rel_path = _repo_relative_path(path, self._root_dir)
        if rel_path not in cache_plan.unchanged:
            return None
        fingerprint = cache_plan.fingerprints.get(rel_path)
        if fingerprint is None or not fingerprint.document_id:
            return None
        cached = cache.read_node(fingerprint.document_id)
        if cached is None:
            cache_rewrites.add(rel_path)
            warnings_list.append(
                {
                    "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                    "message": "Cached node entry is invalid; recomputing document.",
                    "severity": Severity.WARNING.value,
                    "path": rel_path,
                }
            )
            return None
        if cached.get("path") != rel_path:
            cache_rewrites.add(rel_path)
            warnings_list.append(
                {
                    "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                    "message": "Cached node path does not match manifest; recomputing document.",
                    "severity": Severity.WARNING.value,
                    "path": rel_path,
                }
            )
            return None
        if cached.get("document_id") != fingerprint.document_id:
            cache_rewrites.add(rel_path)
            warnings_list.append(
                {
                    "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                    "message": "Cached node document_id does not match manifest; recomputing document.",
                    "severity": Severity.WARNING.value,
                    "path": rel_path,
                }
            )
            return None
        cached_doc_id = str(cached.get("document_id", "")).strip()
        if cached_doc_id:
            expected_ns = _namespace_for_index_path(
                self._layout,
                path,
                cached_doc_id,
                single_namespace=single_namespace,
            )
            if expected_ns is None:
                return None
            cached_ns = str(cached.get("namespace", "")).strip().lower()
            if cached_ns != expected_ns.namespace.lower():
                cache_rewrites.add(rel_path)
                warnings_list.append(
                    {
                        "code": ErrorCode.CACHE_ENTRY_INVALID.value,
                        "message": ("Cached node namespace is stale; recomputing document."),
                        "severity": Severity.WARNING.value,
                        "path": rel_path,
                    }
                )
                return None
        recency = cached.get("_recency")
        if isinstance(recency, str):
            try:
                dt = datetime.fromisoformat(recency)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                cached["_recency"] = dt
            except ValueError:
                cached["_recency"] = datetime.min.replace(tzinfo=timezone.utc)
        return cached

    def _cached_no_change_report(
        self,
        index_path: Path,
        cache_plan: CachePlan,
        warnings_list: List[Dict[str, Any]],
    ) -> tuple[_IndexBuildArtifacts | None, bool]:
        if (
            cache_plan.mode != "incremental"
            or cache_plan.added
            or cache_plan.changed
            or cache_plan.removed
            or self._output_catalog
            or self._output_kanban
            or self._status_filter is not None
            or self._impl_state_filter is not None
            or not index_path.is_file()
        ):
            return None, False
        try:
            payload = json.loads(index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None, False
        data = payload.get("data")
        if not isinstance(data, dict):
            return None, False
        nodes = data.get("nodes")
        edges = data.get("edges")
        if not isinstance(nodes, list) or not isinstance(edges, list):
            return None, False
        single_namespace = self._layout.namespaces[0] if len(self._layout.namespaces) == 1 else None
        for node in nodes:
            if not isinstance(node, dict):
                return None, False
            document_id = str(node.get("document_id", "")).strip()
            path_text = str(node.get("path", "")).strip()
            if not document_id or not path_text:
                return None, False
            expected_ns = _namespace_for_index_path(
                self._layout,
                self._root_dir / path_text,
                document_id,
                single_namespace=single_namespace,
            )
            if expected_ns is None:
                return None, False
            cached_ns = str(node.get("namespace", "")).strip().lower()
            if cached_ns != expected_ns.namespace.lower():
                return None, True
        payload_warnings = payload.get("warnings", [])
        if not isinstance(payload_warnings, list):
            payload_warnings = []
        raw_count = data.get("document_count", len(nodes))
        try:
            document_count = int(raw_count)
        except (ValueError, TypeError):
            document_count = len(nodes)
        return (
            _IndexBuildArtifacts(
                index_path=index_path,
                document_count=document_count,
                warnings=canonicalize_warning_list([*payload_warnings, *warnings_list]),
                documents=nodes,
                edges=edges,
                advice=payload.get("advice", []),
                rebuild=cache_plan.summary(),
            ),
            False,
        )
