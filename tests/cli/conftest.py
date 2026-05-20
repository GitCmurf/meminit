from __future__ import annotations

from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from tests.cli.streaming_helpers import (
    create_initialized_repo,
    stream_schema_validator as build_stream_schema_validator,
)


@pytest.fixture(scope="session")
def stream_schema_validator() -> Draft7Validator:
    return build_stream_schema_validator()


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    create_initialized_repo(tmp_path)
    return tmp_path
