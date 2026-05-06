from __future__ import annotations

import os
import resource
import shutil
import sys
import time
from pathlib import Path

import pytest

from meminit.core.use_cases.index_repository import IndexRepositoryUseCase
from tests.fixtures.streaming.generators import build_streaming_fixture, tree_sha256


FIXTURE_ROOT = Path(__file__).parent / "streaming"


def _max_rss_bytes() -> int:
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return rss if sys.platform == "darwin" else rss * 1024


def test_static_tiny_fixture_has_five_documents():
    docs = sorted((FIXTURE_ROOT / "tiny" / "docs").rglob("*.md"))

    assert len(docs) == 5
    assert (FIXTURE_ROOT / "tiny" / "docops.config.yaml").is_file()


def test_streaming_fixture_generator_is_deterministic(tmp_path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    build_streaming_fixture(first, count=50, seed=1405)
    build_streaming_fixture(second, count=50, seed=1405)

    assert tree_sha256(first) == tree_sha256(second)


def test_generated_medium_fixture_indexes_incrementally(tmp_path):
    build_streaming_fixture(tmp_path, count=50, seed=1405)

    first = IndexRepositoryUseCase(str(tmp_path)).execute()
    first_bytes = first.index_path.read_bytes()
    second = IndexRepositoryUseCase(str(tmp_path)).execute()

    assert second.rebuild["mode"] == "incremental"
    assert second.rebuild["unchanged"] == 50
    assert second.index_path.read_bytes() == first_bytes


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("MEMINIT_RUN_SLOW_SCALE"),
    reason="set MEMINIT_RUN_SLOW_SCALE=1 to run Phase 5 scale fixtures",
)
def test_generated_large_fixture_warm_incremental_target(tmp_path):
    build_streaming_fixture(tmp_path, count=1000, seed=1405)
    IndexRepositoryUseCase(str(tmp_path)).execute()

    started = time.monotonic()
    report = IndexRepositoryUseCase(str(tmp_path)).execute()

    assert report.rebuild["mode"] == "incremental"
    assert report.rebuild["unchanged"] == 1000
    assert time.monotonic() - started < 2.0


@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("MEMINIT_RUN_SLOW_SCALE"),
    reason="set MEMINIT_RUN_SLOW_SCALE=1 to run Phase 5 scale fixtures",
)
def test_generated_scale_fixture_memory_ceiling(tmp_path):
    build_streaming_fixture(tmp_path, count=5000, seed=1405)

    started = time.monotonic()
    report = IndexRepositoryUseCase(str(tmp_path)).execute(use_cache=False)
    elapsed = time.monotonic() - started

    assert report.document_count == 5000
    assert report.rebuild["mode"] == "full"
    assert elapsed < 60.0
    assert _max_rss_bytes() < 256 * 1024 * 1024


def test_static_tiny_fixture_can_be_copied_without_hash_drift(tmp_path):
    source = FIXTURE_ROOT / "tiny"
    target = tmp_path / "tiny"
    shutil.copytree(source, target)

    assert tree_sha256(source) == tree_sha256(target)
