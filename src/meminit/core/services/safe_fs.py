from __future__ import annotations

from pathlib import Path

from meminit.core.services.error_codes import ErrorCode, MeminitError


class UnsafePathError(ValueError):
    """Legacy exception - retained for backward compatibility.

    New code should catch MeminitError with code PATH_ESCAPE instead.
    """

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

    Raises:
        MeminitError: with code PATH_ESCAPE if the path is unsafe.
    """
    root_dir = Path(root_dir).resolve()
    target_path = Path(target_path)

    try:
        resolved = target_path.resolve()
        resolved.relative_to(root_dir)
    except Exception as exc:
        raise MeminitError(
            code=ErrorCode.PATH_ESCAPE,
            message=f"Path '{target_path}' escapes repository root '{root_dir}'",
            details={"target_path": str(target_path), "root_dir": str(root_dir)},
        ) from exc

    try:
        rel = target_path.relative_to(root_dir)
    except Exception:
        raise MeminitError(
            code=ErrorCode.PATH_ESCAPE,
            message=f"Path '{target_path}' is not under repository root '{root_dir}'",
            details={"target_path": str(target_path), "root_dir": str(root_dir)},
        )

    current = root_dir
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise MeminitError(
                code=ErrorCode.PATH_ESCAPE,
                message=f"Path '{target_path}' contains symlink component '{current}'",
                details={
                    "target_path": str(target_path),
                    "symlink_component": str(current),
                    "root_dir": str(root_dir),
                },
            )
