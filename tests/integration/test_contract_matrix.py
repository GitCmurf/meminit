"""Contract-matrix tests: validate envelope contract for every JSON-supporting command.

Tests derive the command list from the capabilities output, making them
self-maintaining. Adding a new JSON-supporting command automatically includes
it in the parametrization.
"""
import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from jsonschema import Draft7Validator

from meminit.cli.main import cli
from meminit.core.use_cases.capabilities import CapabilitiesUseCase
from tests.helpers import parse_first_json_line, stdout_text


@pytest.fixture(scope="module")
def agent_output_schema():
    """Load the agent-output schema for validation.

    Uses the bundled asset (what the CLI actually loads) and asserts
    the docs copy is identical to catch drift.
    """
    bundled_path = (
        Path(__file__).resolve().parents[2]
        / "src"
        / "meminit"
        / "core"
        / "assets"
        / "agent-output.schema.v3.json"
    )
    docs_path = (
        Path(__file__).resolve().parents[2]
        / "docs"
        / "20-specs"
        / "agent-output.schema.v3.json"
    )
    bundled_text = bundled_path.read_text(encoding="utf-8")
    assert bundled_text == docs_path.read_text(
        encoding="utf-8"
    ), "Bundled and docs schema copies have drifted"
    return json.loads(bundled_text)


def _get_json_commands() -> list[dict]:
    """Derive list of JSON-capable commands from capabilities."""
    caps = CapabilitiesUseCase().execute()
    return [c for c in caps["commands"] if c["supports_json"]]


_REQUIRED_FIELDS = {
    "output_schema_version",
    "success",
    "command",
    "run_id",
    "data",
    "warnings",
    "violations",
    "advice",
}


def _repo_agnostic_commands() -> set[str]:
    """Derive repo-agnostic command names from the capabilities registry."""
    caps = CapabilitiesUseCase().execute()
    return {c["name"] for c in caps["commands"] if not c.get("needs_root")}


def _setup_initialized_repo(tmp_path: Path) -> None:
    """Create a minimal initialized repo suitable for most commands."""
    (tmp_path / "docops.config.yaml").write_text(
        "project_name: TestProject\nrepo_prefix: TEST\ndocops_version: '2.0'\n"
        "namespaces:\n  default:\n    docs_root: docs\n    prefix: TEST\n"
        "    type_directories:\n      ADR: '45-adr'\n      PRD: '10-prd'\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "00-governance").mkdir()
    (docs / "00-governance" / "metadata.schema.json").write_text(
        '{"$schema": "http://json-schema.org/draft-07/schema#"}',
        encoding="utf-8",
    )
    (docs / "45-adr").mkdir()
    (docs / "10-prd").mkdir()


def _setup_state_repo(tmp_path: Path) -> None:
    """Create an initialized repo with a valid project-state.yaml."""
    _setup_initialized_repo(tmp_path)
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / "project-state.yaml").write_text(
        "state_schema_version: '2.0'\n"
        "documents:\n  TEST-ADR-001:\n    impl_state: Not Started\n"
        "    updated_by: test\n    updated: '2026-04-15T00:00:00+00:00'\n",
        encoding="utf-8",
    )


def _build_args(name: str, tmp_path: Path) -> list[str]:
    """Build the CLI argument list for a command invocation."""
    positional_args = {
        "new": ["ADR", "Test Document"],
        "adr new": ["Test ADR"],
        "explain": ["--list"],
        "resolve": ["TEST-ADR-001"],
        "identify": ["docs/45-adr/test.md"],
        "link": ["TEST-ADR-001"],
        "protocol check": [],
        "protocol sync": [],
        "state set": ["TEST-ADR-001", "--impl-state", "not-started"],
        "state get": ["TEST-ADR-001"],
        "state list": [],
        "state next": [],
        "state blockers": [],
        "org install": ["--dry-run"],
        "org vendor": [],
        "org status": [],
    }

    # Split compound command names for Click (e.g., "state list" → ["state", "list"])
    cmd_parts = name.split()
    args = cmd_parts + ["--format", "json"]

    if name not in _repo_agnostic_commands():
        args.extend(["--root", str(tmp_path)])

    if name in positional_args:
        args.extend(positional_args[name])

    return args


_STATE_COMMANDS = {"state set", "state get", "state list", "state next", "state blockers"}


def _setup_fixture(name: str, tmp_path: Path) -> None:
    """Set up the appropriate repo fixture for a command."""
    if name == "capabilities":
        return
    if name in _STATE_COMMANDS:
        _setup_state_repo(tmp_path)
    else:
        _setup_initialized_repo(tmp_path)


def _invoke_and_assert_output(name: str, tmp_path: Path, extra_args: list[str] | None = None):
    """Invoke a command and assert it produced valid output (not usage error or empty).

    Isolates MEMINIT_CORRELATION_ID from the parent environment so
    correlation-id-absence tests are deterministic.

    Returns the Click result for further assertions.
    """
    args = _build_args(name, tmp_path)
    if extra_args:
        args.extend(extra_args)
    env = {k: v for k, v in os.environ.items()}
    env["MEMINIT_CORRELATION_ID"] = None
    runner = CliRunner()
    result = runner.invoke(cli, args, env=env)

    assert result.exit_code != 2, (
        f"Command {name} hit usage error — check _build_args fixture: {result.output}"
    )
    assert result.output.strip(), f"Command {name} produced no output"
    return result


class TestEnvelopeValidity:
    """Every JSON-supporting command must produce a valid v3 envelope."""

    @pytest.mark.parametrize(
        "cmd_info",
        _get_json_commands(),
        ids=lambda c: c["name"],
    )
    def test_envelope_has_all_required_fields(self, cmd_info, tmp_path):
        """Each command must include all required envelope fields."""
        name = cmd_info["name"]
        _setup_fixture(name, tmp_path)

        result = _invoke_and_assert_output(name, tmp_path)
        data = parse_first_json_line(result.output)
        for field in _REQUIRED_FIELDS:
            assert field in data, f"Missing required field: {field}"

        # Repo-aware commands must include root; repo-agnostic must not.
        if name in _repo_agnostic_commands():
            assert "root" not in data, f"Repo-agnostic command {name} must not include root"
        else:
            assert "root" in data, f"Repo-aware command {name} must include root"

    @pytest.mark.parametrize(
        "cmd_info",
        _get_json_commands(),
        ids=lambda c: c["name"],
    )
    def test_correlation_id_echo(self, cmd_info, tmp_path):
        """When --correlation-id is provided, it must be echoed in output."""
        name = cmd_info["name"]
        _setup_fixture(name, tmp_path)

        result = _invoke_and_assert_output(name, tmp_path, ["--correlation-id", "test-cid-42"])
        data = parse_first_json_line(result.output)
        assert data.get("correlation_id") == "test-cid-42"

    @pytest.mark.parametrize(
        "cmd_info",
        _get_json_commands(),
        ids=lambda c: c["name"],
    )
    def test_correlation_id_omitted_when_not_provided(self, cmd_info, tmp_path):
        """When --correlation-id is NOT provided, field must be absent."""
        name = cmd_info["name"]
        _setup_fixture(name, tmp_path)

        result = _invoke_and_assert_output(name, tmp_path)
        data = parse_first_json_line(result.output)
        assert "correlation_id" not in data

    @pytest.mark.parametrize(
        "cmd_info",
        _get_json_commands(),
        ids=lambda c: c["name"],
    )
    def test_output_is_valid_json(self, cmd_info, tmp_path):
        """Output must be parseable JSON."""
        name = cmd_info["name"]
        _setup_fixture(name, tmp_path)

        result = _invoke_and_assert_output(name, tmp_path)
        non_empty_lines = [line for line in stdout_text(result).splitlines() if line.strip()]
        assert len(non_empty_lines) == 1, (
            f"Expected exactly one non-empty stdout line, got {len(non_empty_lines)}: {non_empty_lines!r}"
        )
        json.loads(non_empty_lines[0])

    @pytest.mark.parametrize(
        "cmd_info",
        _get_json_commands(),
        ids=lambda c: c["name"],
    )
    def test_envelope_validates_against_schema(self, cmd_info, tmp_path, agent_output_schema):
        """Envelope must validate against agent-output.schema.v3.json."""
        name = cmd_info["name"]
        _setup_fixture(name, tmp_path)

        result = _invoke_and_assert_output(name, tmp_path)
        payload = parse_first_json_line(result.output)
        errors = sorted(Draft7Validator(agent_output_schema).iter_errors(payload), key=str)
        assert not errors, (
            f"Schema validation errors for '{name}':\n"
            + "\n".join(f"  - {e.message}" for e in errors)
        )


class TestPayloadContracts:
    """Specific data-payload field assertions for v3 contracts."""

    def test_index_payload_fields(self, tmp_path):
        """Step 1: index data must match the CLI envelope contract (SPEC-008)."""
        _setup_initialized_repo(tmp_path)
        result = _invoke_and_assert_output("index", tmp_path)
        data = parse_first_json_line(result.output)["data"]

        # Required fields
        for field in ["index_path", "node_count", "edge_count", "nodes", "edges", "filtered"]:
            assert field in data, f"Missing required index field: {field}"

        # Persisted-artifact fields must NOT be in the CLI data payload
        for field in ["index_version", "graph_schema_version", "document_count"]:
            assert field not in data, f"Persisted-artifact field {field} leaked into CLI data"

    def test_protocol_sync_payload_fields(self, tmp_path):
        """Step 3: protocol sync must include dry_run as a stable field."""
        _setup_initialized_repo(tmp_path)

        # Dry-run mode (default)
        r1 = _invoke_and_assert_output("protocol sync", tmp_path)
        d1 = parse_first_json_line(r1.output)["data"]
        assert d1["dry_run"] is True
        assert "applied" in d1
        assert "summary" in d1
        assert "assets" in d1

        # Apply mode
        r2 = _invoke_and_assert_output("protocol sync", tmp_path, ["--no-dry-run"])
        d2 = parse_first_json_line(r2.output)["data"]
        assert d2["dry_run"] is False

    def test_resolve_identify_link_success_payloads(self, tmp_path):
        """Step 2: Successful resolution/identification/link payloads do not include 'found'."""
        _setup_initialized_repo(tmp_path)
        # Create a document so they succeed
        doc_path = tmp_path / "docs" / "45-adr" / "adr-001.md"
        doc_path.write_text(
            "---\ndocument_id: TEST-ADR-001\ntype: ADR\ntitle: Test\nstatus: Draft\ndocops_version: '2.0'\n---\n# Test",
            encoding="utf-8"
        )
        # We need an index for resolve/identify/link to work
        index_result = CliRunner().invoke(cli, ["index", "--root", str(tmp_path)])
        assert index_result.exit_code == 0, f"Indexing failed: {index_result.output}"

        runner = CliRunner()
        common_args = ["--format", "json", "--root", str(tmp_path)]

        # Resolve
        res = runner.invoke(cli, ["resolve"] + common_args + ["TEST-ADR-001"])
        assert res.exit_code == 0
        d_res = parse_first_json_line(res.output)["data"]
        assert "document_id" in d_res
        assert "path" in d_res
        assert "found" not in d_res

        # Identify
        ident = runner.invoke(cli, ["identify"] + common_args + ["docs/45-adr/adr-001.md"])
        assert ident.exit_code == 0
        d_ident = parse_first_json_line(ident.output)["data"]
        assert "path" in d_ident
        assert "document_id" in d_ident
        assert "found" not in d_ident

        # Link
        link = runner.invoke(cli, ["link"] + common_args + ["TEST-ADR-001"])
        assert link.exit_code == 0
        d_link = parse_first_json_line(link.output)["data"]
        assert "document_id" in d_link
        assert "link" in d_link
        assert "found" not in d_link

    def test_resolve_identify_link_not_found_behavior(self, tmp_path):
        """Step 2: Misses are represented as FILE_NOT_FOUND error envelopes."""
        _setup_initialized_repo(tmp_path)
        index_result = CliRunner().invoke(cli, ["index", "--root", str(tmp_path)])
        assert index_result.exit_code == 0, f"Indexing failed: {index_result.output}"

        for cmd in ["resolve", "identify", "link"]:
            args = cmd.split() + ["--format", "json", "--root", str(tmp_path), "NON_EXISTENT"]
            result = CliRunner().invoke(cli, args)
            assert result.exit_code != 0
            payload = parse_first_json_line(result.output)
            assert payload["success"] is False
            assert payload["error"]["code"] == "FILE_NOT_FOUND"
            assert "found" not in payload["data"]

    def test_capabilities_payload_fields(self, tmp_path):
        """CG-1: capabilities payload has required fields and no root."""
        result = _invoke_and_assert_output("capabilities", tmp_path)
        payload = parse_first_json_line(result.output)
        assert "root" not in payload
        data = payload["data"]
        for field in ["capabilities_version", "cli_version", "commands", "features", "error_codes"]:
            assert field in data, f"Missing {field} in capabilities data"

    def test_explain_single_payload_fields(self, tmp_path):
        """CG-1: explain single-code payload has correct detailed fields and no root."""
        # Invoke explain for a known code
        runner = CliRunner()
        result = runner.invoke(cli, ["explain", "FILE_NOT_FOUND", "--format", "json"])
        assert result.exit_code == 0
        payload = parse_first_json_line(result.output)
        assert "root" not in payload
        data = payload["data"]
        for field in ["code", "category", "summary", "cause", "remediation", "spec_reference"]:
            assert field in data, f"Missing {field} in explain single data"

        remed = data["remediation"]
        for r_field in ["action", "resolution_type", "automatable", "relevant_commands"]:
            assert r_field in remed, f"Missing {r_field} in remediation object"

    def test_explain_list_payload_fields(self, tmp_path):
        """CG-1: explain --list payload has correct summary fields and no root."""
        result = _invoke_and_assert_output("explain", tmp_path)
        payload = parse_first_json_line(result.output)
        assert "root" not in payload
        data = payload["data"]
        assert "error_codes" in data
        assert len(data["error_codes"]) > 0
        first_code = data["error_codes"][0]
        for field in ["code", "category", "summary"]:
            assert field in first_code, f"Missing {field} in explain --list entry"

    def test_protocol_check_payload_fields(self, tmp_path):
        """CG-1: protocol check payload has summary and assets fields."""
        _setup_initialized_repo(tmp_path)
        result = _invoke_and_assert_output("protocol check", tmp_path)
        data = parse_first_json_line(result.output)["data"]
        assert "summary" in data
        assert "assets" in data
        summary = data["summary"]
        for field in ["total", "aligned", "drifted", "unparseable"]:
            assert field in summary, f"Missing {field} in protocol check summary"

class TestCapabilitiesSelfConsistency:
    """Capabilities output must be internally consistent."""

    def test_capabilities_lists_all_click_commands(self):
        """Every Click command must appear in capabilities output."""
        import click

        caps = CapabilitiesUseCase().execute()
        cap_names = {c["name"] for c in caps["commands"]}

        click_names = set()
        for name, cmd in cli.commands.items():
            if isinstance(cmd, click.Group):
                for sub_name in cmd.commands:
                    click_names.add(f"{name} {sub_name}")
            elif isinstance(cmd, click.Command):
                click_names.add(name)

        missing = click_names - cap_names
        assert not missing, f"Commands missing from capabilities: {sorted(missing)}"


class TestExplainCompleteness:
    """Explain command must cover all error codes."""

    def test_explain_list_covers_all_error_codes(self):
        """Every ErrorCode must appear in explain --list output."""
        from meminit.core.services.error_codes import ErrorCode

        runner = CliRunner()
        result = runner.invoke(cli, ["explain", "--list", "--format", "json"])
        assert result.exit_code == 0
        data = parse_first_json_line(result.output)
        listed_codes = {e["code"] for e in data["data"]["error_codes"]}

        expected_codes = {code.value for code in ErrorCode}
        missing = expected_codes - listed_codes
        assert not missing, f"Error codes missing from explain --list: {sorted(missing)}"
