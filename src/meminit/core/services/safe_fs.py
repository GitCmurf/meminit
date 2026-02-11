from __future__ import annotations

from pathlib import Path


class UnsafePathError(ValueError):
    pass


def ensure_safe_write_path(*, root_dir: Path, target_path: Path) -> None:
    """
    Ensure a target path is safe to write within a repository root.

    Security goals:
    - Refuse writes that would resolve outside the repo root (e.g., via symlinks).
    - Refuse writes that traverse any existing symlink path component, even if it
      ultimately resolves within the repo root.

    This is a best-effort guard against "symlink escape" attacks when running
    meminit on untrusted repositories.
    """
    root_dir = Path(root_dir).resolve()
    target_path = Path(target_path)

    try:
        resolved = target_path.resolve()
        resolved.relative_to(root_dir)
    except Exception as exc:
        raise UnsafePathError(
            f"Refusing to write '{target_path}': resolves outside repository root '{root_dir}'."
        ) from exc

    try:
        rel = target_path.relative_to(root_dir)
    except Exception:
        # If target_path is not under root_dir syntactically, it is unsafe even if resolution passed.
        raise UnsafePathError(
            f"Refusing to write '{target_path}': path is not under repository root '{root_dir}'."
        )

    current = root_dir
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise UnsafePathError(
                f"Refusing to write '{target_path}': path component '{current}' is a symlink."
            )

