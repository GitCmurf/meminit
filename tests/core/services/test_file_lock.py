"""Tests for FileLockService security and correctness behaviors."""
import os
import sys
from pathlib import Path

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.file_lock import FileLockService

pytestmark = pytest.mark.skipif(
    not hasattr(os, "O_NOFOLLOW") or sys.platform.startswith("win"),
    reason="POSIX file locking / symlink semantics required",
)


def test_acquire_lock_rejects_symlink_escape_before_mkdir(tmp_path: Path):
    """A target_dir that traverses an existing symlink must be rejected before
    any directory is created outside the repo root."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()

    # docs/45-adr is a symlink pointing outside the repo root.
    link = repo / "docs" / "45-adr"
    link.symlink_to(outside)

    service = FileLockService(repo)
    with pytest.raises(MeminitError) as excinfo:
        with service.acquire_lock(link / "nested"):
            pass

    assert excinfo.value.code == ErrorCode.PATH_ESCAPE
    # Nothing should have been created under the escape target.
    assert not (outside / "nested").exists()


def test_acquire_lock_creates_lock_and_releases(tmp_path: Path):
    """Happy path: lock is acquired, yielded, and the lock file is created."""
    repo = tmp_path / "repo"
    target = repo / "docs" / "45-adr"

    service = FileLockService(repo)
    with service.acquire_lock(target) as handle:
        assert handle is not None
        assert (target / FileLockService.LOCK_FILENAME).exists()


def test_caller_oserror_propagates_unwrapped(tmp_path: Path):
    """An OSError raised inside the `with` body must propagate as-is, not be
    misread as lock contention (wrapped in MeminitError or retried)."""
    repo = tmp_path / "repo"
    target = repo / "docs" / "45-adr"

    service = FileLockService(repo)
    sentinel = OSError("disk full from caller")
    with pytest.raises(OSError) as excinfo:
        with service.acquire_lock(target):
            raise sentinel
    assert excinfo.value is sentinel


def test_open_lock_file_closes_fd_on_fdopen_failure(tmp_path: Path, monkeypatch):
    """If os.fdopen fails after os.open succeeds, the raw fd must be closed
    rather than leaked."""
    repo = tmp_path / "repo"
    target = repo / "docs" / "45-adr"
    target.mkdir(parents=True)

    service = FileLockService(repo)
    closed = []
    real_close = os.close

    def fake_fdopen(fd, *args, **kwargs):
        raise OSError("fdopen boom")

    def tracking_close(fd):
        closed.append(fd)
        return real_close(fd)

    monkeypatch.setattr(os, "fdopen", fake_fdopen)
    monkeypatch.setattr(os, "close", tracking_close)

    with pytest.raises(OSError):
        service._open_lock_file(target / FileLockService.LOCK_FILENAME)

    assert closed, "expected the raw file descriptor to be closed on fdopen failure"
