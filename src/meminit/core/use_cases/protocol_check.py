"""Protocol check use case: detect drift in governed protocol assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from meminit.core.services.protocol_assets import (
    DriftOutcome,
    ProtocolAssetRegistry,
    classify_drift,
    resolve_repo_metadata,
)
from meminit.core.services.safe_fs import ensure_existing_regular_file_path


@dataclass(frozen=True)
class ProtocolCheckReport:
    """Result of a protocol check run."""

    summary: Dict[str, int]
    assets: List[Dict]
    success: bool


class ProtocolChecker:
    """Detect drift in governed protocol assets (read-only)."""

    def __init__(
        self,
        root_dir: str,
        registry: Optional[ProtocolAssetRegistry] = None,
    ) -> None:
        self._root_dir = Path(root_dir).resolve()
        self._registry = registry or ProtocolAssetRegistry.default()

    def execute(
        self,
        asset_ids: Optional[List[str]] = None,
    ) -> ProtocolCheckReport:
        """Check protocol assets for drift.

        Args:
            asset_ids: Optional list of asset IDs to check. Defaults to all.
                Unknown IDs raise MeminitError.

        Returns:
            ProtocolCheckReport with per-asset status and summary.
        """
        if asset_ids is not None:
            self._registry.validate_asset_ids(asset_ids)

        assets = self._registry.assets
        if asset_ids is not None:
            # Preserve caller order while preventing duplicate work on the same
            # asset when repeatable --asset flags are used.
            unique_asset_ids = list(dict.fromkeys(asset_ids))
            filtered = []
            for aid in unique_asset_ids:
                a = self._registry.get_by_id(aid)
                if a is not None:
                    filtered.append(a)
            assets = tuple(filtered)

        project_name, repo_prefix = resolve_repo_metadata(self._root_dir)

        statuses = []
        for asset in assets:
            target = self._root_dir / asset.target_path
            on_disk_content = None
            on_disk_mode = None
            if target.exists() or target.is_symlink():
                ensure_existing_regular_file_path(
                    root_dir=self._root_dir,
                    target_path=target,
                )
                on_disk_mode = target.stat().st_mode & 0o777
                on_disk_content = target.read_bytes().decode(
                    "utf-8", errors="surrogateescape"
                )

            canonical = asset.render(project_name=project_name, repo_prefix=repo_prefix)
            status = classify_drift(
                asset,
                canonical,
                on_disk_content,
                on_disk_mode,
            )
            statuses.append(status)

        # Sort by asset_id for determinism
        statuses.sort(key=lambda s: s.asset_id)

        aligned = sum(1 for s in statuses if s.status == DriftOutcome.ALIGNED)
        unparseable = sum(1 for s in statuses if s.status == DriftOutcome.UNPARSEABLE)
        drifted = sum(
            1
            for s in statuses
            if s.status not in (DriftOutcome.ALIGNED, DriftOutcome.UNPARSEABLE)
        )

        asset_dicts = []
        for s in statuses:
            d: Dict = {
                "id": s.asset_id,
                "target_path": s.target_path,
                "ownership": s.ownership,
                "status": s.status.value,
                "auto_fixable": s.auto_fixable,
            }
            if s.expected_version is not None:
                d["expected_version"] = s.expected_version
            if s.recorded_version is not None:
                d["recorded_version"] = s.recorded_version
            if s.expected_sha256 is not None:
                d["expected_sha256"] = s.expected_sha256
            if s.recorded_sha256 is not None:
                d["recorded_sha256"] = s.recorded_sha256
            if s.actual_sha256 is not None:
                d["actual_sha256"] = s.actual_sha256
            if s.expected_file_mode is not None:
                d["expected_file_mode"] = s.expected_file_mode
            if s.actual_file_mode is not None:
                d["actual_file_mode"] = s.actual_file_mode
            asset_dicts.append(d)

        return ProtocolCheckReport(
            summary={
                "total": len(statuses),
                "aligned": aligned,
                "drifted": drifted,
                "unparseable": unparseable,
            },
            assets=asset_dicts,
            success=(drifted == 0 and unparseable == 0),
        )
