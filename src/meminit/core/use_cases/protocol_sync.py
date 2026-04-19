"""Protocol sync use case: safely remediate drift in governed protocol assets."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.protocol_assets import (
    AssetOwnership,
    DriftOutcome,
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
        if asset_ids:
            self._registry.validate_asset_ids(asset_ids)

        # Run checker to get current statuses
        from meminit.core.use_cases.protocol_check import ProtocolChecker

        checker = ProtocolChecker(str(self._root_dir), self._registry)
        check_report = checker.execute(asset_ids=asset_ids)

        project_name, repo_prefix = resolve_repo_metadata(self._root_dir)

        results: List[SyncAssetResult] = []
        warnings: List[Dict] = []
        any_write = False

        for asset_status in check_report.assets:
            prior = asset_status["status"]
            action = _decide_action(prior, force)

            preserved_bytes = None
            if action == "rewrite" and not dry_run:
                asset_desc = self._registry.get_by_id(asset_status["id"])
                if asset_desc is None:
                    continue
                preserved_bytes = self._rewrite_asset(
                    asset_desc, prior, project_name, repo_prefix,
                )
                any_write = True

            results.append(
                SyncAssetResult(
                    id=asset_status["id"],
                    target_path=asset_status["target_path"],
                    prior_status=prior,
                    action=action,
                    preserved_user_bytes=preserved_bytes,
                )
            )

        results.sort(key=lambda r: r.id)

        if force and any_write:
            warnings.append({
                "code": "PROTOCOL_SYNC_FORCE_USED",
                "message": "Force mode was used; tampered assets were overwritten",
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
            applied=any_write and not dry_run,
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
        asset: "ProtocolAsset",
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

        canonical_bytes = canonical.encode("utf-8")

        # Append user bytes verbatim (no normalization, no extra separator)
        # Canonical already ends with \n, so no separator needed
        if user_bytes is not None and preserved_bytes is not None and preserved_bytes > 0:
            full_content = canonical_bytes + user_bytes
        else:
            full_content = canonical_bytes

        atomic_write(target, full_content)

        # Apply file mode if declared
        if asset.file_mode is not None:
            try:
                target.chmod(asset.file_mode)
            except OSError:
                pass

        return preserved_bytes


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
