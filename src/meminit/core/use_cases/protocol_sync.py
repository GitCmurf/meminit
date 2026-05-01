"""Protocol sync use case: safely remediate drift in governed protocol assets."""

from __future__ import annotations

import errno
import logging
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, List, Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.warning_codes import WarningCode
from meminit.core.services.protocol_assets import (
    AssetOwnership,
    DriftOutcome,
    ProtocolAsset,
    ProtocolAssetRegistry,
    parse_protocol_markers,
    resolve_repo_metadata,
)
from meminit.core.services.safe_fs import (
    atomic_write,
    ensure_existing_regular_file_path,
    ensure_safe_write_path,
)


@dataclass(frozen=True)
class SyncAssetResult:
    """Per-asset sync outcome."""

    id: str
    target_path: str
    prior_status: str
    action: str  # "noop" | "rewrite" | "refuse"
    preserved_user_bytes: Optional[int] = None


@dataclass(frozen=True)
class ProtocolSyncReport:
    """Result of a protocol sync run."""

    dry_run: bool
    applied: bool
    summary: Dict[str, int]
    assets: List[Dict]
    success: bool
    warnings: List[Dict] = field(default_factory=list)


class ProtocolSyncer:
    """Synchronize governed protocol assets with the canonical contract."""

    def __init__(
        self,
        root_dir: str,
        registry: Optional[ProtocolAssetRegistry] = None,
    ) -> None:
        self._root_dir = Path(root_dir).resolve()
        self._registry = registry or ProtocolAssetRegistry.default()

    def execute(
        self,
        dry_run: bool = True,
        force: bool = False,
        asset_ids: Optional[List[str]] = None,
    ) -> ProtocolSyncReport:
        """Sync protocol assets.

        Args:
            dry_run: Preview without writing (default True).
            force: Allow overwriting tampered assets.
            asset_ids: Optional list of asset IDs to sync. Defaults to all.

        Returns:
            ProtocolSyncReport with per-asset results and summary.
        """
        if asset_ids is not None:
            self._registry.validate_asset_ids(asset_ids)

        # Run checker to get current statuses
        from meminit.core.use_cases.protocol_check import ProtocolChecker

        checker = ProtocolChecker(str(self._root_dir), self._registry)
        check_report = checker.execute(asset_ids=asset_ids)

        project_name, repo_prefix = resolve_repo_metadata(self._root_dir)

        planned: List[tuple[Dict, ProtocolAsset, str, str]] = []
        refuse_found = False

        for asset_status in check_report.assets:
            prior = asset_status["status"]
            action = _decide_action(prior, force)
            asset_desc = self._registry.get_by_id(asset_status["id"])
            if asset_desc is None:
                continue
            planned.append((asset_status, asset_desc, prior, action))
            if action == "refuse":
                refuse_found = True

        results: List[SyncAssetResult] = [
            SyncAssetResult(
                id=asset_status["id"],
                target_path=asset_status["target_path"],
                prior_status=prior,
                action=action,
                preserved_user_bytes=None,
            )
            for asset_status, _, prior, action in planned
        ]

        warnings: List[Dict] = []
        any_mutation = False
        rewrote_content = False
        tampered_rewritten = False
        mode_repaired = False

        if not dry_run:
            for idx, (_, asset_desc, prior, action) in enumerate(planned):
                if action == "refuse":
                    continue
                if action == "rewrite":
                    preserved_bytes = self._rewrite_asset(
                        asset_desc, prior, project_name, repo_prefix,
                    )
                    results[idx] = replace(
                        results[idx], preserved_user_bytes=preserved_bytes
                    )
                    rewrote_content = True
                    any_mutation = True
                    if prior == DriftOutcome.TAMPERED.value:
                        tampered_rewritten = True
                elif action == "noop" and asset_desc.file_mode is not None:
                    if self._apply_file_mode_if_needed(asset_desc):
                        mode_repaired = True
                        any_mutation = True

        results.sort(key=lambda r: r.id)

        if force:
            force_message = "Force mode was requested"
            if dry_run:
                force_message += " (dry run; no assets were rewritten)"
            elif refuse_found:
                if rewrote_content or mode_repaired:
                    force_message += "; non-refused assets were synced; refused assets were left untouched"
                else:
                    force_message += "; no assets were synced (all were refused or noop)"
            elif tampered_rewritten:
                force_message += "; tampered assets were overwritten"
            elif rewrote_content:
                force_message += "; no tampered assets required rewriting; safe assets were synced"
            elif mode_repaired:
                force_message += "; no tampered assets required rewriting; registered file modes were repaired"
            else:
                force_message += "; no tampered assets required rewriting"
            warnings.append({
                "code": WarningCode.PROTOCOL_SYNC_FORCE_USED,
                "message": force_message,
                "path": str(self._root_dir),
            })

        rewritten = sum(1 for r in results if r.action == "rewrite")
        refused = sum(1 for r in results if r.action == "refuse")
        noop = sum(1 for r in results if r.action == "noop")
        total = len(results)

        asset_dicts: List[Dict] = []
        for r in results:
            d: Dict = {
                "id": r.id,
                "target_path": r.target_path,
                "prior_status": r.prior_status,
                "action": r.action,
            }
            if r.preserved_user_bytes is not None:
                d["preserved_user_bytes"] = r.preserved_user_bytes
            asset_dicts.append(d)

        return ProtocolSyncReport(
            dry_run=dry_run,
            applied=any_mutation and not dry_run,
            summary={
                "total": total,
                "rewritten": rewritten,
                "refused": refused,
                "noop": noop,
            },
            assets=asset_dicts,
            success=(refused == 0 and (not dry_run or noop == total)),
            warnings=warnings,
        )

    def _rewrite_asset(
        self,
        asset: ProtocolAsset,
        prior_status: str,
        project_name: str,
        repo_prefix: str,
    ) -> Optional[int]:
        """Rewrite a protocol asset to disk. Returns preserved user bytes for mixed assets."""
        canonical = asset.render(project_name=project_name, repo_prefix=repo_prefix)
        target = self._root_dir / asset.target_path

        ensure_safe_write_path(root_dir=self._root_dir, target_path=target)
        target.parent.mkdir(parents=True, exist_ok=True)

        preserved_bytes: Optional[int] = None
        user_bytes: Optional[bytes] = None

        if asset.ownership == AssetOwnership.MIXED:
            if target.exists() or target.is_symlink():
                ensure_existing_regular_file_path(
                    root_dir=self._root_dir,
                    target_path=target,
                )
                if prior_status == DriftOutcome.LEGACY.value:
                    user_bytes = target.read_bytes()
                    preserved_bytes = len(user_bytes)
                else:
                    existing_bytes = target.read_bytes()
                    existing_text = existing_bytes.decode(
                        "utf-8", errors="surrogateescape"
                    )
                    parsed = parse_protocol_markers(existing_text)
                    if parsed is not None:
                        # Compute byte offset from raw bytes directly.
                        # read_text() normalizes \r\n to \n, so counting bytes
                        # from text-mode lines undercounts by 1 per CRLF line.
                        # bytes.split(b'\n') preserves \r in each element.
                        raw_parts = existing_bytes.split(b"\n")
                        byte_offset = 0
                        for i in range(parsed.end_line + 1):
                            byte_offset += len(raw_parts[i])
                            if i < len(raw_parts) - 1:
                                byte_offset += 1  # the \n that split() removed
                        user_bytes = existing_bytes[byte_offset:]
                        preserved_bytes = len(user_bytes)
                    else:
                        user_bytes = existing_bytes
                        preserved_bytes = len(user_bytes)
                        logging.warning(
                            "Protocol markers disappeared for %s between "
                            "check and sync; preserving full file content",
                            asset.target_path,
                        )

        canonical_bytes = canonical.encode("utf-8")

        # Append user bytes verbatim (no normalization, no extra separator)
        # Canonical already ends with \n, so no separator needed
        if user_bytes is not None and preserved_bytes is not None and preserved_bytes > 0:
            full_content = canonical_bytes + user_bytes
        else:
            full_content = canonical_bytes

        try:
            atomic_write(target, full_content, file_mode=asset.file_mode)
        except OSError as exc:
            if exc.errno in (errno.EPERM, errno.EACCES):
                reason = "permission denied"
            elif exc.errno == errno.ENOSPC:
                reason = "disk full"
            else:
                reason = str(exc)
            raise MeminitError(
                code=ErrorCode.PROTOCOL_SYNC_WRITE_FAILED,
                message=f"Failed to write protocol asset {asset.target_path}: {reason}",
                details={
                    "target_path": asset.target_path,
                    "expected_mode": asset.file_mode,
                    "reason": reason,
                },
            ) from exc

        return preserved_bytes

    def _apply_file_mode_if_needed(self, asset: ProtocolAsset) -> bool:
        """Ensure the registered executable bit is present.

        Returns True when the file mode was changed.
        """
        if asset.file_mode is None:
            return False

        target = self._root_dir / asset.target_path
        ensure_safe_write_path(root_dir=self._root_dir, target_path=target)
        ensure_existing_regular_file_path(
            root_dir=self._root_dir, target_path=target,
        )
        try:
            current_mode = target.stat().st_mode & 0o777
            if current_mode == asset.file_mode:
                return False
            target.chmod(asset.file_mode)
            return True
        except OSError as exc:
            raise MeminitError(
                code=ErrorCode.PROTOCOL_SYNC_WRITE_FAILED,
                message=(
                    f"Failed to apply file mode {oct(asset.file_mode)} to "
                    f"{asset.target_path}"
                ),
                details={
                    "target_path": asset.target_path,
                    "expected_mode": asset.file_mode,
                    "reason": str(exc),
                },
            ) from exc


def _decide_action(prior_status: str, force: bool) -> str:
    """Decide sync action based on prior drift status and force flag."""
    if prior_status == DriftOutcome.ALIGNED.value:
        return "noop"
    if prior_status == DriftOutcome.TAMPERED.value:
        return "rewrite" if force else "refuse"
    if prior_status == DriftOutcome.UNPARSEABLE.value:
        return "refuse"
    # MISSING, LEGACY, STALE
    return "rewrite"
