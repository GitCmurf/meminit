from __future__ import annotations

import queue
import threading

from meminit.core.services.stream_events import StreamItem
from meminit.core.use_cases.context_repository import ContextRepositoryUseCase, ContextResult
from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase
from meminit.core.use_cases import index_repository
from meminit.core.use_cases.index_repository import IndexRepositoryUseCase
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

    def build_report_after_first_yield(*args, **kwargs):
        sentinel.record("build_report")
        raise AssertionError("scan stream materialized the full report before first item")

    monkeypatch.setattr(use_case, "_build_report", build_report_after_first_yield)

    first = next(use_case.iter_stream().records)
    sentinel.record("yield")

    assert isinstance(first, StreamItem)
    assert first.kind == "file"
    assert sentinel.first_yield_after == ["yield"]


def test_scan_stream_forwards_generate_plan_to_build_report(tmp_path, monkeypatch):
    create_initialized_repo(tmp_path)
    use_case = ScanRepositoryUseCase(str(tmp_path))
    captured: dict[str, bool] = {}

    class DummyReport:
        def as_dict(self):
            return {
                "docs_root": "docs",
                "suggested_type_directories": {},
                "markdown_count": 1,
                "governed_markdown_count": 1,
                "notes": [],
                "ambiguous_types": {},
                "suggested_namespaces": [],
                "configured_namespaces": [],
                "overlapping_namespaces": [],
                "plan": {"plan_version": "1.0", "actions": []},
            }

    def build_report_with_plan(*args, **kwargs):
        captured["generate_plan"] = kwargs["generate_plan"]
        return DummyReport(), []

    monkeypatch.setattr(use_case, "_build_report", build_report_with_plan)

    result = use_case.iter_stream(generate_plan=True)
    assert next(result.records).kind == "file"
    assert captured == {}
    list(result.records)

    assert captured["generate_plan"] is True
    assert result.summary.data["plan"] == {"plan_version": "1.0", "actions": []}


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


def test_context_stream_shallow_does_not_emit_documents(tmp_path, monkeypatch):
    create_initialized_repo(tmp_path)
    use_case = ContextRepositoryUseCase(str(tmp_path))
    captured: dict[str, bool] = {}

    def execute_shallow(*args, **kwargs):
        captured["deep"] = kwargs["deep"]
        return ContextResult(
            data={
                "allowed_types": ["ADR"],
                "config_path": "docops.config.yaml",
                "default_owner": None,
                "document_types": {"ADR": {"directory": "45-adr"}},
                "index_path": "docs/.meminit/index.json",
                "namespaces": [{"name": "default"}],
                "project_name": "Example",
                "repo_prefix": "EXAMPLE",
                "schema_path": "docs/schema.json",
            },
            warnings=[],
            documents=[
                {
                    "document_id": "TEST-ADR-001",
                    "namespace": "default",
                    "path": "docs/45-adr/adr-001-test.md",
                    "title": "Test ADR",
                    "type": "ADR",
                }
            ],
        )

    monkeypatch.setattr(use_case, "execute", execute_shallow)

    result = use_case.iter_stream(deep=False)
    records = list(result.records)

    assert captured["deep"] is False
    assert records[0].kind == "document_type"
    assert all(record.kind != "document" for record in records)
    assert "documents" not in result.summary.data


def test_index_stream_emits_first_node_while_build_is_still_running(
    tmp_path, monkeypatch
):
    create_initialized_repo(tmp_path)
    use_case = IndexRepositoryUseCase(str(tmp_path))
    stream_started = threading.Event()
    release_build = threading.Event()
    first_record_queue: queue.Queue[object] = queue.Queue()
    sentinel = object()

    def build_with_stream(*args, **kwargs):
        emitter = kwargs["stream_item_emitter"]
        assert emitter is not None
        emitter(
            StreamItem(
                "node",
                {
                    "document_id": "EXAMPLE-ADR-001",
                    "path": "docs/45-adr/adr-001-test.md",
                },
            )
        )
        stream_started.set()
        assert release_build.wait(timeout=5), "test did not release build in time"
        return index_repository._IndexBuildArtifacts(
            index_path=tmp_path / "docs" / "01-indices" / "meminit.index.json",
            document_count=1,
            documents=[
                {
                    "document_id": "EXAMPLE-ADR-001",
                    "path": "docs/45-adr/adr-001-test.md",
                }
            ],
            edges=[],
            warnings=[],
            advice=[],
            rebuild={"mode": "full"},
        )

    monkeypatch.setattr(use_case, "_build_index_artifacts", build_with_stream)

    result = use_case.iter_stream(use_cache=False)
    iterator = result.records

    def consume_first_record() -> None:
        try:
            first_record_queue.put(next(iterator))
            release_build.wait(timeout=5)
            for record in iterator:
                first_record_queue.put(record)
        except BaseException as exc:  # pragma: no cover - surfaced in test thread
            first_record_queue.put(exc)
        finally:
            first_record_queue.put(sentinel)

    consumer = threading.Thread(target=consume_first_record, daemon=True)
    consumer.start()

    first = first_record_queue.get(timeout=1)
    assert isinstance(first, StreamItem)
    assert first.kind == "node"
    assert stream_started.wait(timeout=1)

    release_build.set()

    remaining: list[object] = []
    while True:
        item = first_record_queue.get(timeout=1)
        if item is sentinel:
            break
        remaining.append(item)

    consumer.join(timeout=1)

    assert not any(isinstance(item, BaseException) for item in remaining)
    assert result.summary.data["node_count"] == 1


def test_index_stream_emits_cached_nodes_on_no_change_reuse(tmp_path):
    create_initialized_repo(tmp_path)
    use_case = IndexRepositoryUseCase(str(tmp_path))

    use_case.execute()
    result = use_case.iter_stream()
    records = list(result.records)
    node_kinds = [record.kind for record in records if isinstance(record, StreamItem)]

    assert node_kinds[:2] == ["node", "node"]
    assert result.summary.data["node_count"] == 2
    assert result.summary.data["rebuild"]["mode"] == "incremental"
