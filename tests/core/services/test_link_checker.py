import pytest

from meminit.core.domain.entities import Violation
from meminit.core.services.validators import LinkChecker


def test_link_missing_target():
    checker = LinkChecker(root_dir="/app")
    body = "See [This Link](missing.md) for info."
    # Mocking file existence check
    checker._file_exists = lambda p: False

    violation = checker.validate_links("docs/source.md", body)
    assert isinstance(violation, list)
    assert len(violation) == 1
    assert violation[0].rule == "LINK_BROKEN"
    assert "missing.md" in violation[0].message


def test_link_exists():
    checker = LinkChecker(root_dir="/app")
    body = "See [This Link](exists.md) for info."
    checker._file_exists = lambda p: True

    violation = checker.validate_links("docs/source.md", body)
    assert len(violation) == 0


def test_link_exists_with_fragment():
    checker = LinkChecker(root_dir="/app")
    body = "See [This Link](exists.md#section) for info."
    checker._file_exists = lambda p: str(p).endswith("/docs/exists.md")

    violation = checker.validate_links("docs/source.md", body)
    assert len(violation) == 0


def test_external_link_ignored():
    checker = LinkChecker(root_dir="/app")
    body = "See [Google](https://google.com)."
    violation = checker.validate_links("docs/source.md", body)
    assert len(violation) == 0


def test_link_escape_outside_root_is_rejected_even_if_target_exists():
    checker = LinkChecker(root_dir="/app")
    body = "See [Secret](../../secret.md) for info."
    checker._file_exists = lambda p: str(p).endswith("secret.md")

    violations = checker.validate_links("docs/source.md", body)
    assert len(violations) == 1
    assert violations[0].rule == "LINK_BROKEN"
    assert "outside root" in violations[0].message.lower()
