from __future__ import annotations

from meminit.core.services.stream_events import StreamItem
from meminit.core.use_cases import index_repository
from meminit.core.use_cases.context_repository import ContextRepositoryUseCase
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase
from tests.cli.streaming_helpers import create_initialized_repo


class FirstYieldSentinel:
    def __init__(self) -> None:
        self.first_yield_after: list[str] = []

    def record(self, marker: str) -> None:
        self.first_yield_after.append(marker)


def test_scan_stream_yields_file_before_full_report_materialization(tmp_path, monkeypatch):
    create_initialized_repo(tmp_path)
    use_case = ScanRepositoryUseCase(str(tmp_path))
    sentinel = FirstYieldSentinel()

    def execute_after_first_yield(*args, **kwargs):
        sentinel.record("execute")
        raise AssertionError("scan stream materialized the full report before first item")

    monkeypatch.setattr(use_case, "execute", execute_after_first_yield)

    first = next(use_case.iter_stream().records)
    sentinel.record("yield")

    assert isinstance(first, StreamItem)
    assert first.kind == "file"
    assert sentinel.first_yield_after == ["yield"]


def test_context_stream_yields_document_type_before_deep_report_materialization(
    tmp_path, monkeypatch
):
    create_initialized_repo(tmp_path)
    use_case = ContextRepositoryUseCase(str(tmp_path))
    sentinel = FirstYieldSentinel()

    def execute_after_first_yield(*args, **kwargs):
        sentinel.record("execute")
        raise AssertionError("context stream materialized deep context before first item")

    monkeypatch.setattr(use_case, "execute", execute_after_first_yield)

    first = next(use_case.iter_stream().records)
    sentinel.record("yield")

    assert isinstance(first, StreamItem)
    assert first.kind == "document_type"
    assert sentinel.first_yield_after == ["yield"]


def test_index_stream_yields_node_before_public_report_materialization(
    tmp_path, monkeypatch
):
    create_initialized_repo(tmp_path)
    use_case = IndexRepositoryUseCase(str(tmp_path))
    sentinel = FirstYieldSentinel()

    def report_after_first_yield(*args, **kwargs):
        sentinel.record("report")
        raise AssertionError("index stream assembled IndexBuildReport before first item")

    monkeypatch.setattr(index_repository, "IndexBuildReport", report_after_first_yield)

    first = next(use_case.iter_stream(use_cache=False).records)
    sentinel.record("yield")

    assert isinstance(first, StreamItem)
    assert first.kind == "node"
    assert sentinel.first_yield_after == ["yield"]
