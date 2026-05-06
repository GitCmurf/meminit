from __future__ import annotations

import json
from importlib import resources
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from tests.cli.streaming_helpers import create_initialized_repo


@pytest.fixture(scope="session")
def stream_schema_validator() -> Draft7Validator:
    schema = json.loads(
        resources.files("meminit.core.assets")
        .joinpath("agent-output.stream.schema.v1.json")
        .read_text(encoding="utf-8")
    )
    return Draft7Validator(schema)


@pytest.fixture
def initialized_repo(tmp_path: Path) -> Path:
    create_initialized_repo(tmp_path)
    return tmp_path
