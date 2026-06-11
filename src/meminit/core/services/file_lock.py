"""File locking service for concurrent document creation."""

import errno
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.observability import log_debug
from meminit.core.services.safe_fs import ensure_safe_write_path

# Optional POSIX file locking. Absent on Windows / unsupported platforms, in
# which case locking degrades to a best-effort no-op (see acquire_lock).
fcntl: Any
try:
    import fcntl as _fcntl_module  # type: ignore

    fcntl = _fcntl_module
except ImportError:  # pragma: no cover - Windows or unsupported platforms
    fcntl = None


class FileLockService:
    """Service for managing file locks during document creation."""

    LOCK_FILENAME = ".meminit.lock"
    LOCK_RETRY_DELAY_SECONDS = 0.01
    DEFAULT_TIMEOUT_MS = 3000

    # Class-level handle to the module-level fcntl (None when unavailable).
    fcntl = fcntl

    def __init__(self, root_dir: Path):
        """Initialize file lock service.

        Args:
            root_dir: Repository root directory for path validation
        """
        self._root_dir = root_dir

    def get_lock_timeout_ms(self) -> int:
        """Get the lock acquisition timeout in milliseconds.

        Resolution order:
        1. MEMINIT_LOCK_TIMEOUT_MS environment variable
        2. Default value of 3000ms (3 seconds)

        Returns:
            Timeout in milliseconds. Returns 3000 if env var is not a valid integer.
        """
        try:
            return int(os.environ.get("MEMINIT_LOCK_TIMEOUT_MS", str(self.DEFAULT_TIMEOUT_MS)))
        except ValueError:
            return self.DEFAULT_TIMEOUT_MS

    @contextmanager
    def acquire_lock(self, target_dir: Path):
        """Acquire exclusive lock for the target directory.

        Uses fcntl.flock with LOCK_EX | LOCK_NB and retries up to timeout.
        Lock file is .meminit.lock in the target directory.

        Args:
            target_dir: Directory to lock

        Yields:
            Lock file handle (or None if file locking unavailable)

        Raises:
            MeminitError: with LOCK_TIMEOUT if lock cannot be acquired
        """
        lock_path = target_dir / self.LOCK_FILENAME
        # Validate before any filesystem write. mkdir is itself a write, so it
        # must not run before we confirm the path stays within the repo root and
        # does not traverse an existing symlink component.
        ensure_safe_write_path(root_dir=self._root_dir, target_path=lock_path)
        target_dir.mkdir(parents=True, exist_ok=True)

        # Best-effort fallback for non-POSIX platforms: continue without file
        # locking rather than failing all document creation operations.
        if self.fcntl is None:
            log_debug(
                "file_locking_unavailable",
                {
                    "platform": sys.platform,
                    "directory": str(target_dir),
                },
            )
            yield None
            return

        timeout_ms = self.get_lock_timeout_ms()
        start_time = time.monotonic()
        lock_file = None

        try:
            while True:
                try:
                    ensure_safe_write_path(root_dir=self._root_dir, target_path=lock_path)
                    lock_file = self._open_lock_file(lock_path)
                except MeminitError:
                    if lock_file:
                        try:
                            lock_file.close()
                        except Exception:
                            pass
                    raise
                except OSError as exc:
                    if lock_file:
                        try:
                            lock_file.close()
                        except Exception:
                            pass
                    raise MeminitError(
                        code=ErrorCode.UNKNOWN_ERROR,
                        message=f"Could not open lock file '{lock_path}': {exc}",
                        details={
                            "directory": str(target_dir),
                            "lock_path": str(lock_path),
                            "errno": exc.errno,
                        },
                    ) from exc

                try:
                    self.fcntl.flock(lock_file.fileno(), self.fcntl.LOCK_EX | self.fcntl.LOCK_NB)
                except OSError as exc:
                    if lock_file:
                        try:
                            lock_file.close()
                        except Exception:
                            pass

                    if not self._is_lock_contention_error(exc):
                        raise MeminitError(
                            code=ErrorCode.UNKNOWN_ERROR,
                            message=f"Could not acquire lock for '{target_dir}': {exc}",
                            details={
                                "directory": str(target_dir),
                                "lock_path": str(lock_path),
                                "errno": exc.errno,
                            },
                        ) from exc

                    elapsed_ms = (time.monotonic() - start_time) * 1000
                    if elapsed_ms >= timeout_ms:
                        raise MeminitError(
                            code=ErrorCode.LOCK_TIMEOUT,
                            message=f"Could not acquire lock for {target_dir} within {timeout_ms}ms",
                            details={
                                "directory": str(target_dir),
                                "timeout_ms": timeout_ms,
                            },
                        )
                    time.sleep(self.LOCK_RETRY_DELAY_SECONDS)
                    continue

                # Lock acquired. Yield outside the OSError-catching scope above so
                # an OSError raised by the caller's `with` body is not misread as
                # lock contention (which would mask it or trigger a retry loop).
                break

            yield lock_file
        finally:
            self.release_lock(lock_file)

    def _open_lock_file(self, lock_path: Path):
        """Open a lock file without following symlinks when supported."""
        flags = os.O_RDWR | os.O_CREAT
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW

        try:
            fd = os.open(lock_path, flags, 0o600)
        except OSError as exc:
            if hasattr(os, "O_NOFOLLOW") and exc.errno == errno.ELOOP:
                raise MeminitError(
                    code=ErrorCode.PATH_ESCAPE,
                    message=f"Lock path '{lock_path}' is a symlink and cannot be used",
                    details={"lock_path": str(lock_path)},
                ) from exc
            raise
        try:
            return os.fdopen(fd, "a+")
        except Exception:
            # Avoid leaking the raw descriptor if wrapping it fails.
            try:
                os.close(fd)
            except OSError:
                pass
            raise

    def _is_lock_contention_error(self, exc: OSError) -> bool:
        """Check if OSError indicates lock contention."""
        contention_errnos = {errno.EAGAIN}
        if hasattr(errno, "EWOULDBLOCK"):
            contention_errnos.add(errno.EWOULDBLOCK)
        if hasattr(errno, "EACCES"):
            contention_errnos.add(errno.EACCES)
        return exc.errno in contention_errnos

    def release_lock(self, lock_file) -> None:
        """Release the lock file."""
        if lock_file:
            try:
                if self.fcntl is not None:
                    self.fcntl.flock(lock_file.fileno(), self.fcntl.LOCK_UN)
                lock_file.close()
            except Exception:
                pass
