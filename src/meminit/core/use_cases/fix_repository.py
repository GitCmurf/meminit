import re
import shutil
import hashlib
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

import frontmatter

from meminit.core.domain.entities import FixAction, FixReport, Severity, Violation
from meminit.core.services.metadata_normalization import normalize_yaml_scalar_footguns
from meminit.core.services.repo_config import RepoConfig, load_repo_layout
from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.safe_fs import ensure_safe_write_path
from meminit.core.services.validators import SchemaValidator
from meminit.core.use_cases.check_repository import CheckRepositoryUseCase
from meminit.core.services.scan_plan import MigrationPlan, PlanAction, PlanActionType


class FixRepositoryUseCase:
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
        self.checker = CheckRepositoryUseCase(root_dir)
        self._existing_document_ids: set[str] = set()
        self._schema_validators: dict[str, SchemaValidator] = {}

    def execute(self, dry_run: bool = False, namespace: str | None = None, plan: Optional[MigrationPlan] = None) -> FixReport:
        if plan is not None:
            report = self._execute_plan(plan, dry_run)
            
            # Post-plan compliance check to populate remaining violations
            violations = self.checker.execute()
            if namespace:
                target_ns = self._layout.get_namespace(namespace)
                if target_ns:
                    ns_root = str(Path(self.root_dir) / target_ns.docs_root)
                    violations = [v for v in violations if v.file.startswith(ns_root)]
            
            report.remaining_violations.extend(violations)
            return report

        # 1. Run Check
        violations = self.checker.execute()
        self._existing_document_ids = self._scan_existing_document_ids()
        report = FixReport()

        target_ns = self._layout.get_namespace(namespace) if namespace else None
        if namespace and target_ns is None:
            report.remaining_violations.append(
                Violation(
                    file="docops.config.yaml",
                    line=0,
                    rule="CONFIG_INVALID",
                    message=f"Unknown namespace: {namespace}",
                    severity=Severity.ERROR,
                )
            )
            return report

        if target_ns is not None:
            filtered: list[Violation] = []
            for v in violations:
                p = self.root_dir / v.file
                ns_for_path = self._layout.namespace_for_path(p)
                if (
                    ns_for_path
                    and ns_for_path.namespace.lower() == target_ns.namespace.lower()
                ):
                    filtered.append(v)
            violations = filtered

        renames = [v for v in violations if v.rule == "FILENAME_CONVENTION"]
        other_violations = [v for v in violations if v.rule != "FILENAME_CONVENTION"]

        # 2. Handle Renames
        self._process_renames(renames, report, dry_run)

        # 3. Handle Content Fixes
        self._process_content_fixes(other_violations, report, dry_run)

        return report

    def _execute_plan(self, plan: MigrationPlan, dry_run: bool) -> FixReport:
        report = FixReport()
        self._existing_document_ids = self._scan_existing_document_ids()
        modified_paths = set()

        for action in plan.actions:
            v_file = action.target_path or action.source_path
            src_path = self.root_dir / action.source_path
            target_path = self.root_dir / action.target_path

            # 1. Safe Path Validation
            try:
                ensure_safe_write_path(root_dir=self.root_dir, target_path=src_path)
                ensure_safe_write_path(root_dir=self.root_dir, target_path=target_path)
            except MeminitError as exc:
                if exc.code == ErrorCode.PATH_ESCAPE:
                    report.remaining_violations.append(
                        Violation(file=v_file, line=0, rule="UNSAFE_PATH", message=exc.message)
                    )
                    continue
                raise

            # 2. Non-Destructive Validation
            if action.safety.destructive:
                report.remaining_violations.append(
                    Violation(file=v_file, line=0, rule="UNSAFE_ACTION", message="Destructive actions are forbidden.")
                )
                continue

            # 3. Drift Detection
            if action.preconditions.source_sha256 and src_path not in modified_paths:
                if not src_path.exists():
                    report.remaining_violations.append(
                        Violation(file=v_file, line=0, rule="DRIFT_DETECTED", message="Source file is missing.")
                    )
                    continue
                current_sha256 = f"sha256:{hashlib.sha256(src_path.read_bytes()).hexdigest()}"
                if current_sha256 != action.preconditions.source_sha256:
                    report.remaining_violations.append(
                        Violation(file=v_file, line=0, rule="DRIFT_DETECTED", message="Source file hash mismatch.")
                    )
                    continue

            # 4. Collision Policy
            if src_path != target_path and target_path.exists() and not action.safety.overwrites:
                report.remaining_violations.append(
                    Violation(file=v_file, line=0, rule="COLLISION", message=f"Target path {action.target_path} exists.")
                )
                continue

            # Apply Phase
            try:
                if action.action in (PlanActionType.RENAME_FILE, PlanActionType.MOVE_FILE):
                    if not dry_run:
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(src_path), str(target_path))
                    modified_paths.add(target_path)
                    modified_paths.add(src_path)
                    report.fixed_violations.append(
                        FixAction(file=v_file, action=action.action.value if hasattr(action.action, 'value') else str(action.action), description=f"Moved/Renamed {action.source_path} to {action.target_path}")
                    )

                elif action.action in (PlanActionType.INSERT_METADATA_BLOCK, PlanActionType.UPDATE_METADATA):
                    if not dry_run:
                        try:
                            content_bytes = src_path.read_bytes()
                            post = frontmatter.loads(content_bytes.decode('utf-8'))
                        except Exception:
                            post = frontmatter.Post("")

                        if not post.metadata:
                            post.metadata = {}
                        
                        patch = action.metadata_patch or {}
                        for k, v in patch.items():
                            post.metadata[k] = v

                        if "document_id" not in post.metadata or post.metadata.get("document_id") == "__TBD__":
                            ns = self._layout.namespace_for_path(src_path)
                            doc_type = post.metadata.get("type", "DOC")
                            if ns:
                                post.metadata["document_id"] = self._generate_unique_document_id(doc_type, ns)

                        post.metadata = normalize_yaml_scalar_footguns(post.metadata)
                        target_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(target_path, "w", encoding="utf-8") as f:
                            f.write(frontmatter.dumps(post))
                    
                    modified_paths.add(target_path)
                    modified_paths.add(src_path)
                    report.fixed_violations.append(
                        FixAction(file=v_file, action=action.action.value if hasattr(action.action, 'value') else str(action.action), description="Applied metadata patch")
                    )
                else:
                    report.remaining_violations.append(
                        Violation(file=v_file, line=0, rule="UNKNOWN_ACTION", message=f"Unknown action {action.action}")
                    )
            except Exception as e:
                import traceback
                traceback.print_exc()
                report.remaining_violations.append(
                    Violation(file=v_file, line=0, rule="APPLY_ERROR", message=str(e))
                )

        return report

    def _process_renames(
        self, violations: List[Violation], report: FixReport, dry_run: bool
    ):
        for v in violations:
            src_path = self.root_dir / v.file
            new_path = self._compute_renamed_path(src_path)
            new_name = new_path.name

            try:
                ensure_safe_write_path(root_dir=self.root_dir, target_path=src_path)
                ensure_safe_write_path(root_dir=self.root_dir, target_path=new_path)
            except MeminitError as exc:
                if exc.code == ErrorCode.PATH_ESCAPE:
                    report.remaining_violations.append(
                        Violation(
                            file=v.file,
                            line=0,
                            rule="UNSAFE_PATH",
                            message=exc.message,
                            severity=Severity.ERROR,
                        )
                    )
                    continue
                raise

            if not dry_run:
                try:
                    if src_path.exists() and not new_path.exists():
                        shutil.move(str(src_path), str(new_path))
                        # Only record success if move succeeds
                        action = FixAction(
                            file=v.file,
                            action="Rename",
                            description=f"Rename '{src_path.name}' to '{new_name}'",
                        )
                        report.fixed_violations.append(action)
                    else:
                        report.remaining_violations.append(v)
                except Exception as e:
                    print(f"Failed to rename {v.file}: {e}")
                    report.remaining_violations.append(v)
            else:
                # In dry-run, we just record intent
                action = FixAction(
                    file=v.file,
                    action="Rename (Dry Run)",
                    description=f"Would rename '{src_path.name}' to '{new_name}'",
                )
                report.fixed_violations.append(action)

    def _process_content_fixes(
        self, violations: List[Violation], report: FixReport, dry_run: bool
    ):
        file_map = self._group_and_locate_files(violations, report)

        for path, file_violations in file_map.items():
            self._apply_file_fixes(path, file_violations, report, dry_run)

    def _group_and_locate_files(
        self, violations: List[Violation], report: FixReport
    ) -> Dict[Path, List[Violation]]:
        file_map = {}
        for v in violations:
            if v.rule not in [
                "SCHEMA_VALIDATION",
                "SCHEMA_MISSING",
                "FRONTMATTER_MISSING",
            ]:
                report.remaining_violations.append(v)
                continue

            path = self._resolve_target_path(v, report)
            if not path:
                report.remaining_violations.append(v)
                continue

            if path not in file_map:
                file_map[path] = []
            file_map[path].append(v)

        return file_map

    def _resolve_target_path(
        self, violation: Violation, report: FixReport
    ) -> Optional[Path]:
        target_path = self.root_dir / violation.file

        if target_path.exists():
            return target_path

        # Check if it was renamed
        # Logic: We assume if it doesn't verify at original path, it might be at new path
        potential_new_path = self._compute_renamed_path(target_path)

        if potential_new_path.exists():
            return potential_new_path

        return None

    def _compute_renamed_path(self, original_path: Path) -> Path:
        """Compute the target path after applying filename conventions."""
        if original_path.name in self.FILENAME_EXCEPTIONS:
            return original_path
        stem = original_path.stem.lower()
        suffix = original_path.suffix.lower()

        stem = stem.replace(" ", "-").replace("_", "-")
        stem = re.sub(r"[^a-z0-9-]", "-", stem)
        stem = re.sub(r"-{2,}", "-", stem).strip("-")
        if not stem:
            stem = "doc"

        return original_path.parent / f"{stem}{suffix}"

    def _apply_file_fixes(
        self, path: Path, violations: List[Violation], report: FixReport, dry_run: bool
    ):
        try:
            ns = self._layout.namespace_for_path(path)
            if ns is None:
                report.remaining_violations.extend(violations)
                return

            post = frontmatter.load(path)
            modified = False
            rel_path = str(path.relative_to(self.root_dir))
            fixed_start = len(report.fixed_violations)
            remaining_start = len(report.remaining_violations)

            for v in violations:
                if self._apply_single_fix(v, post, rel_path, report, ns):
                    modified = True
                else:
                    report.remaining_violations.append(v)

            if modified and not dry_run:
                try:
                    ensure_safe_write_path(root_dir=self.root_dir, target_path=path)
                except MeminitError as exc:
                    if exc.code == ErrorCode.PATH_ESCAPE:
                        del report.fixed_violations[fixed_start:]
                        del report.remaining_violations[remaining_start:]
                        report.remaining_violations.extend(violations)
                        report.remaining_violations.append(
                            Violation(
                                file=rel_path,
                                line=0,
                                rule="UNSAFE_PATH",
                                message=exc.message,
                                severity=Severity.ERROR,
                            )
                        )
                        return
                    raise

                post.metadata = normalize_yaml_scalar_footguns(post.metadata or {})
                content = frontmatter.dumps(post)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)

        except Exception as e:
            print(f"Failed to apply fixes to {path}: {e}")
            report.remaining_violations.extend(violations)

    def _apply_single_fix(
        self,
        violation: Violation,
        post: Any,
        rel_path: str,
        report: FixReport,
        ns: RepoConfig,
    ) -> bool:
        # Match based on rule + specific field if available
        if violation.rule == "SCHEMA_VALIDATION":
            actions = self._ensure_minimum_frontmatter(post, rel_path, ns)

            if not actions:
                return False

            if self._is_schema_compliant(post.metadata, ns):
                report.fixed_violations.extend(actions)
                return True

            # We changed the file, but do not claim compliance if the schema still fails.
            report.remaining_violations.append(violation)
            return True

        if violation.rule == "FRONTMATTER_MISSING":
            if not post.metadata:
                post.metadata = {}

            actions = self._ensure_minimum_frontmatter(post, rel_path, ns)

            if self._is_schema_compliant(post.metadata, ns):
                action = FixAction(
                    rel_path,
                    "Add frontmatter",
                    "Initialized required frontmatter fields",
                )
                report.fixed_violations.append(action)
                report.fixed_violations.extend(actions)
            else:
                # We changed the file, but do not claim compliance if the schema still fails.
                report.remaining_violations.append(violation)
            return True

        # Fallback for older message-based matching (legacy)
        modified = False

        if "last_updated" in violation.message and "last_updated" not in post.metadata:
            post.metadata["last_updated"] = date.today().isoformat()
            action = FixAction(rel_path, "Update last_updated", "Set to today's date")
            report.fixed_violations.append(action)
            modified = True

        if (
            "docops_version" in violation.message
            and "docops_version" not in post.metadata
        ):
            post.metadata["docops_version"] = str(ns.docops_version or "2.0")
            action = FixAction(rel_path, "Update docops_version", "Set to 2.0")
            report.fixed_violations.append(action)
            modified = True

        return modified

    def _ensure_minimum_frontmatter(
        self, post: Any, rel_path: str, ns: RepoConfig
    ) -> List[FixAction]:
        actions: List[FixAction] = []
        # Required schema fields
        if "docops_version" not in post.metadata:
            post.metadata["docops_version"] = str(ns.docops_version or "2.0")
            actions.append(FixAction(rel_path, "Update docops_version", "Set to 2.0"))
        if "last_updated" not in post.metadata:
            post.metadata["last_updated"] = date.today().isoformat()
            actions.append(
                FixAction(rel_path, "Update last_updated", "Set to today's date")
            )
        if "status" not in post.metadata:
            post.metadata["status"] = "Draft"
            actions.append(FixAction(rel_path, "Set status", "Set to Draft"))
        if "version" not in post.metadata:
            post.metadata["version"] = "0.1"
            actions.append(FixAction(rel_path, "Set version", "Set to 0.1"))
        if "owner" not in post.metadata:
            post.metadata["owner"] = "__TBD__"
            actions.append(FixAction(rel_path, "Set owner", "Set to __TBD__"))

        inferred_type = self._infer_doc_type(rel_path, ns)
        if "type" not in post.metadata:
            post.metadata["type"] = inferred_type
            actions.append(FixAction(rel_path, "Set type", f"Set to {inferred_type}"))

        inferred_title = self._infer_title(post.content, Path(rel_path).stem)
        if "title" not in post.metadata:
            post.metadata["title"] = inferred_title
            actions.append(
                FixAction(
                    rel_path, "Set title", "Inferred from first heading or filename"
                )
            )

        if "document_id" not in post.metadata:
            new_id = self._generate_unique_document_id(inferred_type, ns)
            post.metadata["document_id"] = new_id
            actions.append(
                FixAction(rel_path, "Set document_id", "Generated a new unique ID")
            )

        return actions

    def _infer_doc_type(self, rel_path: str, ns: RepoConfig) -> str:
        try:
            parts = Path(rel_path).parts
        except Exception:
            return "DOC"

        docs_root = ns.docs_root.strip("/").replace("\\", "/")
        docs_root_parts = tuple(Path(docs_root).parts) if docs_root else ()
        if docs_root_parts and tuple(parts[: len(docs_root_parts)]) == docs_root_parts:
            rel_to_docs = Path(*parts[len(docs_root_parts) :])
            candidates: list[tuple[int, str]] = []
            for doc_type, subdir in ns.type_directories.items():
                sub_parts = Path(subdir).parts
                if rel_to_docs.parts[: len(sub_parts)] == sub_parts:
                    candidates.append((len(sub_parts), doc_type))
            if candidates:
                candidates.sort(reverse=True)
                return candidates[0][1]
        return "DOC"

    def _infer_title(self, body: str, fallback_stem: str) -> str:
        for line in body.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                title = stripped.lstrip("#").strip()
                if title:
                    return title
        return fallback_stem.replace("-", " ").strip().title() or "Untitled"

    def _is_schema_compliant(self, metadata: Dict[str, Any], ns: RepoConfig) -> bool:
        normalized = self._normalize_metadata_for_schema(metadata)
        validator = self._get_schema_validator(ns)
        if not validator.is_ready():
            return False
        return validator.validate_data(normalized) is None

    def _get_schema_validator(self, ns: RepoConfig) -> SchemaValidator:
        key = ns.schema_path
        existing = self._schema_validators.get(key)
        if existing:
            return existing
        v = SchemaValidator(str(ns.schema_file))
        self._schema_validators[key] = v
        return v

    def _normalize_metadata_for_schema(
        self, metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        # Keep in sync with checker normalization to avoid YAML scalar false positives.
        return normalize_yaml_scalar_footguns(metadata)

    def _scan_existing_document_ids(self) -> set[str]:
        ids: set[str] = set()
        for ns in self._layout.namespaces:
            docs_dir = ns.docs_dir
            if not docs_dir.exists():
                continue
            for path in docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue

                try:
                    post = frontmatter.load(path)
                    doc_id = post.metadata.get("document_id")
                    if isinstance(doc_id, str) and doc_id.strip():
                        ids.add(doc_id.strip())
                except Exception:
                    continue

        return ids

    def _generate_unique_document_id(self, doc_type: str, ns: RepoConfig) -> str:
        repo_prefix = ns.repo_prefix
        id_type = self._id_type_segment(doc_type)

        pattern = re.compile(
            rf"^{re.escape(repo_prefix)}-{re.escape(id_type)}-(\d{{3}})$"
        )
        max_seq = 0
        for existing in self._existing_document_ids:
            match = pattern.match(existing)
            if match:
                max_seq = max(max_seq, int(match.group(1)))

        next_seq = max_seq + 1
        # Ensure uniqueness even if there are gaps/collisions.
        while True:
            candidate = f"{repo_prefix}-{id_type}-{next_seq:03d}"
            if candidate not in self._existing_document_ids:
                self._existing_document_ids.add(candidate)
                return candidate
            next_seq += 1

    def _id_type_segment(self, doc_type: str) -> str:
        doc_type_upper = str(doc_type).upper()
        if doc_type_upper == "GOVERNANCE":
            return "GOV"
        if 3 <= len(doc_type_upper) <= 10 and doc_type_upper.isalpha():
            return doc_type_upper
        segment = re.sub(r"[^A-Z]", "", doc_type_upper)[:10]
        return segment if len(segment) >= 3 else "DOC"
