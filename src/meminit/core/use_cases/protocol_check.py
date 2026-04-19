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
        if asset_ids:
            self._registry.validate_asset_ids(asset_ids)

        assets = self._registry.assets
        if asset_ids:
            filtered = []
            for aid in asset_ids:
                a = self._registry.get_by_id(aid)
                if a is not None:
                    filtered.append(a)
            assets = tuple(filtered)

        project_name, repo_prefix = resolve_repo_metadata(self._root_dir)

        statuses = []
        for asset in assets:
            target = self._root_dir / asset.target_path
            on_disk_content = None
            if target.exists():
                on_disk_content = target.read_text(encoding="utf-8")

            canonical = asset.render(project_name=project_name, repo_prefix=repo_prefix)
            status = classify_drift(asset, canonical, on_disk_content)
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
