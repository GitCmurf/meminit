"""Tests for the capabilities registry and use case."""

import click

from importlib.metadata import PackageNotFoundError

import pytest

from meminit.cli.main import cli
from meminit.cli.shared_flags import _CAPABILITIES_REGISTRY
from meminit.core.services import versioning
from meminit.core.use_cases.capabilities import CapabilitiesUseCase


def test_all_click_commands_have_capabilities_entry():
    """Fail if a new command is added without a corresponding registry entry."""
    registered_names = set(_CAPABILITIES_REGISTRY.keys())
    click_commands = set()

    for name, cmd in cli.commands.items():
        if isinstance(cmd, click.Group):
            for sub_name, _ in cmd.commands.items():
                click_commands.add(f"{name} {sub_name}")
        elif isinstance(cmd, click.Command):
            click_commands.add(name)

    missing = click_commands - registered_names
    assert not missing, f"Commands missing from capabilities registry: {sorted(missing)}"


def test_capabilities_use_case_returns_deterministic_output():
    """CapabilitiesUseCase.execute() returns a fully deterministic dict."""
    use_case = CapabilitiesUseCase()
    data1 = use_case.execute()
    data2 = use_case.execute()
    assert data1 == data2



def test_capabilities_use_case_falls_back_to_pyproject_version(monkeypatch):
    """Capabilities must work in source-tree runs when package metadata is absent."""
    monkeypatch.setattr(
        versioning,
        "package_version",
        lambda _name: (_ for _ in ()).throw(PackageNotFoundError("meminit")),
    )
    versioning.get_cli_version.cache_clear()

    caps = CapabilitiesUseCase().execute()
    assert caps["cli_version"] == versioning.get_cli_version()
    versioning.get_cli_version.cache_clear()


def test_capabilities_includes_required_fields():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()

    assert "capabilities_version" in caps
    assert "cli_version" in caps
    assert "output_schema_version" in caps
    assert "commands" in caps
    assert "output_formats" in caps
    assert "global_flags" in caps
    assert "features" in caps
    assert "error_codes" in caps


def test_capabilities_commands_sorted_by_name():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    names = [c["name"] for c in caps["commands"]]
    assert names == sorted(names)


def test_capabilities_error_codes_sorted():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    assert caps["error_codes"] == sorted(caps["error_codes"])


def test_capabilities_global_flags_sorted():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    flags = [f["flag"] for f in caps["global_flags"]]
    assert flags == sorted(flags)


def test_capabilities_output_formats_sorted():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    assert caps["output_formats"] == sorted(caps["output_formats"])


def test_capabilities_commands_have_required_metadata():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()

    for cmd in caps["commands"]:
        assert "name" in cmd
        assert "description" in cmd
        assert "supports_json" in cmd
        assert "supports_correlation_id" in cmd
        assert "needs_root" in cmd
        assert "agent_facing" in cmd
        assert isinstance(cmd["supports_json"], bool)
        assert isinstance(cmd["supports_correlation_id"], bool)
        assert isinstance(cmd["needs_root"], bool)
        assert isinstance(cmd["agent_facing"], bool)


def test_capabilities_features_are_boolean():
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()

    for feat, value in caps["features"].items():
        assert isinstance(value, bool), f"features.{feat} is not boolean"


def test_human_oriented_commands_marked_not_agent_facing():
    """Commands that are human workflow steps should have agent_facing=False."""
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    non_agent = [c["name"] for c in caps["commands"] if not c["agent_facing"]]
    assert "install-precommit" in non_agent
    assert "org install" in non_agent
    assert "org vendor" in non_agent
    assert "org status" in non_agent
    assert len(non_agent) >= 4


def test_registry_has_agent_and_non_agent_entries():
    """At least one command is agent_facing and at least one is not."""
    agent = [n for n, e in _CAPABILITIES_REGISTRY.items() if e["agent_facing"]]
    non_agent = [n for n, e in _CAPABILITIES_REGISTRY.items() if not e["agent_facing"]]
    assert agent, "At least one command must be agent_facing=True"
    assert non_agent, "At least one command must be agent_facing=False"


def test_global_flags_match_shared_options():
    """Each declared global flag must correspond to an actual shared option."""
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    flag_names = {f["flag"] for f in caps["global_flags"]}

    # Expected universal flags from agent_output_options() — --root is NOT
    # universal (repo-agnostic commands don't accept it); agents should check
    # per-command `needs_root` instead.
    expected = {"--format", "--correlation-id", "--include-timestamp", "--output"}
    missing = expected - flag_names
    extra = flag_names - expected
    assert not missing, f"Global flags missing from capabilities: {sorted(missing)}"
    assert not extra, f"Extra global flags not in shared options: {sorted(extra)}"


def test_agent_facing_commands_support_json_and_correlation():
    """PR-7 guardrail: every agent_facing=True capability must advertise supports_json=True and supports_correlation_id=True."""
    use_case = CapabilitiesUseCase()
    caps = use_case.execute()
    violations = []
    for cmd in caps["commands"]:
        if cmd["agent_facing"]:
            if not cmd["supports_json"]:
                violations.append(f"{cmd['name']}: supports_json=False")
            if not cmd["supports_correlation_id"]:
                violations.append(f"{cmd['name']}: supports_correlation_id=False")
    assert not violations, (
        "Agent-facing commands must support JSON and correlation IDs: "
        + "; ".join(violations)
    )
