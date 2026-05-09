from __future__ import annotations

import json

from click.testing import CliRunner

from meminit.cli.main import cli
from meminit.core.use_cases.scan_repository import scan_suggestion_items
from tests.cli.streaming_helpers import records


def _items_by_kind(stream_records, kind: str) -> list[dict]:
    return [
        record["data"]
        for record in stream_records
        if record["record_type"] == "item" and record.get("kind") == kind
    ]


def test_index_json_and_ndjson_are_equivalent(initialized_repo):
    runner = CliRunner()
    json_result = runner.invoke(
        cli, ["index", "--root", str(initialized_repo), "--format", "json"]
    )
    stream_result = runner.invoke(
        cli, ["index", "--root", str(initialized_repo), "--format", "ndjson"]
    )

    assert json_result.exit_code == 0, json_result.output
    assert stream_result.exit_code == 0, stream_result.output
    envelope = json.loads(json_result.output)
    stream = records(stream_result.output)
    summary = stream[-1]["data"]
    assert _items_by_kind(stream, "node") == sorted(
        envelope["data"]["nodes"], key=lambda row: row["document_id"]
    )
    assert _items_by_kind(stream, "edge") == sorted(
        envelope["data"]["edges"],
        key=lambda row: (
            row.get("source", ""),
            row.get("target", ""),
            row.get("type", row.get("edge_type", "")),
        ),
    )
    assert summary["node_count"] == envelope["data"]["node_count"]
    assert summary["edge_count"] == envelope["data"]["edge_count"]


def test_scan_json_and_ndjson_summaries_are_equivalent(initialized_repo):
    runner = CliRunner()
    json_result = runner.invoke(
        cli, ["scan", "--root", str(initialized_repo), "--format", "json"]
    )
    stream_result = runner.invoke(
        cli, ["scan", "--root", str(initialized_repo), "--format", "ndjson"]
    )

    assert json_result.exit_code == 0, json_result.output
    assert stream_result.exit_code == 0, stream_result.output
    report = json.loads(json_result.output)["data"]["report"]
    summary = records(stream_result.output)[-1]["data"]
    assert summary == report


def test_scan_suggestions_sort_by_severity_code_and_path():
    suggestions = scan_suggestion_items(
        {
            "docs_root": "docs",
            "suggested_type_directories": {"ADR": "adrs"},
            "ambiguous_types": {"SPEC": ["specs", "specifications"]},
            "suggested_namespaces": [{"name": "packages"}],
        }
    )

    assert [(row["severity"], row["code"], row["path"]) for row in suggestions] == [
        ("info", "suggested_namespaces", "docops.config.yaml"),
        ("info", "suggested_type_directories", "docs"),
        ("warning", "ambiguous_types", "docs"),
    ]


def test_context_json_and_ndjson_are_equivalent(initialized_repo):
    runner = CliRunner()
    json_result = runner.invoke(
        cli, ["context", "--root", str(initialized_repo), "--deep", "--format", "json"]
    )
    stream_result = runner.invoke(
        cli, ["context", "--root", str(initialized_repo), "--deep", "--format", "ndjson"]
    )

    assert json_result.exit_code == 0, json_result.output
    assert stream_result.exit_code == 0, stream_result.output
    envelope = json.loads(json_result.output)
    stream = records(stream_result.output)
    summary = stream[-1]["data"]
    assert _items_by_kind(stream, "namespace") == sorted(
        envelope["data"]["namespaces"], key=lambda row: row["name"]
    )
    expected_doc_types = []
    for doc_type, payload in envelope["data"]["document_types"].items():
        row = {"type": doc_type}
        if isinstance(payload, dict):
            row.update(payload)
        row["type"] = doc_type
        expected_doc_types.append(row)
    assert _items_by_kind(stream, "document_type") == sorted(
        expected_doc_types, key=lambda row: row["type"]
    )
    assert _items_by_kind(stream, "document") == sorted(
        envelope["data"]["documents"],
        key=lambda row: (row["document_id"], row["path"]),
    )
    assert summary == {
        key: value
        for key, value in envelope["data"].items()
        if key not in {"namespaces", "documents"}
    }
