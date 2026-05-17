from __future__ import annotations

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

    def execute_after_first_yield(*args, **kwargs):
        sentinel.record("execute")
        raise AssertionError("scan stream materialized the full report before first item")

    monkeypatch.setattr(use_case, "execute", execute_after_first_yield)

    first = next(use_case.iter_stream().records)
    sentinel.record("yield")

    assert isinstance(first, StreamItem)
    assert first.kind == "file"
    assert sentinel.first_yield_after == ["yield"]


def test_scan_stream_forwards_generate_plan_to_execute(tmp_path, monkeypatch):
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

    def execute_with_plan(*args, **kwargs):
        captured["generate_plan"] = kwargs["generate_plan"]
        return DummyReport()

    monkeypatch.setattr(use_case, "execute", execute_with_plan)

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
