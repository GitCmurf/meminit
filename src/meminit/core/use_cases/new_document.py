import errno
import os
import re
import sys
import tempfile
import time
import warnings
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import frontmatter
import yaml

from meminit.core.domain.entities import NewDocumentParams, NewDocumentResult
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.metadata_normalization import normalize_yaml_scalar_footguns
from meminit.core.services.observability import get_current_run_id, log_debug, log_operation
from meminit.core.services.repo_config import RepoConfig, load_repo_config, load_repo_layout
from meminit.core.services.safe_fs import ensure_safe_write_path
from meminit.core.services.validators import SchemaValidator

try:
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows or unsupported platforms
    fcntl = None

ALLOWED_STATUSES = ["Draft", "In Review", "Approved", "Superseded"]
RELATED_ID_PATTERN = re.compile(r"^[A-Z]{3,10}-[A-Z]{3,10}-\d{3}$")


class NewDocumentUseCase:
    def __init__(self, root_dir: str):
        self._layout = load_repo_layout(root_dir)
        self.root_dir = self._layout.root_dir

    def execute(
        self,
        doc_type: str,
        title: str,
        namespace: Optional[str] = None,
    ) -> Path:
        params = NewDocumentParams(doc_type=doc_type, title=title, namespace=namespace)
        result = self.execute_with_params(params)
        if not result.success:
            if result.error:
                if isinstance(result.error, MeminitError):
                    if result.error.code == ErrorCode.UNKNOWN_TYPE:
                        raise ValueError(result.error.message)
                    if result.error.code == ErrorCode.UNKNOWN_NAMESPACE:
                        raise ValueError(result.error.message)
                    if result.error.code == ErrorCode.DUPLICATE_ID:
                        raise FileExistsError(result.error.message)
                raise result.error
            raise RuntimeError("Document creation failed")
        return result.path

    def execute_with_params(self, params: NewDocumentParams) -> NewDocumentResult:
        try:
            return self._execute_internal(params)
        except MeminitError as e:
            return NewDocumentResult(
                success=False,
                doc_type=params.doc_type,
                title=params.title,
                status=params.status,
                owner=params.owner,
                area=params.area,
                description=params.description,
                keywords=params.keywords,
                related_ids=params.related_ids,
                superseded_by=params.superseded_by,
                dry_run=params.dry_run,
                error=e,
            )
        except Exception as e:
            return NewDocumentResult(
                success=False,
                doc_type=params.doc_type,
                title=params.title,
                status=params.status,
                owner=params.owner,
                area=params.area,
                description=params.description,
                keywords=params.keywords,
                related_ids=params.related_ids,
                superseded_by=params.superseded_by,
                dry_run=params.dry_run,
                error=e,
            )

    def _execute_internal(self, params: NewDocumentParams) -> NewDocumentResult:
        reasoning: Optional[List[Dict[str, Any]]] = [] if params.verbose else None

        with log_operation(
            operation="document_create",
            details={"doc_type": params.doc_type, "title": params.title},
            run_id=get_current_run_id(),
        ) as ctx:
            return self._execute_internal_impl(params, reasoning, ctx)

    def _execute_internal_impl(
        self,
        params: NewDocumentParams,
        reasoning: Optional[List[Dict[str, Any]]],
        ctx: Dict[str, Any],
    ) -> NewDocumentResult:
        if params.related_ids:
            seen = set()
            unique_related_ids = []
            for rid in params.related_ids:
                if rid not in seen:
                    seen.add(rid)
                    unique_related_ids.append(rid)
            params = NewDocumentParams(
                doc_type=params.doc_type,
                title=params.title,
                namespace=params.namespace,
                owner=params.owner,
                area=params.area,
                description=params.description,
                status=params.status,
                keywords=params.keywords,
                related_ids=unique_related_ids if unique_related_ids else None,
                superseded_by=params.superseded_by,
                document_id=params.document_id,
                dry_run=params.dry_run,
                verbose=params.verbose,
            )

        if params.status not in ALLOWED_STATUSES:
            raise MeminitError(
                code=ErrorCode.INVALID_STATUS,
                message=f"Invalid status '{params.status}'. Allowed values: {ALLOWED_STATUSES}",
                details={"status": params.status, "allowed": ALLOWED_STATUSES},
            )

        if params.status == "Superseded" and not params.superseded_by:
            warnings.warn(
                "Document status is 'Superseded'. "
                "Consider adding 'superseded_by' field to indicate the replacement document.",
                UserWarning,
            )

        if params.superseded_by:
            if not RELATED_ID_PATTERN.match(params.superseded_by):
                raise MeminitError(
                    code=ErrorCode.INVALID_RELATED_ID,
                    message=f"Invalid superseded_by '{params.superseded_by}'. Must match pattern: ^[A-Z]{{3,10}}-[A-Z]{{3,10}}-\\d{{3}}$",
                    details={
                        "superseded_by": params.superseded_by,
                        "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\d{3}$",
                    },
                )

        if params.related_ids:
            for rid in params.related_ids:
                if not RELATED_ID_PATTERN.match(rid):
                    raise MeminitError(
                        code=ErrorCode.INVALID_RELATED_ID,
                        message=f"Invalid related_id '{rid}'. Must match pattern: ^[A-Z]{{3,10}}-[A-Z]{{3,10}}-\\d{{3}}$",
                        details={
                            "related_id": rid,
                            "pattern": "^[A-Z]{3,10}-[A-Z]{3,10}-\\d{3}$",
                        },
                    )

        ns = (
            self._layout.get_namespace(params.namespace)
            if params.namespace
            else self._layout.default_namespace()
        )
        if ns is None:
            valid = [n.namespace for n in self._layout.namespaces]
            raise MeminitError(
                code=ErrorCode.UNKNOWN_NAMESPACE,
                message=f"Unknown namespace: {params.namespace}. Valid namespaces: {valid}",
                details={"namespace": params.namespace, "valid": valid},
            )

        normalized_type = self._normalize_type(params.doc_type)
        expected_subdir = ns.expected_subdir_for_type(normalized_type)
        if not expected_subdir:
            valid = sorted(ns.type_directories.keys())
            raise MeminitError(
                code=ErrorCode.UNKNOWN_TYPE,
                message=f"Unknown document type: {params.doc_type}. Valid types: {valid}",
                details={"doc_type": params.doc_type, "valid": valid},
            )

        target_dir = ns.docs_dir / expected_subdir
        ensure_safe_write_path(root_dir=self.root_dir, target_path=target_dir)

        if reasoning is not None:
            reasoning.append(
                {
                    "decision": "directory_selected",
                    "value": str(target_dir.relative_to(self.root_dir)),
                }
            )

        if not params.dry_run:
            target_dir.mkdir(parents=True, exist_ok=True)

        lock_file = None
        try:
            if not params.dry_run:
                lock_file = self._acquire_lock(target_dir)

            if params.document_id:
                if not RELATED_ID_PATTERN.match(params.document_id):
                    raise MeminitError(
                        code=ErrorCode.INVALID_ID_FORMAT,
                        message=f"Invalid document_id '{params.document_id}'. Must match pattern: ^[A-Z]{{3,10}}-[A-Z]{{3,10}}-\\d{{3}}$",
                        details={"document_id": params.document_id},
                    )
                id_parts = params.document_id.split("-")
                provided_prefix = id_parts[0] if id_parts else ""
                expected_prefix = (ns.repo_prefix or "").upper()
                if provided_prefix.upper() != expected_prefix:
                    raise MeminitError(
                        code=ErrorCode.INVALID_ID_FORMAT,
                        message=(
                            f"document_id prefix segment '{provided_prefix}' does not match "
                            f"namespace repo_prefix '{ns.repo_prefix}'"
                        ),
                        details={
                            "document_id": params.document_id,
                            "namespace": ns.namespace,
                            "expected_prefix": ns.repo_prefix,
                        },
                    )
                provided_type = id_parts[1] if len(id_parts) >= 2 else ""
                if provided_type.upper() != normalized_type.upper():
                    raise MeminitError(
                        code=ErrorCode.INVALID_ID_FORMAT,
                        message=f"document_id type segment '{provided_type}' does not match doc_type '{normalized_type}'",
                        details={
                            "document_id": params.document_id,
                            "doc_type": normalized_type,
                        },
                    )
                doc_id = params.document_id

                if reasoning is not None:
                    reasoning.append(
                        {
                            "decision": "id_allocated",
                            "value": doc_id,
                            "method": "deterministic",
                        }
                    )

                filename = self._generate_filename(doc_id, params.title)
                target_path = target_dir / filename
                ensure_safe_write_path(root_dir=self.root_dir, target_path=target_path)

                # Lock is per target type directory; deterministic IDs are validated
                # against the type segment, so concurrent creates in other directories
                # cannot legitimately produce the same document_id.
                existing_path = self._find_existing_document_id(doc_id, ns)
                if existing_path is not None:
                    existing_resolved = existing_path.resolve()
                    target_resolved = target_path.resolve()
                    if existing_resolved != target_resolved:
                        raise MeminitError(
                            code=ErrorCode.DUPLICATE_ID,
                            message=(
                                f"Document ID already exists: {doc_id} " f"at {existing_path}"
                            ),
                            details={
                                "document_id": doc_id,
                                "existing_path": str(existing_path),
                                "target_path": str(target_path),
                            },
                        )

                if target_path.exists():
                    existing_content = target_path.read_text(encoding="utf-8")
                    owner, owner_source = self._resolve_owner_with_source(params.owner, ns)
                    if reasoning is not None:
                        reasoning.append(
                            {
                                "decision": "owner_resolved",
                                "value": owner,
                                "source": owner_source,
                            }
                        )
                    content = self._load_template(
                        normalized_type,
                        params.title,
                        doc_id,
                        ns,
                        owner=owner,
                        status=params.status,
                        area=params.area,
                        description=params.description,
                        keywords=params.keywords,
                        related_ids=params.related_ids,
                        superseded_by=params.superseded_by,
                    )
                    if reasoning is not None:
                        template_path_str = ns.templates.get(normalized_type.lower())
                        template_name = template_path_str if template_path_str else "default"
                        reasoning.append(
                            {
                                "decision": "template_loaded",
                                "value": template_name,
                            }
                        )
                    post = frontmatter.loads(content)
                    actual_metadata = dict(post.metadata or {})
                    self._validate_generated_metadata(actual_metadata, ns)

                    idempotent_last_updated = self._idempotent_last_updated(
                        existing_content, post, content
                    )
                    if idempotent_last_updated is not None:
                        ctx["details"]["document_id"] = doc_id
                        ctx["details"]["path"] = str(target_path)
                        return NewDocumentResult(
                            success=True,
                            path=target_path,
                            document_id=doc_id,
                            doc_type=normalized_type,
                            title=params.title,
                            status=params.status,
                            version="0.1",
                            owner=owner,
                            area=params.area,
                            last_updated=idempotent_last_updated,
                            docops_version=str(ns.docops_version or "2.0"),
                            description=params.description,
                            keywords=params.keywords,
                            related_ids=params.related_ids,
                            superseded_by=params.superseded_by,
                            dry_run=params.dry_run,
                            reasoning=reasoning,
                        )
                    raise MeminitError(
                        code=ErrorCode.FILE_EXISTS,
                        message=f"File already exists with different content: {target_path}",
                        details={"path": str(target_path), "document_id": doc_id},
                    )
            else:
                doc_id = self._generate_id(normalized_type, target_dir, ns)

                if reasoning is not None:
                    reasoning.append(
                        {
                            "decision": "id_allocated",
                            "value": doc_id,
                            "method": "sequential",
                        }
                    )

                filename = self._generate_filename(doc_id, params.title)
                target_path = target_dir / filename
                ensure_safe_write_path(root_dir=self.root_dir, target_path=target_path)

                if target_path.exists():
                    raise MeminitError(
                        code=ErrorCode.DUPLICATE_ID,
                        message=f"Document already exists: {target_path}",
                        details={"path": str(target_path)},
                    )

            owner, owner_source = self._resolve_owner_with_source(params.owner, ns)
            if reasoning is not None:
                reasoning.append(
                    {
                        "decision": "owner_resolved",
                        "value": owner,
                        "source": owner_source,
                    }
                )
            content = self._load_template(
                normalized_type,
                params.title,
                doc_id,
                ns,
                owner=owner,
                status=params.status,
                area=params.area,
                description=params.description,
                keywords=params.keywords,
                related_ids=params.related_ids,
                superseded_by=params.superseded_by,
            )
            if reasoning is not None:
                template_path_str = ns.templates.get(normalized_type.lower())
                template_name = template_path_str if template_path_str else "default"
                reasoning.append(
                    {
                        "decision": "template_loaded",
                        "value": template_name,
                    }
                )

            post = frontmatter.loads(content)
            actual_metadata = dict(post.metadata or {})
            self._validate_generated_metadata(actual_metadata, ns)

            if params.dry_run:
                ctx["details"]["document_id"] = doc_id
                ctx["details"]["path"] = str(target_path)
                return NewDocumentResult(
                    success=True,
                    path=target_path,
                    document_id=doc_id,
                    doc_type=normalized_type,
                    title=params.title,
                    status=params.status,
                    version="0.1",
                    owner=owner,
                    area=params.area,
                    last_updated=date.today().isoformat(),
                    docops_version=str(ns.docops_version or "2.0"),
                    description=params.description,
                    keywords=params.keywords,
                    related_ids=params.related_ids,
                    superseded_by=params.superseded_by,
                    dry_run=True,
                    content=content,
                    reasoning=reasoning,
                )

            temp_path_str = None
            temp_file = None
            cleanup_error_msg = None
            try:
                temp_fd, temp_path_str = tempfile.mkstemp(
                    suffix=".md.tmp",
                    prefix=".",
                    dir=target_dir,
                )
                temp_file = os.fdopen(temp_fd, "w", encoding="utf-8")
                temp_file.write(content)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_file.close()
                temp_file = None

                os.replace(temp_path_str, target_path)
                temp_path_str = None
            except Exception as e:
                if temp_file:
                    try:
                        temp_file.close()
                    except Exception as ce:
                        cleanup_error_msg = f"Temp file close failed: {ce}"
                if temp_path_str and os.path.exists(temp_path_str):
                    try:
                        os.remove(temp_path_str)
                    except Exception as ce:
                        cleanup_error_msg = (
                            cleanup_error_msg or ""
                        ) + f" Temp file removal failed: {ce}"
                if isinstance(e, MeminitError):
                    if cleanup_error_msg:
                        if e.details is None:
                            e.details = {}
                        e.details["cleanup_error"] = cleanup_error_msg.strip()
                    raise
                details = {"original_error": str(e)}
                if cleanup_error_msg:
                    details["cleanup_error"] = cleanup_error_msg.strip()
                raise MeminitError(
                    code=ErrorCode.UNKNOWN_ERROR,
                    message=f"Document creation failed: {e}",
                    details=details,
                ) from e

            ctx["details"]["document_id"] = doc_id
            ctx["details"]["path"] = str(target_path)
            return NewDocumentResult(
                success=True,
                path=target_path,
                document_id=doc_id,
                doc_type=normalized_type,
                title=params.title,
                status=params.status,
                version="0.1",
                owner=owner,
                area=params.area,
                last_updated=date.today().isoformat(),
                docops_version=str(ns.docops_version or "2.0"),
                description=params.description,
                keywords=params.keywords,
                related_ids=params.related_ids,
                superseded_by=params.superseded_by,
                dry_run=False,
                reasoning=reasoning,
            )
        finally:
            if lock_file:
                self._release_lock(lock_file)

    def _resolve_owner(self, cli_owner: Optional[str], ns: RepoConfig) -> str:
        """Resolve the document owner using the precedence chain (F2.8).

        Precedence order (first non-empty value wins):
        1. CLI argument (--owner flag)
        2. Environment variable MEMINIT_DEFAULT_OWNER
        3. docops.config.yaml 'default_owner' key
        4. Fallback to '__TBD__' placeholder

        Args:
            cli_owner: Owner value from CLI argument, may be None.
            ns: Repository configuration (unused but available for future namespace-level defaults).

        Returns:
            Resolved owner string, or '__TBD__' if no source provided a value.
        """
        if cli_owner:
            return cli_owner

        env_owner = os.environ.get("MEMINIT_DEFAULT_OWNER")
        if env_owner:
            return env_owner

        config = self._load_config_yaml()
        if config:
            config_owner = config.get("default_owner")
            if config_owner:
                return str(config_owner)

        return "__TBD__"

    def _resolve_owner_with_source(self, cli_owner: Optional[str], ns: RepoConfig) -> tuple:
        """Resolve owner and return (value, source) tuple.

        Precedence order (first non-empty value wins):
        1. CLI argument (--owner flag) -> "cli"
        2. Environment variable MEMINIT_DEFAULT_OWNER -> "env"
        3. docops.config.yaml 'default_owner' key -> "config"
        4. Fallback to '__TBD__' -> "default"

        Args:
            cli_owner: Owner value from CLI argument, may be None.
            ns: Repository configuration (unused but available for future namespace-level defaults).

        Returns:
            Tuple of (resolved_owner, source) where source indicates where the value came from.
        """
        if cli_owner:
            return (cli_owner, "cli")

        env_owner = os.environ.get("MEMINIT_DEFAULT_OWNER")
        if env_owner:
            return (env_owner, "env")

        config = self._load_config_yaml()
        if config:
            config_owner = config.get("default_owner")
            if config_owner:
                return (str(config_owner), "config")

        return ("__TBD__", "default")

    def _load_config_yaml(self) -> Optional[Dict[str, Any]]:
        """Load the docops.config.yaml file from the repository root.

        Returns:
            Parsed YAML configuration as a dictionary, or None if the file
            does not exist or cannot be parsed.
        """
        config_path = self.root_dir / "docops.config.yaml"
        if config_path.exists():
            try:
                return yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except Exception:
                return None
        return None

    def _validate_generated_metadata(self, metadata: Dict[str, Any], ns: RepoConfig) -> None:
        """Validate generated metadata against schema and required fields."""
        schema_validator = SchemaValidator(str(ns.schema_file))
        if schema_validator.is_ready():
            normalized = normalize_yaml_scalar_footguns(metadata)
            violation = schema_validator.validate_data(normalized)
            if violation:
                raise MeminitError(
                    code=ErrorCode.SCHEMA_INVALID,
                    message=f"Generated document fails schema validation: {violation.message}",
                    details={
                        "field": violation.rule,
                        "value": metadata.get(violation.rule),
                        "validation_message": violation.message,
                    },
                )
        else:
            raise MeminitError(
                code=ErrorCode.SCHEMA_INVALID,
                message=f"Schema file not available: {ns.schema_file}",
                details={"schema_path": str(ns.schema_file)},
            )

        for required_field in ["document_id", "type", "title", "status", "owner"]:
            value = metadata.get(required_field)
            if required_field == "owner" and value == "__TBD__":
                continue
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise MeminitError(
                    code=ErrorCode.SCHEMA_INVALID,
                    message=f"Required field '{required_field}' is empty or missing",
                    details={"field": required_field, "value": str(value)},
                )

    def _idempotent_last_updated(
        self, existing_content: str, generated_post: Any, generated_content: str
    ) -> Optional[str]:
        """Return last_updated for idempotent matches, or None when not idempotent."""
        if existing_content == generated_content:
            generated_meta = dict(getattr(generated_post, "metadata", {}) or {})
            normalized_meta = normalize_yaml_scalar_footguns(generated_meta)
            return self._coerce_last_updated(normalized_meta.get("last_updated"))

        try:
            existing_post = frontmatter.loads(existing_content)
        except Exception:
            return None

        if existing_post.content != generated_post.content:
            return None

        existing_meta = normalize_yaml_scalar_footguns(dict(existing_post.metadata or {}))
        generated_meta = normalize_yaml_scalar_footguns(
            dict(getattr(generated_post, "metadata", {}) or {})
        )
        existing_last_updated = existing_meta.get("last_updated")
        generated_last_updated = generated_meta.get("last_updated")
        existing_meta.pop("last_updated", None)
        generated_meta.pop("last_updated", None)
        if existing_meta != generated_meta:
            return None
        return self._coerce_last_updated(existing_last_updated or generated_last_updated)

    def _coerce_last_updated(self, value: Any) -> str:
        """Return a normalized last_updated string or today's date as fallback."""
        if isinstance(value, str) and value.strip():
            return value
        return date.today().isoformat()

    def _get_lock_timeout_ms(self) -> int:
        """Get the lock acquisition timeout in milliseconds.

        Resolution order:
        1. MEMINIT_LOCK_TIMEOUT_MS environment variable
        2. Default value of 3000ms (3 seconds)

        Returns:
            Timeout in milliseconds. Returns 3000 if env var is not a valid integer.
        """
        try:
            return int(os.environ.get("MEMINIT_LOCK_TIMEOUT_MS", "3000"))
        except ValueError:
            return 3000

    def _acquire_lock(self, target_dir: Path):
        """Acquire exclusive lock for the target directory.

        Uses fcntl.flock with LOCK_EX | LOCK_NB and retries up to timeout.
        Lock file is .meminit.lock in the target directory.

        Raises:
            MeminitError: with LOCK_TIMEOUT if lock cannot be acquired
        """
        lock_path = target_dir / ".meminit.lock"
        target_dir.mkdir(parents=True, exist_ok=True)
        ensure_safe_write_path(root_dir=self.root_dir, target_path=lock_path)

        # Best-effort fallback for non-POSIX platforms: continue without file
        # locking rather than failing all document creation operations.
        if fcntl is None:
            log_debug(
                "file_locking_unavailable",
                {
                    "platform": sys.platform,
                    "directory": str(target_dir),
                },
            )
            return None

        timeout_ms = self._get_lock_timeout_ms()
        start_time = time.monotonic()

        while True:
            lock_file = None
            try:
                ensure_safe_write_path(root_dir=self.root_dir, target_path=lock_path)
                lock_file = self._open_lock_file(lock_path)
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return lock_file
            except MeminitError:
                if lock_file:
                    try:
                        lock_file.close()
                    except Exception:
                        pass
                raise
            except (IOError, OSError):
                if lock_file:
                    try:
                        lock_file.close()
                    except Exception:
                        pass
                elapsed_ms = (time.monotonic() - start_time) * 1000
                if elapsed_ms >= timeout_ms:
                    raise MeminitError(
                        code=ErrorCode.LOCK_TIMEOUT,
                        message=f"Could not acquire lock for {target_dir} within {timeout_ms}ms",
                        details={
                            "directory": str(target_dir),
                            "timeout_ms": timeout_ms,
                        },
                    )
                time.sleep(0.05)

    def _open_lock_file(self, lock_path: Path):
        """Open a lock file without following symlinks when supported."""
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            if hasattr(os, "O_NOFOLLOW") and exc.errno == errno.ELOOP:
                raise MeminitError(
                    code=ErrorCode.PATH_ESCAPE,
                    message=f"Lock path '{lock_path}' is a symlink and cannot be used",
                    details={"lock_path": str(lock_path)},
                ) from exc
            raise
        return os.fdopen(fd, "a+")

    def _release_lock(self, lock_file) -> None:
        """Release the lock file."""
        if lock_file:
            try:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass

    def _normalize_type(self, doc_type: str) -> str:
        """Normalize a document type string to canonical uppercase form.

        Applies type alias resolution (e.g., 'Governance' -> 'GOV') and ensures
        consistent uppercase representation for ID generation and directory lookup.

        Args:
            doc_type: Raw document type string from user input.

        Returns:
            Normalized uppercase type string. 'GOVERNANCE' is mapped to 'GOV'.
        """
        t = str(doc_type).strip().upper()
        if t == "GOVERNANCE":
            return "GOV"
        return t

    def get_available_types(self, namespace: Optional[str] = None) -> List[Dict[str, str]]:
        """Return available document types and directories for a namespace."""
        ns = (
            self._layout.get_namespace(namespace) if namespace else self._layout.default_namespace()
        )
        if ns is None:
            valid = [n.namespace for n in self._layout.namespaces]
            raise MeminitError(
                code=ErrorCode.UNKNOWN_NAMESPACE,
                message=f"Unknown namespace: {namespace}. Valid namespaces: {valid}",
                details={"namespace": namespace, "valid": valid},
            )

        types_list: List[Dict[str, str]] = []
        for doc_type, directory in sorted(ns.type_directories.items()):
            dir_path = f"{ns.docs_root}/{directory}"
            if not dir_path.endswith("/"):
                dir_path += "/"
            types_list.append({"type": doc_type, "directory": dir_path})
        return types_list

    def get_valid_types(self, namespace: Optional[str] = None) -> List[str]:
        """Return sorted valid document types for a namespace."""
        return [item["type"] for item in self.get_available_types(namespace)]

    def _generate_id(self, doc_type: str, target_dir: Path, ns: RepoConfig) -> str:
        repo_prefix = ns.repo_prefix
        id_type = self._id_type_segment(doc_type)

        max_id = 0
        scanned_files = 0
        regex = re.compile(rf"^{re.escape(id_type.lower())}-(\d{{3}})-", re.IGNORECASE)
        frontmatter_regex = re.compile(
            rf"^[A-Z]{{3,10}}-{re.escape(id_type)}-(\d{{3}})$", re.IGNORECASE
        )

        for p in target_dir.glob("*.md"):
            scanned_files += 1
            match = regex.match(p.name)
            if match:
                num = int(match.group(1))
                if num > max_id:
                    max_id = num
            else:
                try:
                    post = frontmatter.load(p)
                except (OSError, UnicodeDecodeError, yaml.YAMLError):
                    continue

                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str):
                    continue

                doc_id = doc_id.strip()
                match = frontmatter_regex.match(doc_id)
                if match:
                    num = int(match.group(1))
                    if num > max_id:
                        max_id = num

        next_id = max_id + 1
        log_debug(
            operation="debug.id_generation",
            details={
                "doc_type": doc_type,
                "target_dir": str(target_dir),
                "scanned_files": scanned_files,
                "max_id": max_id,
                "next_id": next_id,
            },
        )
        return f"{repo_prefix}-{id_type}-{next_id:03d}"

    def _find_existing_document_id(self, doc_id: str, ns: RepoConfig) -> Optional[Path]:
        """Find an existing document path by document_id within the namespace docs root."""
        for path in ns.docs_dir.rglob("*.md"):
            if ns.is_excluded(path):
                continue
            try:
                post = frontmatter.load(str(path))
            except Exception:
                continue
            metadata = post.metadata or {}
            existing_id = metadata.get("document_id")
            if isinstance(existing_id, str) and existing_id.strip() == doc_id:
                return path
        return None

    def _generate_filename(self, doc_id: str, title: str) -> str:
        """Generate a filesystem-safe filename for a document.

        The filename format is: {type-segment}-{sequence}-{slugified-title}.md
        For example, 'ADR-042-use-hexagonal-architecture.md'.

        Title is slugified: lowercase, spaces to hyphens, non-alphanumeric
        characters removed, consecutive hyphens collapsed.

        Args:
            doc_id: Full document ID (e.g., 'MEMINIT-ADR-042').
            title: Document title to slugify.

        Returns:
            Filename string ending in '.md'.
        """
        safe_title = title.lower().replace(" ", "-")
        safe_title = re.sub(r"[^a-z0-9-]", "", safe_title)
        safe_title = re.sub(r"-{2,}", "-", safe_title).strip("-")
        if not safe_title:
            safe_title = "untitled"
        parts = doc_id.split("-")
        short_id = doc_id.lower()
        if len(parts) >= 3:
            short_id = f"{parts[-2].lower()}-{parts[-1].lower()}"
        return f"{short_id}-{safe_title}.md"

    def _generate_visible_metadata_block(self, metadata: Dict[str, Any]) -> str:
        """Generate a visible metadata block in blockquote format (F6).

        Format:
        > **Document ID:** MEMINIT-ADR-042
        > **Owner:** owner-name
        > **Status:** Draft
        ...
        """
        display_fields = [
            ("document_id", "Document ID"),
            ("owner", "Owner"),
            ("status", "Status"),
            ("version", "Version"),
            ("last_updated", "Last Updated"),
            ("type", "Type"),
            ("area", "Area"),
            ("description", "Description"),
        ]

        lines = []
        for key, label in display_fields:
            value = metadata.get(key)
            if value is not None and value != "":
                lines.append(f"> **{label}:** {value}")

        return "\n".join(lines)

    def _load_template(
        self,
        doc_type: str,
        title: str,
        doc_id: str,
        ns: RepoConfig,
        owner: str = "__TBD__",
        status: str = "Draft",
        area: Optional[str] = None,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        related_ids: Optional[List[str]] = None,
        superseded_by: Optional[str] = None,
        strict: bool = False,
    ) -> str:
        template_path_str = ns.templates.get(doc_type.lower())
        template_content = ""
        template_frontmatter: Dict[str, Any] = {}
        template_path: Optional[Path] = None
        template_found = False

        if template_path_str:
            template_path = self.root_dir / template_path_str
            if template_path.exists():
                template_content = template_path.read_text(encoding="utf-8")
                template_found = True
            elif strict:
                raise MeminitError(
                    code=ErrorCode.TEMPLATE_NOT_FOUND,
                    message=f"Template not found for type '{doc_type}': {template_path}",
                    details={"doc_type": doc_type, "template_path": str(template_path)},
                )
        log_debug(
            operation="debug.template_resolution",
            details={
                "doc_type": doc_type,
                "template_path": str(template_path) if template_path else None,
                "template_found": template_found,
            },
        )

        body = template_content
        if body.strip().startswith("---"):
            try:
                post = frontmatter.loads(body)
            except (yaml.YAMLError, ValueError):
                pass
            else:
                template_frontmatter = dict(post.metadata) if post.metadata else {}
                body = post.content

        if not body.strip():
            body = f"# {doc_type}: {title}\n\n## Context\n\n## Content\n"
            log_debug(
                operation="debug.template_resolution",
                details={
                    "doc_type": doc_type,
                    "fallback": "default_skeleton",
                },
            )

        docops_version = str(ns.docops_version or "2.0")

        generated_metadata: Dict[str, Any] = {
            "document_id": doc_id,
            "type": doc_type,
            "title": title,
            "status": status,
            "version": "0.1",
            "last_updated": date.today().isoformat(),
            "owner": owner,
            "docops_version": docops_version,
        }

        if area is not None:
            generated_metadata["area"] = area
        if description is not None:
            generated_metadata["description"] = description
        if keywords is not None:
            generated_metadata["keywords"] = keywords
        if related_ids is not None:
            generated_metadata["related_ids"] = related_ids
        if superseded_by is not None:
            generated_metadata["superseded_by"] = superseded_by

        for key, value in list(template_frontmatter.items()):
            if isinstance(value, str):
                template_frontmatter[key] = self._apply_common_template_substitutions(
                    value,
                    doc_type=doc_type,
                    title=title,
                    doc_id=doc_id,
                    status=status,
                    owner=owner,
                    area=area,
                    description=description,
                    keywords=keywords,
                    related_ids=related_ids,
                )
            elif isinstance(value, list):
                template_frontmatter[key] = [
                    self._apply_common_template_substitutions(
                        v,
                        doc_type=doc_type,
                        title=title,
                        doc_id=doc_id,
                        status=status,
                        owner=owner,
                        area=area,
                        description=description,
                        keywords=keywords,
                        related_ids=related_ids,
                    )
                    if isinstance(v, str)
                    else v
                    for v in value
                ]

        metadata = {**template_frontmatter, **generated_metadata}

        body = self._apply_common_template_substitutions(
            body,
            doc_type=doc_type,
            title=title,
            doc_id=doc_id,
            status=status,
            owner=owner,
            area=area,
            description=description,
            keywords=keywords,
            related_ids=related_ids,
        )

        visible_block = self._generate_visible_metadata_block(metadata)
        if "<!-- MEMINIT_METADATA_BLOCK -->" in body:
            body = body.replace("<!-- MEMINIT_METADATA_BLOCK -->", visible_block)

        fm_yaml = yaml.safe_dump(metadata, sort_keys=False, default_flow_style=False).strip()
        return f"---\n{fm_yaml}\n---\n\n{body.lstrip()}"

    def _id_type_segment(self, doc_type: str) -> str:
        """Extract the type segment for document ID generation.

        Converts a document type to the uppercase alphabetic segment used in
        document IDs (e.g., 'ADR' in 'MEMINIT-ADR-042').

        Rules:
        - 'GOVERNANCE' maps to 'GOV'
        - Types with 3-10 alphabetic characters are used as-is
        - Otherwise, extracts uppercase letters and truncates to 10 chars
        - Falls back to 'DOC' if fewer than 3 valid characters

        Args:
            doc_type: Normalized document type string.

        Returns:
            3-10 character uppercase alphabetic type segment.
        """
        doc_type_upper = doc_type.upper()
        if doc_type_upper == "GOVERNANCE":
            return "GOV"
        if 3 <= len(doc_type_upper) <= 10 and doc_type_upper.isalpha():
            return doc_type_upper
        segment = re.sub(r"[^A-Z]", "", doc_type_upper)[:10]
        return segment if len(segment) >= 3 else "DOC"

    def _apply_common_template_substitutions(
        self,
        body: str,
        doc_type: str,
        title: str,
        doc_id: str,
        status: str,
        owner: str = "__TBD__",
        area: Optional[str] = None,
        description: Optional[str] = None,
        keywords: Optional[List[str]] = None,
        related_ids: Optional[List[str]] = None,
    ) -> str:
        """Apply standard placeholder substitutions to template content.

        Replaces common template placeholders with actual values:
        - {title}: Document title
        - {status}: Document status
        - <REPO>, <PROJECT>: Repository prefix from document ID
        - <SEQ>: Sequence number from document ID
        - <YYYY-MM-DD>: Current date in ISO format
        - <Decision Title>, <Feature Title>: Title aliases
        - <Team or Person>: Owner value
        - {owner}: Owner value (F7.2)
        - {area}: Area value (F7.2)
        - {description}: Description value (F7.2)
        - {keywords}: Comma-separated keywords (F7.3)
        - {related_ids}: Comma-separated related IDs (F7.3)

        Args:
            body: Template content (frontmatter body or markdown content).
            doc_type: Document type (unused but available for extensions).
            title: Document title.
            doc_id: Full document ID for extracting prefix and sequence.
            status: Document lifecycle status.
            owner: Resolved owner value.
            area: Optional area classification.
            description: Optional document description.
            keywords: Optional list of keywords.
            related_ids: Optional list of related document IDs.

        Returns:
            Content with all placeholders replaced.
        """
        parts = doc_id.split("-")
        default_ns = self._layout.default_namespace()
        repo_prefix = parts[0] if len(parts) >= 1 else ""
        if not repo_prefix and default_ns:
            repo_prefix = default_ns.repo_prefix
        seq = parts[-1] if len(parts) >= 3 else "001"

        today = date.today().isoformat()

        substitutions = {
            "{title}": title,
            "{status}": status,
            "<REPO>": repo_prefix,
            "<PROJECT>": repo_prefix,
            "<SEQ>": seq,
            "<YYYY-MM-DD>": today,
            "<Decision Title>": title,
            "<Feature Title>": title,
            "<Team or Person>": owner,
            "{owner}": owner,
            "{area}": area or "",
            "{description}": description or "",
            "{keywords}": ", ".join(keywords) if keywords else "",
            "{related_ids}": ", ".join(related_ids) if related_ids else "",
        }

        for k, v in substitutions.items():
            body = body.replace(k, v)

        return body
