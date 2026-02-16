import pytest

from meminit.core.services.safe_fs import ensure_safe_write_path, UnsafePathError
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
