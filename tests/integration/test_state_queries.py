"""Q01-Q20 fixture matrix for Phase 4 state query commands.

Each fixture is materialized programmatically (builder pattern) per
PLAN-013 section 3.5.2. Tests are parametrized over the 20 scenarios.
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest
import yaml
from click.testing import CliRunner

from meminit.cli.main import cli
from meminit.core.services.error_codes import ErrorCode
from meminit.core.use_cases.state_document import StateDocumentUseCase
from tests.helpers import parse_first_json_line


def _runner() -> CliRunner:
    import inspect
    kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        kwargs["mix_stderr"] = False
    return CliRunner(**kwargs)


def _write_config(tmp_path: Path, prefix: str = "Q") -> None:
    (tmp_path / "docops.config.yaml").write_text(
        f"project_name: Fixture\nrepo_prefix: {prefix}\ndocops_version: '2.0'\n"
        f"namespaces:\n  default:\n    docs_root: docs\n    prefix: {prefix}\n"
        f"    type_directories:\n      ADR: '45-adr'\n",
        encoding="utf-8",
    )
    docs = tmp_path / "docs"
    docs.mkdir(exist_ok=True)
    (docs / "00-governance").mkdir(exist_ok=True)
    (docs / "00-governance" / "metadata.schema.json").write_text("{}", encoding="utf-8")
    (docs / "45-adr").mkdir(exist_ok=True)
    (docs / "01-indices").mkdir(parents=True, exist_ok=True)


def _write_state(tmp_path: Path, documents: Dict[str, Dict[str, Any]]) -> Path:
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "project-state.yaml"
    payload = {"state_schema_version": "2.0", "documents": documents}
    state_path.write_text(
        yaml.dump(payload, default_flow_style=False, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )
    return state_path


def _make_entry(
    impl_state: str = "Not Started",
    updated_by: str = "test",
    updated: str = "2026-01-01T00:00:00+00:00",
    priority: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    blocked_by: Optional[List[str]] = None,
    assignee: Optional[str] = None,
    next_action: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "impl_state": impl_state,
        "updated_by": updated_by,
        "updated": updated,
    }
    if priority is not None:
        entry["priority"] = priority
    if depends_on:
        entry["depends_on"] = depends_on
    if blocked_by:
        entry["blocked_by"] = blocked_by
    if assignee is not None:
        entry["assignee"] = assignee
    if next_action is not None:
        entry["next_action"] = next_action
    if notes is not None:
        entry["notes"] = notes
    return entry


def _invoke_state_next(tmp_path: Path, **extra_flags) -> Dict[str, Any]:
    args = ["state", "next", "--root", str(tmp_path), "--format", "json"]
    for k, v in extra_flags.items():
        k = k.replace("_", "-")
        if isinstance(v, bool) and v:
            args.append(f"--{k}")
        elif isinstance(v, str):
            args.extend([f"--{k}", v])
    result = _runner().invoke(cli, args)
    if result.exit_code == 0:
        return json.loads(result.output.strip().splitlines()[-1])
    return {"_exit_code": result.exit_code, "_output": result.output}


def _invoke_state_blockers(tmp_path: Path, **extra_flags) -> Dict[str, Any]:
    args = ["state", "blockers", "--root", str(tmp_path), "--format", "json"]
    for k, v in extra_flags.items():
        k = k.replace("_", "-")
        if isinstance(v, str):
            args.extend([f"--{k}", v])
    result = _runner().invoke(cli, args)
    if result.exit_code == 0:
        return json.loads(result.output.strip().splitlines()[-1])
    return {"_exit_code": result.exit_code, "_output": result.output}


def _invoke_state_list(tmp_path: Path, **extra_flags) -> Dict[str, Any]:
    args = ["state", "list", "--root", str(tmp_path), "--format", "json"]
    for k, v in extra_flags.items():
        k = k.replace("_", "-")
        if isinstance(v, bool) and v:
            args.append(f"--{k}")
        elif isinstance(v, str):
            args.extend([f"--{k}", v])
    result = _runner().invoke(cli, args)
    if result.exit_code == 0:
        return json.loads(result.output.strip().splitlines()[-1])
    return {"_exit_code": result.exit_code, "_output": result.output}


# --- Fixture builder: returns (tmp_path with repo, expected) ---

def _write_state_legacy(tmp_path: Path, documents: Dict[str, Dict[str, Any]]) -> Path:
    state_dir = tmp_path / "docs" / "01-indices"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / "project-state.yaml"
    payload = {"documents": documents}
    state_path.write_text(
        yaml.dump(payload, default_flow_style=False, allow_unicode=True, sort_keys=True),
        encoding="utf-8",
    )
    return state_path


def _setup_q01(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state_legacy(tmp_path, {
        "FIX-ADR-001": {
            "impl_state": "Not Started",
            "updated_by": "test",
            "updated": "2026-01-01T00:00:00+00:00",
        },
    })
    return {"id": "Q01", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q02(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
        "FIX-ADR-003": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
    })
    return {"id": "Q02", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q03(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", priority="P0"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started"),
    })
    return {"id": "Q03", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q04(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", updated="2026-06-01T00:00:00+00:00"),
    })
    return {"id": "Q04", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q05(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started"),
        "FIX-ADR-003": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-002"]),
        "FIX-ADR-004": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-002"]),
    })
    return {"id": "Q05", "expected_reason": None, "expected_doc": "FIX-ADR-002"}


def _setup_q06(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", updated="2026-01-01T00:00:00+00:00"),
    })
    return {"id": "Q06", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q07(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-002"]),
        "FIX-ADR-002": _make_entry(impl_state="Done"),
    })
    return {"id": "Q07", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q08(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-002"]),
        "FIX-ADR-002": _make_entry(impl_state="In Progress"),
    })
    return {"id": "Q08", "expected_reason": "queue_empty", "expected_doc": None}


def _setup_q09(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-999"]),
    })
    return {"id": "Q09", "expected_reason": "queue_empty", "expected_doc": None}


def _setup_q10(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-002"]),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-001"]),
    })
    return {"id": "Q10", "expected_error": "STATE_DEPENDENCY_CYCLE"}


def _setup_q11(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started"),
    })
    return {"id": "Q11", "expected_error": "STATE_SELF_DEPENDENCY"}


def _setup_q12(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started"),
    })
    return {"id": "Q12", "expected_error": "STATE_INVALID_PRIORITY"}


def _setup_q13(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started"),
    })
    return {"id": "Q13", "expected_error": "STATE_FIELD_TOO_LONG"}


def _setup_q14(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", priority="P0", assignee="agent:codex"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", priority="P1", assignee="agent:codex"),
        "FIX-ADR-003": _make_entry(impl_state="Not Started", priority="P0", assignee="human:alice"),
    })
    return {"id": "Q14", "expected_reason": None, "expected_doc": "FIX-ADR-001"}


def _setup_q15(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="In Progress"),
    })
    return {"id": "Q15", "expected_reason": "queue_empty", "expected_doc": None}


def _setup_q16(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    return {"id": "Q16", "expected_reason": "state_missing", "expected_doc": None}


def _setup_q17(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Done", depends_on=["FIX-ADR-002"]),
        "FIX-ADR-002": _make_entry(impl_state="In Progress"),
    })
    return {"id": "Q17"}


def _setup_q18(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started"),
    })
    return {"id": "Q18"}


def _setup_q19(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", priority="P1"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started", depends_on=["FIX-ADR-001"]),
    })
    return {"id": "Q19"}


def _setup_q20(tmp_path: Path) -> dict:
    _write_config(tmp_path)
    (tmp_path / "docs" / "45-adr" / "adr-001.md").write_text(
        "---\ndocument_id: FIX-ADR-001\ntitle: Test ADR\nstatus: Draft\n---\nBody",
        encoding="utf-8",
    )
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", priority="P0", assignee="agent:codex"),
    })
    return {"id": "Q20"}


_FIXTURE_BUILDERS = {
    "Q01": _setup_q01, "Q02": _setup_q02, "Q03": _setup_q03, "Q04": _setup_q04,
    "Q05": _setup_q05, "Q06": _setup_q06, "Q07": _setup_q07, "Q08": _setup_q08,
    "Q09": _setup_q09, "Q10": _setup_q10, "Q11": _setup_q11, "Q12": _setup_q12,
    "Q13": _setup_q13, "Q14": _setup_q14, "Q15": _setup_q15, "Q16": _setup_q16,
    "Q17": _setup_q17, "Q18": _setup_q18, "Q19": _setup_q19, "Q20": _setup_q20,
}


# --- Unified scenario registry ---
#
# Maps scenario ID → {test_function: parametrize_id_or_None}.
# The _FIXTURE_BUILDERS dict is the single source of truth for which
# scenarios exist. The test functions below each select their relevant
# subset from _ALL_SCENARIO_IDS.

_ALL_SCENARIO_IDS = sorted(_FIXTURE_BUILDERS.keys())

_NEXT_SCENARIOS = [
    "Q01", "Q02", "Q03", "Q04", "Q05", "Q06", "Q07", "Q08",
    "Q09", "Q14", "Q15", "Q16",
]

_BLOCKERS_SCENARIOS = ["Q08", "Q09"]

_SET_VALIDATION_SCENARIOS = ["Q10", "Q11", "Q12", "Q13"]


@pytest.mark.parametrize("scenario_id", _NEXT_SCENARIOS)
def test_state_next_selection(scenario_id: str, tmp_path: Path):
    meta = _FIXTURE_BUILDERS[scenario_id](tmp_path)
    data = _invoke_state_next(tmp_path)

    assert data["success"] is True
    entry = data["data"]["entry"]
    reason = data["data"]["reason"]

    if meta.get("expected_doc") is None:
        assert entry is None
        assert reason == meta["expected_reason"]
    else:
        assert entry is not None
        assert entry["document_id"] == meta["expected_doc"]
        assert data["data"]["selection"]["rule"] is not None


@pytest.mark.parametrize("scenario_id", _BLOCKERS_SCENARIOS)
def test_state_blockers(scenario_id: str, tmp_path: Path):
    meta = _FIXTURE_BUILDERS[scenario_id](tmp_path)
    data = _invoke_state_blockers(tmp_path)

    assert data["success"] is True
    blocked = data["data"]["blocked"]

    if scenario_id == "Q08":
        assert len(blocked) >= 1
        blocked_ids = [b["document_id"] for b in blocked]
        assert "FIX-ADR-001" in blocked_ids
        b001 = next(b for b in blocked if b["document_id"] == "FIX-ADR-001")
        assert any(ob["id"] == "FIX-ADR-002" for ob in b001["open_blockers"])
    elif scenario_id == "Q09":
        assert len(blocked) >= 1


# --- Parametrized state set validation (Q10, Q11, Q12, Q13) ---

@pytest.mark.parametrize("scenario_id", _SET_VALIDATION_SCENARIOS)
def test_state_set_validation(scenario_id: str, tmp_path: Path):
    meta = _FIXTURE_BUILDERS[scenario_id](tmp_path)
    runner = _runner()

    if scenario_id == "Q10":
        state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
        assert state_file.exists()
        original = state_file.read_text()

        result = runner.invoke(cli, [
            "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
            "--add-depends-on", "FIX-ADR-002", "--root", str(tmp_path), "--format", "json",
        ])
        assert result.exit_code != 0
        assert "STATE_DEPENDENCY_CYCLE" in result.output
        assert state_file.read_text() == original

    elif scenario_id == "Q11":
        result = runner.invoke(cli, [
            "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
            "--add-depends-on", "FIX-ADR-001", "--root", str(tmp_path), "--format", "json",
        ])
        assert result.exit_code != 0
        assert "STATE_SELF_DEPENDENCY" in result.output

    elif scenario_id == "Q12":
        result = runner.invoke(cli, [
            "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
            "--priority", "P9", "--root", str(tmp_path), "--format", "json",
        ])
        assert result.exit_code != 0
        assert "STATE_INVALID_PRIORITY" in result.output

    elif scenario_id == "Q13":
        long_action = "x" * 600
        result = runner.invoke(cli, [
            "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
            "--next-action", long_action, "--root", str(tmp_path), "--format", "json",
        ])
        assert result.exit_code != 0
        assert "STATE_FIELD_TOO_LONG" in result.output


# --- Q17: Advisory-only status conflict ---

def test_state_advisory_q17(tmp_path: Path):
    _setup_q17(tmp_path)
    data = _invoke_state_list(tmp_path)

    assert data["success"] is True
    advice = data["advice"]
    advice_codes = [a["code"] for a in advice]
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" in advice_codes
    assert "advice" not in data["data"]
    for a in advice:
        assert "code" in a, f"Advice item missing 'code': {a}"
        assert "message" in a, f"Advice item missing 'message': {a}"
        assert "document_id" in a, f"Advice item missing 'document_id': {a}"
        assert "path" in a, f"Advice item missing 'path': {a}"


# --- Q18: Idempotency (state set) ---

def test_state_idempotency_q18_file_hash(tmp_path: Path):
    _setup_q18(tmp_path)
    state_file = tmp_path / "docs" / "01-indices" / "project-state.yaml"
    use_case = StateDocumentUseCase(str(tmp_path))

    use_case.set_state("FIX-ADR-001", impl_state="Not Started", priority="P1")
    first_hash = hashlib.sha256(state_file.read_bytes()).hexdigest()

    use_case.set_state("FIX-ADR-001", impl_state="Not Started", priority="P1")
    second_hash = hashlib.sha256(state_file.read_bytes()).hexdigest()

    assert first_hash == second_hash


def test_state_idempotency_q18_cli_envelope_bytes(tmp_path: Path):
    """Q18 byte-exact regression: two consecutive CLI state set calls with
    the same flags must produce byte-identical JSON envelopes on stdout."""
    _setup_q18(tmp_path)
    runner = _runner()

    r1 = runner.invoke(cli, [
        "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
        "--priority", "P1", "--root", str(tmp_path), "--format", "json",
    ])
    r2 = runner.invoke(cli, [
        "state", "set", "FIX-ADR-001", "--impl-state", "Not Started",
        "--priority", "P1", "--root", str(tmp_path), "--format", "json",
    ])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    stdout1 = r1.output.strip().splitlines()[-1]
    stdout2 = r2.output.strip().splitlines()[-1]
    assert stdout1 == stdout2


# --- Q19: Determinism (state list byte-identical envelopes) ---

def test_state_determinism_q19_state_list(tmp_path: Path):
    """Q19 byte-exact regression: two state list calls must produce
    byte-identical stdout (not just logically-equivalent JSON)."""
    _setup_q19(tmp_path)
    runner = _runner()

    r1 = runner.invoke(cli, [
        "state", "list", "--root", str(tmp_path), "--format", "json",
    ])
    r2 = runner.invoke(cli, [
        "state", "list", "--root", str(tmp_path), "--format", "json",
    ])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    stdout1 = r1.output.strip().splitlines()[-1]
    stdout2 = r2.output.strip().splitlines()[-1]
    assert stdout1 == stdout2


def test_state_determinism_q19_state_next(tmp_path: Path):
    """Q19 byte-exact regression: two state next calls must produce
    byte-identical stdout."""
    _setup_q19(tmp_path)
    runner = _runner()

    r1 = runner.invoke(cli, [
        "state", "next", "--root", str(tmp_path), "--format", "json",
    ])
    r2 = runner.invoke(cli, [
        "state", "next", "--root", str(tmp_path), "--format", "json",
    ])
    assert r1.exit_code == 0
    assert r2.exit_code == 0
    stdout1 = r1.output.strip().splitlines()[-1]
    stdout2 = r2.output.strip().splitlines()[-1]
    assert stdout1 == stdout2


# --- Q20: Index integration with v2 state fields ---

def test_index_v2_integration_q20(tmp_path: Path):
    _setup_q20(tmp_path)
    runner = _runner()

    result = runner.invoke(cli, [
        "index", "--root", str(tmp_path), "--format", "json",
    ])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])

    nodes = data["data"]["nodes"]
    assert len(nodes) == 1
    node = nodes[0]
    assert node["document_id"] == "FIX-ADR-001"
    assert node.get("priority") == "P0"
    assert "ready" in node
    assert "open_blockers" in node
    assert "unblocks" in node

    index_path = tmp_path / "docs" / "01-indices" / "meminit.index.json"
    assert index_path.exists()
    persisted = json.loads(index_path.read_text())
    assert persisted["data"]["nodes"][0]["priority"] == "P0"


# ---------------------------------------------------------------------------
# AR-B: Scenario × command parametrized envelope-shape matrix
# ---------------------------------------------------------------------------

_COMMAND_INVOKE = {
    "state_next": lambda p: _invoke_state_next(p),
    "state_list": lambda p: _invoke_state_list(p),
    "state_blockers": lambda p: _invoke_state_blockers(p),
}

_SCENARIO_COMMANDS: Dict[str, List[str]] = {
    "Q01": ["state_next", "state_list"],
    "Q02": ["state_next", "state_list"],
    "Q03": ["state_next", "state_list"],
    "Q04": ["state_next", "state_list"],
    "Q05": ["state_next", "state_list"],
    "Q06": ["state_next", "state_list"],
    "Q07": ["state_next", "state_list"],
    "Q08": ["state_next", "state_list", "state_blockers"],
    "Q09": ["state_next", "state_list", "state_blockers"],
    "Q14": ["state_next", "state_list"],
    "Q15": ["state_next", "state_list"],
    "Q16": ["state_next", "state_list"],
    "Q17": ["state_list"],
    "Q18": ["state_list"],
    "Q19": ["state_next", "state_list"],
    "Q20": ["state_list"],
}

_CROSS_PRODUCT = [
    pytest.param(sid, cmd, id=f"{sid}-{cmd}")
    for sid, cmds in sorted(_SCENARIO_COMMANDS.items())
    for cmd in cmds
]


@pytest.mark.parametrize("scenario_id,command", _CROSS_PRODUCT)
def test_scenario_command_envelope_shape(scenario_id: str, command: str, tmp_path: Path):
    meta = _FIXTURE_BUILDERS[scenario_id](tmp_path)
    data = _COMMAND_INVOKE[command](tmp_path)

    if "expected_error" in meta:
        assert data.get("_exit_code", 0) != 0
        return

    assert data["success"] is True, f"{scenario_id}/{command} failed: {data}"
    assert data["output_schema_version"] == "3.0"
    assert "data" in data
    assert "warnings" in data

    entries = data["data"].get("entries")
    entry = data["data"].get("entry")
    target = entries or ([entry] if entry else [])
    for e in target:
        if e is None:
            continue
        assert "ready" in e, f"{scenario_id}/{command}: missing 'ready' on {e.get('document_id')}"
        assert "open_blockers" in e, f"{scenario_id}/{command}: missing 'open_blockers'"
        assert "unblocks" in e, f"{scenario_id}/{command}: missing 'unblocks'"


# ---------------------------------------------------------------------------
# AR-new-3: P2 fidelity — explicit P2 round-trips, absent stays absent
# ---------------------------------------------------------------------------

def test_index_p2_round_trips_and_none_is_absent(tmp_path):
    """Explicit P2 persists to index node; absent priority stays absent (AR-new-3)."""
    _write_config(tmp_path)
    (tmp_path / "docs" / "45-adr" / "adr-001.md").write_text(
        "---\ndocument_id: FIX-ADR-001\ntitle: P2 Doc\nstatus: Draft\n---\nBody",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "45-adr" / "adr-002.md").write_text(
        "---\ndocument_id: FIX-ADR-002\ntitle: No Priority Doc\nstatus: Draft\n---\nBody",
        encoding="utf-8",
    )
    _write_state(tmp_path, {
        "FIX-ADR-001": _make_entry(impl_state="Not Started", priority="P2"),
        "FIX-ADR-002": _make_entry(impl_state="Not Started"),
    })
    runner = _runner()
    result = runner.invoke(cli, ["index", "--root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    data = json.loads(result.output.strip().splitlines()[-1])
    nodes = {n["document_id"]: n for n in data["data"]["nodes"]}
    assert nodes["FIX-ADR-001"].get("priority") == "P2", "Explicit P2 must round-trip"
    assert "priority" not in nodes["FIX-ADR-002"], "No-priority entry must not have priority key"


def test_q01_legacy_v1_no_migration_warning(tmp_path):
    """Q01: Legacy v1 state file (no schema_version key) reads succeed without schema/migration warnings."""
    _write_config(tmp_path)
    _write_state_legacy(tmp_path, {
        "FIX-ADR-001": {
            "impl_state": "Not Started",
            "updated_by": "test",
            "updated": "2026-01-01T00:00:00+00:00",
        },
    })
    data = _invoke_state_next(tmp_path)
    assert data["success"] is True
    assert data["data"]["entry"] is not None
    assert data["data"]["entry"]["document_id"] == "FIX-ADR-001"
    migration_codes = [
        w["code"] for w in (data.get("warnings") or [])
        if "SCHEMA" in w.get("code", "") or "MIGRATION" in w.get("code", "")
    ]
    assert migration_codes == [], f"Legacy v1 should not emit schema/migration warnings: {migration_codes}"
