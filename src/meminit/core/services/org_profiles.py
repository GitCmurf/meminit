from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

from meminit.core.services.xdg_paths import get_xdg_paths


@dataclass(frozen=True)
class OrgProfile:
    name: str
    version: str
    docops_version: str
    files: Dict[str, bytes]  # repo-relative paths within the profile
    source: str  # "packaged" | "global"

    def digest(self) -> str:
        h = hashlib.sha256()
        for rel in sorted(self.files.keys()):
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            h.update(self.files[rel])
            h.update(b"\0")
        return h.hexdigest()


def global_profile_dir(profile_name: str, env: Optional[Mapping[str, str]] = None) -> Path:
    xdg = get_xdg_paths(env=env)
    return xdg.meminit_data_dir / "org" / "profiles" / profile_name


def packaged_profile_root(profile_name: str) -> Path:
    # This returns an importlib.resources Traversable, but we keep the interface path-like.
    # Callers should use `resources.files()` for traversal and reading.
    return Path("org_profiles") / profile_name


def _load_manifest_from_traversable(root: resources.abc.Traversable) -> dict:
    manifest_text = root.joinpath("profile.json").read_text(encoding="utf-8")
    return json.loads(manifest_text)


def _load_manifest_from_dir(root: Path) -> dict:
    return json.loads((root / "profile.json").read_text(encoding="utf-8"))


def _read_files_from_root(root: resources.abc.Traversable, rel_paths: Iterable[str]) -> Dict[str, bytes]:
    out: Dict[str, bytes] = {}
    for rel in rel_paths:
        p = root.joinpath(rel)
        out[rel] = p.read_bytes()
    return out


def _read_files_from_dir(root: Path, rel_paths: Iterable[str]) -> Dict[str, bytes]:
    out: Dict[str, bytes] = {}
    for rel in rel_paths:
        out[rel] = (root / rel).read_bytes()
    return out


def load_packaged_profile(profile_name: str = "default") -> OrgProfile:
    root = resources.files("meminit.core.assets").joinpath(str(packaged_profile_root(profile_name)))
    manifest = _load_manifest_from_traversable(root)
    rels = set(str(p) for p in (manifest.get("files", []) or []))
    rels.add("profile.json")
    files = _read_files_from_root(root, sorted(rels))
    return OrgProfile(
        name=manifest.get("profile_name", profile_name),
        version=str(manifest.get("profile_version", "0.0")),
        docops_version=str(manifest.get("docops_version", "2.0")),
        files=files,
        source="packaged",
    )


def load_global_profile(profile_name: str = "default", env: Optional[Mapping[str, str]] = None) -> OrgProfile:
    root = global_profile_dir(profile_name, env=env)
    manifest = _load_manifest_from_dir(root)
    rels = set(str(p) for p in (manifest.get("files", []) or []))
    rels.add("profile.json")
    files = _read_files_from_dir(root, sorted(rels))
    return OrgProfile(
        name=manifest.get("profile_name", profile_name),
        version=str(manifest.get("profile_version", "0.0")),
        docops_version=str(manifest.get("docops_version", "2.0")),
        files=files,
        source="global",
    )


def resolve_org_profile(
    profile_name: str = "default", env: Optional[Mapping[str, str]] = None, prefer_global: bool = True
) -> OrgProfile:
    """
    Resolve which org profile should be used.

    Priority:
    - global XDG-installed profile (if present) when `prefer_global=True`
    - packaged default profile shipped with meminit
    """

    if prefer_global:
        root = global_profile_dir(profile_name, env=env)
        if (root / "profile.json").exists():
            return load_global_profile(profile_name=profile_name, env=env)
    return load_packaged_profile(profile_name=profile_name)


def diff_profile_to_repo(profile: OrgProfile, repo_root: Path, mapping: Mapping[str, str]) -> Tuple[int, int, int]:
    """
    Compute a simple diff summary: (would_create, would_update, unchanged).
    """
    create = update = same = 0
    for profile_rel, repo_rel in mapping.items():
        target = repo_root / repo_rel
        content = profile.files.get(profile_rel, b"")
        if not target.exists():
            create += 1
            continue
        try:
            existing = target.read_bytes()
        except OSError:
            update += 1
            continue
        if existing == content:
            same += 1
        else:
            update += 1
    return create, update, same
