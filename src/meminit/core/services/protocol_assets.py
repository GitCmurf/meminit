"""Protocol asset registry, marker parsing, drift classification, and normalization.

Provides the single source of truth for which repo-local files are governable
protocol assets, how drift is classified, and how canonical payloads are
rendered.  Consumed by ``init``, ``protocol check``, and ``protocol sync``.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from importlib import resources
from pathlib import Path
from typing import Optional, Tuple

from meminit.core.services.repo_config import load_repo_config


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PROTOCOL_ASSET_VERSION = "1.0"

_MARKER_BEGIN_RE = re.compile(
    r"^<!--\s+MEMINIT_PROTOCOL:\s+begin\s+id=(\S+)\s+version=(\S+)\s+sha256=([0-9a-fA-F]{64})\s+-->$"
)
_MARKER_END_RE = re.compile(
    r"^<!--\s+MEMINIT_PROTOCOL:\s+end\s+id=(\S+)\s+-->$"
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class AssetOwnership(str, Enum):
    GENERATED = "generated"
    MIXED = "mixed"


class DriftOutcome(str, Enum):
    ALIGNED = "aligned"
    MISSING = "missing"
    LEGACY = "legacy"
    STALE = "stale"
    TAMPERED = "tampered"
    UNPARSEABLE = "unparseable"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProtocolAsset:
    """Definition of a single governable protocol asset."""

    id: str
    target_path: str
    package_resource: str
    ownership: AssetOwnership
    file_mode: Optional[int] = None

    def render(self, *, project_name: str = "", repo_prefix: str = "") -> str:
        """Load canonical payload from package resources, interpolate, wrap."""
        content = (
            resources.files("meminit.core.assets")
            .joinpath(self.package_resource)
            .read_text(encoding="utf-8")
        )
        content = content.replace("{{PROJECT_NAME}}", project_name)
        content = content.replace("{{REPO_PREFIX}}", repo_prefix)

        if self.ownership == AssetOwnership.MIXED:
            normalized = normalize_protocol_payload(content)
            sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            begin = f"<!-- MEMINIT_PROTOCOL: begin id={self.id} version={PROTOCOL_ASSET_VERSION} sha256={sha} -->"
            end = f"<!-- MEMINIT_PROTOCOL: end id={self.id} -->"
            return f"{begin}\n{normalized}{end}\n"

        return normalize_protocol_payload(content)


@dataclass
class ParsedMarkers:
    """Parsed MEMINIT_PROTOCOL region from a mixed-ownership file."""

    asset_id: str
    version: str
    recorded_sha256: str
    managed_payload: str
    begin_line: int
    end_line: int


@dataclass(frozen=True)
class DriftStatus:
    """Per-asset drift classification result."""

    asset_id: str
    target_path: str
    ownership: str
    status: DriftOutcome
    expected_version: Optional[str] = None
    recorded_version: Optional[str] = None
    expected_sha256: Optional[str] = None
    recorded_sha256: Optional[str] = None
    actual_sha256: Optional[str] = None
    auto_fixable: bool = False


@dataclass(frozen=True)
class ProtocolAssetRegistry:
    """Immutable registry of all governable protocol assets."""

    assets: tuple[ProtocolAsset, ...] = ()

    def __post_init__(self) -> None:
        ids = [a.id for a in self.assets]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Duplicate asset IDs in registry: {ids}")
        object.__setattr__(self, "_by_id", {a.id: a for a in self.assets})
        object.__setattr__(self, "_ids", tuple(ids))

    def get_by_id(self, asset_id: str) -> Optional[ProtocolAsset]:
        return self._by_id.get(asset_id)

    def validate_asset_ids(self, asset_ids) -> None:
        from meminit.core.services.error_codes import ErrorCode, MeminitError
        unknown = [aid for aid in asset_ids if aid not in self._ids]
        if unknown:
            raise MeminitError(
                code=ErrorCode.INVALID_FLAG_COMBINATION,
                message=f"Unknown asset IDs: {', '.join(sorted(unknown))}. "
                f"Valid IDs: {', '.join(self._ids)}",
                details={"unknown_ids": sorted(unknown), "valid_ids": list(self._ids)},
            )

    @property
    def ids(self) -> Tuple[str, ...]:
        return self._ids

    @classmethod
    def default(cls) -> ProtocolAssetRegistry:
        return cls(
            assets=(
                ProtocolAsset(
                    id="agents-md",
                    target_path="AGENTS.md",
                    package_resource="AGENTS.md",
                    ownership=AssetOwnership.MIXED,
                ),
                ProtocolAsset(
                    id="meminit-docops-skill",
                    target_path=".agents/skills/meminit-docops/SKILL.md",
                    package_resource="meminit-docops-skill.md",
                    ownership=AssetOwnership.GENERATED,
                ),
                ProtocolAsset(
                    id="meminit-brownfield-script",
                    target_path=".agents/skills/meminit-docops/scripts/meminit_brownfield_plan.sh",
                    package_resource="scripts/meminit_brownfield_plan.sh",
                    ownership=AssetOwnership.GENERATED,
                    file_mode=0o755,
                ),
            )
        )


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_protocol_payload(content: str) -> str:
    """Normalize content for deterministic hashing.

    1. Convert all line endings to LF.
    2. Strip trailing whitespace from each line.
    3. Remove trailing empty lines.
    4. Ensure exactly one trailing newline.
    """
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in content.split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines) + "\n"


def _sha256_normalized_text(content: str) -> str:
    """Hash normalized text using surrogate-safe UTF-8 encoding.

    Surrogate escape preserves any non-UTF-8 bytes that were decoded from disk
    so byte-preserving protocol workflows can classify drift without crashing.
    """
    return hashlib.sha256(
        normalize_protocol_payload(content).encode("utf-8", errors="surrogateescape")
    ).hexdigest()


# ---------------------------------------------------------------------------
# Marker parsing
# ---------------------------------------------------------------------------


def parse_protocol_markers(content: str) -> Optional[ParsedMarkers]:
    """Parse MEMINIT_PROTOCOL markers from file content.

    Returns ``None`` if no begin marker is found (legacy state).
    Raises ``ValueError`` if markers are malformed (unparseable state).
    Returns ``ParsedMarkers`` on success.

    Validation rules (unparseable if violated):
    - Begin marker must be the first non-blank line (no preamble allowed).
    - Exactly one begin marker and exactly one end marker.
    - No protocol markers may appear outside the managed region.
    """
    lines = content.split("\n")

    begin_indices = [
        i for i, line in enumerate(lines) if _MARKER_BEGIN_RE.match(line.strip())
    ]

    if not begin_indices:
        # Any MEMINIT_PROTOCOL marker text without a valid begin marker is
        # malformed. This covers stray end markers, malformed begin markers,
        # and any other protocol-marker text that cannot be parsed as a valid
        # managed region header.
        if any("MEMINIT_PROTOCOL" in line for line in lines):
            raise ValueError("MEMINIT_PROTOCOL marker text found without begin marker")
        return None

    if len(begin_indices) > 1:
        raise ValueError("Multiple MEMINIT_PROTOCOL begin markers found")

    begin_idx = begin_indices[0]

    # Reject preamble before begin marker
    for line in lines[:begin_idx]:
        if line.strip():
            raise ValueError("Non-blank content before MEMINIT_PROTOCOL begin marker")

    begin_match = _MARKER_BEGIN_RE.match(lines[begin_idx].strip())
    if not begin_match:
        raise ValueError("Malformed MEMINIT_PROTOCOL begin marker")

    asset_id = begin_match.group(1)
    version = begin_match.group(2)
    recorded_sha = begin_match.group(3)

    end_indices = [
        i
        for i, line in enumerate(lines[begin_idx + 1 :], start=begin_idx + 1)
        if _MARKER_END_RE.match(line.strip())
    ]

    if not end_indices:
        raise ValueError("Missing MEMINIT_PROTOCOL end marker")

    end_idx = end_indices[0]
    end_match = _MARKER_END_RE.match(lines[end_idx].strip())
    end_id = end_match.group(1) if end_match else ""

    if end_id != asset_id:
        raise ValueError(
            f"MEMINIT_PROTOCOL end marker id '{end_id}' does not match begin id '{asset_id}'"
        )

    # Reject protocol markers outside the managed region (after end marker)
    for line in lines[end_idx + 1 :]:
        stripped = line.strip()
        if _MARKER_BEGIN_RE.match(stripped) or _MARKER_END_RE.match(stripped):
            raise ValueError("Protocol markers found outside the managed region")

    managed_payload = "\n".join(lines[begin_idx + 1 : end_idx])

    return ParsedMarkers(
        asset_id=asset_id,
        version=version,
        recorded_sha256=recorded_sha,
        managed_payload=managed_payload,
        begin_line=begin_idx,
        end_line=end_idx,
    )


# ---------------------------------------------------------------------------
# Drift classification
# ---------------------------------------------------------------------------


def classify_drift(
    asset: ProtocolAsset,
    canonical_render: str,
    on_disk_content: Optional[str],
) -> DriftStatus:
    """Classify the drift state of a single protocol asset.

    Classification order (plan-012 section 3.2.2):
    1. missing: target path absent
    2. For generated assets: normalize whole file, compare -> aligned/stale
    3. For mixed assets: no markers -> legacy
    4. For mixed assets with markers: malformed -> unparseable
    5. For mixed assets with parseable markers: hash mismatch -> tampered
    6. For mixed assets self-consistent: version/hash mismatch vs canonical -> stale/aligned
    """
    # For mixed assets, the comparison hash is of the managed payload only
    # (what's stored in the begin marker sha256 attribute), not the full
    # render including markers.
    if asset.ownership == AssetOwnership.MIXED:
        canonical_parsed = parse_protocol_markers(canonical_render)
        canonical_sha = (
            canonical_parsed.recorded_sha256
            if canonical_parsed
            else _sha256_normalized_text(canonical_render)
        )
    else:
        canonical_sha = _sha256_normalized_text(canonical_render)

    # 1. Missing
    if on_disk_content is None:
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.MISSING,
            expected_version=PROTOCOL_ASSET_VERSION,
            expected_sha256=canonical_sha,
            auto_fixable=True,
        )

    # Fully generated assets: whole-file comparison
    if asset.ownership == AssetOwnership.GENERATED:
        disk_sha = _sha256_normalized_text(on_disk_content)
        if disk_sha == canonical_sha:
            return DriftStatus(
                asset_id=asset.id,
                target_path=asset.target_path,
                ownership=asset.ownership.value,
                status=DriftOutcome.ALIGNED,
                expected_version=PROTOCOL_ASSET_VERSION,
                expected_sha256=canonical_sha,
                actual_sha256=disk_sha,
            )
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.STALE,
            expected_version=PROTOCOL_ASSET_VERSION,
            expected_sha256=canonical_sha,
            actual_sha256=disk_sha,
            auto_fixable=True,
        )

    # Mixed-ownership assets
    try:
        parsed = parse_protocol_markers(on_disk_content)
    except ValueError:
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.UNPARSEABLE,
            auto_fixable=False,
        )

    # 3. No markers found -> legacy
    if parsed is None:
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.LEGACY,
            expected_version=PROTOCOL_ASSET_VERSION,
            expected_sha256=canonical_sha,
            auto_fixable=True,
        )

    # 5. Parseable markers: recompute hash of managed payload
    actual_sha = _sha256_normalized_text(parsed.managed_payload)

    if actual_sha != parsed.recorded_sha256:
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.TAMPERED,
            expected_version=PROTOCOL_ASSET_VERSION,
            recorded_version=parsed.version,
            expected_sha256=canonical_sha,
            recorded_sha256=parsed.recorded_sha256,
            actual_sha256=actual_sha,
            auto_fixable=False,
        )

    # 6. Self-consistent: compare version and hash against canonical
    version_match = parsed.version == PROTOCOL_ASSET_VERSION
    hash_match = actual_sha == canonical_sha
    if version_match and hash_match:
        return DriftStatus(
            asset_id=asset.id,
            target_path=asset.target_path,
            ownership=asset.ownership.value,
            status=DriftOutcome.ALIGNED,
            expected_version=PROTOCOL_ASSET_VERSION,
            recorded_version=parsed.version,
            expected_sha256=canonical_sha,
            recorded_sha256=parsed.recorded_sha256,
            actual_sha256=actual_sha,
        )

    return DriftStatus(
        asset_id=asset.id,
        target_path=asset.target_path,
        ownership=asset.ownership.value,
        status=DriftOutcome.STALE,
        expected_version=PROTOCOL_ASSET_VERSION,
        recorded_version=parsed.version,
        expected_sha256=canonical_sha,
        recorded_sha256=parsed.recorded_sha256,
        actual_sha256=actual_sha,
        auto_fixable=True,
    )


# ---------------------------------------------------------------------------
# Repo metadata resolution (shared by init, check, sync)
# ---------------------------------------------------------------------------


def resolve_repo_metadata(root_dir: Path) -> Tuple[str, str]:
    """Resolve project_name and repo_prefix from the repository."""
    config = load_repo_config(root_dir)
    return config.project_name, config.repo_prefix
