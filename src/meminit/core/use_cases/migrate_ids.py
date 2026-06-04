from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import frontmatter

from meminit.core.domain.document_ids import document_id_type_segment
from meminit.core.services.metadata_normalization import normalize_yaml_scalar_footguns
from meminit.core.services.repo_config import RepoConfig, RepoLayout, load_repo_layout
from meminit.core.services.safe_fs import ensure_safe_write_path

_DOC_ID_LINE_RE = re.compile(r"^(> \*\*Document ID:\*\* )(.+?)(\s*)$", re.IGNORECASE)


@dataclass(frozen=True)
class IdMigrationAction:
    file: str
    old_id: str
    new_id: str
    doc_type: str
    updated_frontmatter: bool
    updated_metadata_block: bool
    updated_heading: bool
    rewritten_reference_count: int


@dataclass(frozen=True)
class IdMigrationReport:
    dry_run: bool
    actions: List[IdMigrationAction]
    skipped_files: List[str]
    advice: List[dict[str, str]]

    def as_dict(self) -> dict:
        return {
            "dry_run": self.dry_run,
            "actions": [
                {
                    "file": a.file,
                    "old_id": a.old_id,
                    "new_id": a.new_id,
                    "doc_type": a.doc_type,
                    "updated_frontmatter": a.updated_frontmatter,
                    "updated_metadata_block": a.updated_metadata_block,
                    "updated_heading": a.updated_heading,
                    "rewritten_reference_count": a.rewritten_reference_count,
                }
                for a in self.actions
            ],
            "skipped_files": self.skipped_files,
            "advice": self.advice,
        }


class MigrateIdsUseCase:
    """
    Rewrite legacy `document_id` values into the Meminit canonical format:
    `REPO-TYPE-SEQ` (e.g., `AIDHA-PRD-001`).

    Safety:
    - dry-run by default (caller decides whether to write)
    - only rewrites governed docs under docs_root
    - only rewrites frontmatter and known visible metadata block lines
    - optional reference rewriting (disabled by default)
    """

    def __init__(self, root_dir: str):
        self._layout: RepoLayout = load_repo_layout(root_dir)
        self._root_dir = self._layout.root_dir

    def execute(
        self,
        dry_run: bool = True,
        rewrite_references: bool = False,
        force_restamp: bool = False,
    ) -> IdMigrationReport:
        actions: List[IdMigrationAction] = []
        skipped: List[str] = []
        advice: List[dict[str, str]] = []

        used_numbers, canonical_id_counts = self._collect_id_metrics()
        next_numbers: Dict[Tuple[str, str], int] = {
            key: (max(nums) + 1 if nums else 1) for key, nums in used_numbers.items()
        }

        seen_canonical_ids: Set[str] = set()

        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                skipped.append(f"{ns.namespace}:docs_root_missing:{ns.docs_root}")
                continue

            type_by_subdir = self._invert_type_directories(ns)

            for path in sorted(ns.docs_dir.rglob("*.md")):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue

                rel_path = path.relative_to(self._root_dir).as_posix()
                try:
                    post = frontmatter.load(path)
                except Exception:
                    skipped.append(rel_path)
                    continue

                if not post.metadata:
                    skipped.append(rel_path)
                    continue

                old_id = post.metadata.get("document_id")
                if not isinstance(old_id, str) or not old_id.strip():
                    skipped.append(rel_path)
                    continue
                old_id = old_id.strip()

                doc_type = post.metadata.get("type")
                if not isinstance(doc_type, str) or not doc_type.strip():
                    inferred = self._infer_doc_type_from_path(path, ns, type_by_subdir)
                    if not inferred:
                        skipped.append(rel_path)
                        continue
                    doc_type = inferred
                else:
                    doc_type = doc_type.strip().upper()

                canonical_parts = self._parse_canonical_id(old_id)
                if canonical_parts:
                    old_prefix, old_type_segment, _old_seq = canonical_parts
                    expected_type_segment = document_id_type_segment(doc_type)
                    if old_prefix != ns.repo_prefix or old_type_segment != expected_type_segment:
                        # document_id is immutable once canonical. A prefix/type-segment
                        # mismatch is a valid, unique ID that merely disagrees with the
                        # namespace convention, so by default we surface it as advice and
                        # leave it untouched. Restamping is destructive (breaks external
                        # references), so it only happens when the caller explicitly opts
                        # in via force_restamp.
                        advice.append(
                            {
                                "code": "ID_PREFIX_MISMATCH",
                                "message": (
                                    f"{rel_path} uses {old_id}, but namespace "
                                    f"{ns.namespace} expects {ns.repo_prefix}-"
                                    f"{expected_type_segment}-SEQ."
                                ),
                            }
                        )
                        if force_restamp:
                            new_id = self._allocate_next_id(
                                ns.repo_prefix, expected_type_segment, used_numbers, next_numbers
                            )
                            actions.append(
                                self._migrate_post(
                                    path=path,
                                    rel_path=rel_path,
                                    post=post,
                                    old_id=old_id,
                                    new_id=new_id,
                                    doc_type=doc_type,
                                    dry_run=dry_run,
                                    rewrite_references=rewrite_references,
                                )
                            )
                        continue

                    # Check for duplicate canonical IDs
                    if canonical_id_counts.get(old_id, 0) > 1:
                        # This is a duplicate canonical ID situation
                        if old_id not in seen_canonical_ids:
                            # First occurrence - keep the ID, mark as seen
                            seen_canonical_ids.add(old_id)
                            continue
                        # Duplicate occurrence - renumber it
                        seen_canonical_ids.add(old_id)
                        actions.append(
                            self._migrate_post(
                                path=path,
                                rel_path=rel_path,
                                post=post,
                                old_id=old_id,
                                new_id=self._allocate_next_id(
                                    ns.repo_prefix,
                                    expected_type_segment,
                                    used_numbers,
                                    next_numbers,
                                ),
                                doc_type=doc_type,
                                dry_run=dry_run,
                                rewrite_references=rewrite_references,
                            )
                        )
                        continue
                    else:
                        # Single canonical ID - already correct, skip
                        continue

                # Non-canonical ID - migrate it
                actions.append(
                    self._migrate_post(
                        path=path,
                        rel_path=rel_path,
                        post=post,
                        old_id=old_id,
                        new_id=self._allocate_next_id(
                            ns.repo_prefix,
                            document_id_type_segment(doc_type),
                            used_numbers,
                            next_numbers,
                        ),
                        doc_type=doc_type,
                        dry_run=dry_run,
                        rewrite_references=rewrite_references,
                    )
                )

        return IdMigrationReport(
            dry_run=dry_run,
            actions=actions,
            skipped_files=sorted(set(skipped)),
            advice=advice,
        )

    def _parse_canonical_id(self, document_id: str) -> Optional[Tuple[str, str, int]]:
        match = re.match(r"^([A-Z]{3,10})-([A-Z]{3,10})-(\d{3})$", document_id)
        if not match:
            return None
        return match.group(1), match.group(2), int(match.group(3))

    def _migrate_post(
        self,
        *,
        path: Path,
        rel_path: str,
        post: Any,
        old_id: str,
        new_id: str,
        doc_type: str,
        dry_run: bool,
        rewrite_references: bool,
    ) -> IdMigrationAction:
        post.metadata["document_id"] = new_id

        content, md_updated = self._replace_metadata_block_id(post.content, old_id, new_id)
        post.content = content

        content, heading_updated = self._replace_first_heading_id(post.content, old_id, new_id)
        post.content = content

        rewritten_refs = 0
        if rewrite_references:
            content, rewritten_refs = self._replace_id_references(post.content, old_id, new_id)
            post.content = content

        if not dry_run:
            post.metadata = normalize_yaml_scalar_footguns(post.metadata or {})
            ensure_safe_write_path(root_dir=self._root_dir, target_path=path)
            path.write_text(frontmatter.dumps(post), encoding="utf-8")

        return IdMigrationAction(
            file=rel_path,
            old_id=old_id,
            new_id=new_id,
            doc_type=doc_type,
            updated_frontmatter=True,
            updated_metadata_block=md_updated,
            updated_heading=heading_updated,
            rewritten_reference_count=rewritten_refs,
        )

    def _collect_id_metrics(self) -> Tuple[Dict[Tuple[str, str], List[int]], Dict[str, int]]:
        """Collect both sequence numbers and canonical ID counts in a single pass."""
        used_numbers: Dict[Tuple[str, str], List[int]] = {}
        canonical_counts: Dict[str, int] = {}
        regex = re.compile(r"^([A-Z]{3,10})-([A-Z]{3,10})-(\d{3})$")

        for ns in self._layout.namespaces:
            if not ns.docs_dir.exists():
                continue
            for path in ns.docs_dir.rglob("*.md"):
                owner = self._layout.namespace_for_path(path)
                if owner is None or owner.namespace.lower() != ns.namespace.lower():
                    continue
                if ns.is_excluded(path):
                    continue
                try:
                    post = frontmatter.load(path)
                except Exception:
                    continue
                doc_id = post.metadata.get("document_id")
                if not isinstance(doc_id, str):
                    continue
                m = regex.match(doc_id.strip())
                if not m:
                    continue

                repo, doc_type, seq = m.group(1), m.group(2), m.group(3)
                canonical_id = f"{repo}-{doc_type}-{seq}"

                used_numbers.setdefault((repo, doc_type), []).append(int(seq))
                canonical_counts[canonical_id] = canonical_counts.get(canonical_id, 0) + 1

        return used_numbers, canonical_counts

    def _invert_type_directories(self, ns: RepoConfig) -> Dict[Tuple[str, ...], str]:
        inverted: Dict[Tuple[str, ...], str] = {}
        for doc_type, subdir in ns.type_directories.items():
            parts = tuple(Path(subdir).parts)
            if parts:
                inverted[parts] = doc_type
        # Sort by specificity (longest path first) when matching.
        return dict(sorted(inverted.items(), key=lambda kv: len(kv[0]), reverse=True))

    def _infer_doc_type_from_path(
        self, path: Path, ns: RepoConfig, type_by_subdir: Dict[Tuple[str, ...], str]
    ) -> Optional[str]:
        try:
            rel_to_docs = path.relative_to(ns.docs_dir)
        except ValueError:
            return None
        rel_parts = rel_to_docs.parts
        for parts, doc_type in type_by_subdir.items():
            if rel_parts[: len(parts)] == parts:
                return doc_type
        return None

    def _allocate_next_id(
        self,
        repo_prefix: str,
        doc_type: str,
        used_numbers: Dict[Tuple[str, str], List[int]],
        next_numbers: Dict[Tuple[str, str], int],
    ) -> str:
        key = (repo_prefix, doc_type)
        used_set = set(used_numbers.get(key, []))
        n = next_numbers.get(key, 1)
        while n in used_set:
            n += 1
        used_set.add(n)
        used_numbers.setdefault(key, []).append(n)
        next_numbers[key] = n + 1
        return f"{repo_prefix}-{doc_type}-{n:03d}"

    def _replace_metadata_block_id(self, text: str, old_id: str, new_id: str) -> Tuple[str, bool]:
        if "<!-- MEMINIT_METADATA_BLOCK" not in text:
            return text, False

        updated = False
        lines = text.splitlines()
        for i, line in enumerate(lines):
            m = _DOC_ID_LINE_RE.match(line.strip())
            if m and m.group(2).strip() == old_id:
                lines[i] = f"{m.group(1)}{new_id}{m.group(3)}"
                updated = True
        return "\n".join(lines), updated

    def _replace_first_heading_id(self, text: str, old_id: str, new_id: str) -> Tuple[str, bool]:
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("# "):
                if old_id in line:
                    lines[i] = line.replace(old_id, new_id, 1)
                    return "\n".join(lines), True
                return text, False
        return text, False

    def _replace_id_references(self, text: str, old_id: str, new_id: str) -> Tuple[str, int]:
        # Conservative word-boundary replacement.
        pattern = re.compile(rf"(?<![A-Z0-9-]){re.escape(old_id)}(?![A-Z0-9-])")
        new_text, n = pattern.subn(new_id, text)
        return new_text, n
