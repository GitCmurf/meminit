"""File locking service for concurrent document creation."""

import errno
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.observability import log_debug
from meminit.core.services.safe_fs import ensure_safe_write_path


class FileLockService:
    """Service for managing file locks during document creation."""

    LOCK_FILENAME = ".meminit.lock"
    LOCK_RETRY_DELAY_SECONDS = 0.01
    DEFAULT_TIMEOUT_MS = 3000

    fcntl: Optional[Any] = None
    try:
        import fcntl as fcntl_module
        fcntl = fcntl_module
    except ImportError:
        pass  # Windows or unsupported platforms

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
        target_dir.mkdir(parents=True, exist_ok=True)
        ensure_safe_write_path(root_dir=self._root_dir, target_path=lock_path)

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
                    yield lock_file
                    return
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
        return os.fdopen(fd, "a+")

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