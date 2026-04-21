from __future__ import annotations

import os
import tempfile

from pathlib import Path

from meminit.core.services.error_codes import ErrorCode, MeminitError


class UnsafePathError(ValueError):
    """Legacy exception - retained for backward compatibility.

    New code should catch MeminitError with code PATH_ESCAPE instead.
    """

    pass


class MeminitPathEscapeError(MeminitError, UnsafePathError):
    """Error for path escape that is catchable as both MeminitError and UnsafePathError.

    This ensures backward compatibility: existing code that catches UnsafePathError
    will still work, while new code can catch MeminitError with code PATH_ESCAPE.
    """

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            code=ErrorCode.PATH_ESCAPE, message=message, details=details or {}
        )


class MeminitFileTypeError(MeminitError):
    """Error raised when a path exists but is not a regular file."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(
            code=ErrorCode.NOT_A_REGULAR_FILE, message=message, details=details or {}
        )


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
        MeminitPathEscapeError: which is both MeminitError (code PATH_ESCAPE)
                                and UnsafePathError for backward compatibility.
    """
    root_dir = Path(root_dir).resolve()
    target_path = Path(target_path)

    try:
        resolved = target_path.resolve()
        resolved.relative_to(root_dir)
    except Exception as exc:
        raise MeminitPathEscapeError(
            message=f"Path '{target_path}' escapes repository root '{root_dir}'",
            details={"target_path": str(target_path), "root_dir": str(root_dir)},
        ) from exc

    try:
        rel = target_path.relative_to(root_dir)
    except Exception as exc:
        raise MeminitPathEscapeError(
            message=f"Path '{target_path}' is not under repository root '{root_dir}'",
            details={"target_path": str(target_path), "root_dir": str(root_dir)},
        ) from exc

    current = root_dir
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise MeminitPathEscapeError(
                message=f"Path '{target_path}' contains symlink component '{current}'",
                details={
                    "target_path": str(target_path),
                    "symlink_component": str(current),
                    "root_dir": str(root_dir),
                },
            )


def ensure_existing_regular_file_path(*, root_dir: Path, target_path: Path) -> None:
    """Ensure an existing target path is a regular file within the repo root.

    This reuses the write-path safety checks to reject symlink escapes and then
    adds a regular-file check so read-only commands do not follow symlinks or
    operate on directories, devices, or other non-regular targets.
    """
    ensure_safe_write_path(root_dir=root_dir, target_path=target_path)

    target_path = Path(target_path)
    if not target_path.is_file():
        raise MeminitFileTypeError(
            message=f"Path '{target_path}' is not a regular file",
            details={
                "target_path": str(target_path),
                "root_dir": str(Path(root_dir).resolve()),
                "required": "regular file (not directory/symlink)",
            },
        )


def atomic_write(
    target_path: Path,
    content: str | bytes,
    *,
    encoding: str = "utf-8",
    file_mode: int | None = None,
) -> None:
    """Write content to target path atomically using temp-file + os.replace.

    Creates a temporary file in the same directory as the target, writes
    the content, then atomically replaces the target.  Ensures no partial
    writes are visible to concurrent readers.

    If *file_mode* is given, it is applied to the temp file before the
    atomic rename so that chmod failures abort the write entirely.

    The caller is responsible for validating the target path with
    ``ensure_safe_write_path`` before calling this function.
    """
    if isinstance(content, str):
        data = content.encode(encoding)
    else:
        data = content

    effective_mode = file_mode
    if effective_mode is None:
        try:
            effective_mode = target_path.stat().st_mode & 0o777
        except OSError:
            effective_mode = 0o666

    fd, tmp_path = tempfile.mkstemp(
        dir=str(target_path.parent),
        prefix=f".{target_path.name}.tmp.",
        suffix=".tmp",
    )
    try:
        try:
            os.fchmod(fd, effective_mode)
        except AttributeError:
            os.chmod(tmp_path, effective_mode)
        view = memoryview(data)
        written = 0
        while written < len(view):
            count = os.write(fd, view[written:])
            if count <= 0:
                raise OSError("short write while writing atomic temp file")
            written += count
        os.close(fd)
        fd = None
        os.replace(tmp_path, str(target_path))
    except BaseException:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
