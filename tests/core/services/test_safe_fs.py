import os

import pytest

from pathlib import Path

from meminit.core.services.safe_fs import (
    ensure_safe_write_path,
    ensure_existing_regular_file_path,
    UnsafePathError,
    MeminitFileTypeError,
    MeminitPathEscapeError,
)
from meminit.core.services.error_codes import MeminitError, ErrorCode


def test_path_escape_catchable_as_unsafe_path_error(tmp_path):
    """Backward compatibility: PATH_ESCAPE must be catchable as UnsafePathError."""
    with pytest.raises(UnsafePathError):
        ensure_safe_write_path(
            root_dir=tmp_path, target_path=tmp_path / ".." / "etc" / "passwd"
        )


def test_path_escape_is_also_meminit_error(tmp_path):
    """PATH_ESCAPE should also be catchable as MeminitError."""
    with pytest.raises(MeminitError) as exc_info:
        ensure_safe_write_path(
            root_dir=tmp_path, target_path=tmp_path / ".." / "etc" / "passwd"
        )

    assert exc_info.value.code == ErrorCode.PATH_ESCAPE


def test_atomic_write_retries_short_writes(tmp_path, monkeypatch):
    from meminit.core.services.safe_fs import atomic_write

    target = tmp_path / "artifact.txt"
    writes = []
    real_write = os.write

    def short_write(fd, data):
        writes.append(len(data))
        if len(writes) == 1:
            return real_write(fd, data[:3])
        return real_write(fd, data)

    monkeypatch.setattr(os, "write", short_write)

    atomic_write(target, "abcdef")

    assert target.read_text(encoding="utf-8") == "abcdef"
    assert len(writes) >= 2


def test_atomic_write_preserves_existing_mode(tmp_path):
    from meminit.core.services.safe_fs import atomic_write

    target = tmp_path / "artifact.txt"
    target.write_text("old", encoding="utf-8")
    target.chmod(0o640)

    atomic_write(target, "new")

    assert target.read_text(encoding="utf-8") == "new"
    assert target.stat().st_mode & 0o777 == 0o640


def test_atomic_write_uses_umask_for_new_files(tmp_path):
    from meminit.core.services.safe_fs import atomic_write

    target = tmp_path / "artifact.txt"
    original_umask = os.umask(0o027)
    try:
        atomic_write(target, "new")
    finally:
        os.umask(original_umask)

    assert target.read_text(encoding="utf-8") == "new"
    assert target.stat().st_mode & 0o777 == 0o640


def test_ensure_existing_regular_file_rejects_directory(tmp_path):
    (tmp_path / "subdir").mkdir()
    with pytest.raises(MeminitFileTypeError) as exc_info:
        ensure_existing_regular_file_path(
            root_dir=tmp_path, target_path=tmp_path / "subdir"
        )
    assert exc_info.value.code == ErrorCode.NOT_A_REGULAR_FILE
    assert isinstance(exc_info.value, MeminitError)
    assert not isinstance(exc_info.value, MeminitPathEscapeError)


def test_ensure_existing_regular_file_rejects_missing(tmp_path):
    with pytest.raises(MeminitFileTypeError) as exc_info:
        ensure_existing_regular_file_path(
            root_dir=tmp_path, target_path=tmp_path / "nonexistent"
        )
    assert exc_info.value.code == ErrorCode.NOT_A_REGULAR_FILE


def test_ensure_existing_regular_file_accepts_regular_file(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("hello", encoding="utf-8")
    ensure_existing_regular_file_path(root_dir=tmp_path, target_path=target)


def test_ensure_existing_regular_file_symlink_escape_is_path_escape(tmp_path):
    outside = tmp_path.parent / "outside-file.txt"
    outside.write_text("outside", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(outside)
    with pytest.raises(MeminitPathEscapeError) as exc_info:
        ensure_existing_regular_file_path(root_dir=tmp_path, target_path=link)
    assert exc_info.value.code == ErrorCode.PATH_ESCAPE
