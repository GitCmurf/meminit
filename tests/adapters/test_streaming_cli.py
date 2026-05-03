import json
from importlib import resources
from datetime import datetime, timezone
from pathlib import Path

from click.testing import CliRunner
from jsonschema import Draft7Validator

from meminit.cli.main import cli
from meminit.core.services.error_codes import ErrorCode


def _records(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.strip()]


def _init_repo(tmp_path):
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0, result.output
    doc_dir = tmp_path / "docs" / "45-adr"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "adr-001-test.md").write_text(
        "---\n"
        "document_id: TEST-ADR-001\n"
        "type: ADR\n"
        "title: Test ADR\n"
        "status: Draft\n"
        "version: '0.1'\n"
        "last_updated: '2026-05-03'\n"
        "owner: Test Team\n"
        "docops_version: '2.0'\n"
        "area: TEST\n"
        "description: Test document.\n"
        "keywords: [test]\n"
        "related_ids: []\n"
        "---\n\n# ADR: Test\n",
        encoding="utf-8",
    )


def _validator() -> Draft7Validator:
    schema = json.loads(
        resources.files("meminit.core.assets")
        .joinpath("agent-output.stream.schema.v1.json")
        .read_text(encoding="utf-8")
    )
    return Draft7Validator(schema)


def test_stream_schema_copies_are_identical():
    packaged = (
        resources.files("meminit.core.assets")
        .joinpath("agent-output.stream.schema.v1.json")
        .read_text(encoding="utf-8")
    )
    docs = Path("docs/20-specs/agent-output.stream.schema.v1.json").read_text(
        encoding="utf-8"
    )
    assert docs == packaged


def test_index_ndjson_outputs_header_items_and_summary(tmp_path):
    _init_repo(tmp_path)
    result = CliRunner().invoke(
        cli, ["index", "--root", str(tmp_path), "--format", "ndjson"]
    )
    assert result.exit_code == 0, result.output
    records = _records(result.output)
    assert [r["sequence"] for r in records] == list(range(len(records)))
    assert records[0]["record_type"] == "header"
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["data"]["rebuild"]["mode"] == "full"
    assert {r.get("kind") for r in records if r["record_type"] == "item"} >= {"node"}
    for record in records:
        assert not list(_validator().iter_errors(record))


def test_ndjson_header_uses_real_timestamp(tmp_path):
    _init_repo(tmp_path)
    result = CliRunner().invoke(
        cli,
        [
            "context",
            "--root",
            str(tmp_path),
            "--deep",
            "--format",
            "ndjson",
            "--include-timestamp",
        ],
    )
    assert result.exit_code == 0, result.output
    header = _records(result.output)[0]
    assert header["record_type"] == "header"
    started_at = datetime.fromisoformat(header["started_at"].replace("Z", "+00:00"))
    delta_seconds = abs((datetime.now(timezone.utc) - started_at).total_seconds())
    assert delta_seconds < 60


def test_index_ndjson_graph_fatal_emits_terminal_error(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "docs" / "45-adr" / "adr-dup.md").write_text(
        "---\n"
        "document_id: TEST-ADR-001\n"
        "type: ADR\n"
        "title: Duplicate ADR\n"
        "status: Draft\n"
        "version: '0.1'\n"
        "last_updated: '2026-05-03'\n"
        "owner: Test Team\n"
        "docops_version: '2.0'\n"
        "area: TEST\n"
        "description: Duplicate document.\n"
        "keywords: [test]\n"
        "related_ids: []\n"
        "---\n\n# ADR: Duplicate\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli, ["index", "--root", str(tmp_path), "--format", "ndjson"]
    )
    assert result.exit_code != 0
    records = _records(result.output)
    assert records[0]["record_type"] == "header"
    assert records[-1]["record_type"] == "error"
    assert records[-1]["error"]["code"] == ErrorCode.GRAPH_DUPLICATE_DOCUMENT_ID.value


def test_context_ndjson_requires_deep(tmp_path):
    _init_repo(tmp_path)
    result = CliRunner().invoke(
        cli, ["context", "--root", str(tmp_path), "--format", "ndjson"]
    )
    assert result.exit_code == 64
    records = _records(result.output)
    assert records[-1]["record_type"] == "error"
    assert records[-1]["error"]["code"] == ErrorCode.STREAM_UNSUPPORTED_FORMAT.value


def test_context_ndjson_requires_deep_respects_output_path(tmp_path):
    _init_repo(tmp_path)
    output = tmp_path / "context.ndjson"
    result = CliRunner().invoke(
        cli,
        [
            "context",
            "--root",
            str(tmp_path),
            "--format",
            "ndjson",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 64
    records = _records(output.read_text(encoding="utf-8"))
    assert records[0]["record_type"] == "header"
    assert records[-1]["record_type"] == "error"
    assert records[-1]["error"]["code"] == ErrorCode.STREAM_UNSUPPORTED_FORMAT.value


def test_check_ndjson_emits_structured_unsupported_error(tmp_path):
    result = CliRunner().invoke(
        cli, ["check", "--root", str(tmp_path), "--format", "ndjson"]
    )
    assert result.exit_code == 64
    records = _records(result.output)
    assert records[0]["record_type"] == "header"
    assert records[-1]["record_type"] == "error"
    assert records[-1]["error"]["code"] == ErrorCode.STREAM_UNSUPPORTED_FORMAT.value


def test_context_deep_ndjson_includes_documents(tmp_path):
    _init_repo(tmp_path)
    result = CliRunner().invoke(
        cli, ["context", "--root", str(tmp_path), "--deep", "--format", "ndjson"]
    )
    assert result.exit_code == 0, result.output
    records = _records(result.output)
    documents = [
        r["data"]
        for r in records
        if r["record_type"] == "item" and r.get("kind") == "document"
    ]
    assert {
        "document_id": "TEST-ADR-001",
        "namespace": "default",
        "path": "docs/45-adr/adr-001-test.md",
        "title": "Test ADR",
        "type": "ADR",
    } in documents
    assert records[-1]["data"]["document_count"] == len(documents)


def test_index_ndjson_allows_external_output_path(tmp_path):
    root = tmp_path / "repo"
    _init_repo(root)
    output = tmp_path / "index.ndjson"
    result = CliRunner().invoke(
        cli,
        [
            "index",
            "--root",
            str(root),
            "--format",
            "ndjson",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    assert output.exists()
    records = _records(output.read_text(encoding="utf-8"))
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["success"] is True


def test_index_ndjson_emits_failed_summary_for_error_severity_state(tmp_path):
    root = tmp_path / "repo"
    _init_repo(root)
    state_dir = root / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "documents:\n"
        "  UNKNOWN-001:\n"
        "    impl_state: Done\n"
        "    updated: 2025-12-21T10:00:00Z\n"
        "    : invalid\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        cli, ["index", "--root", str(root), "--format", "ndjson"]
    )
    assert result.exit_code == 1, result.output
    records = _records(result.output)
    assert records[-1]["record_type"] == "summary"
    assert records[-1]["success"] is False
    assert any(
        warning.get("code") == "E_STATE_YAML_MALFORMED"
        for warning in records[-1]["warnings"]
    )


def test_capabilities_advertises_streaming(tmp_path):
    result = CliRunner().invoke(cli, ["capabilities", "--format", "json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["data"]["features"]["streaming"] is True
    commands = {c["name"]: c for c in payload["data"]["commands"]}
    assert commands["index"]["supports_ndjson"] is True
    assert commands["scan"]["supports_ndjson"] is True
    assert commands["context"]["supports_ndjson"] is True
