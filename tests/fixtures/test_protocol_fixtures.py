"""Fixture-driven protocol check/sync tests (F01-F13, F14-F15)."""

import json
from pathlib import Path

import pytest

from meminit.core.use_cases.protocol_check import ProtocolChecker
from meminit.core.use_cases.protocol_sync import ProtocolSyncer
from tests.fixtures.protocol.conftest import FIXTURE_SCENARIOS


@pytest.fixture
def fresh_repo(tmp_path):
    return tmp_path


class TestProtocolCheckFixtures:
    """Parametrized check tests using fixture scenarios F01-F13."""

    @pytest.mark.parametrize(
        "scenario_id",
        list(FIXTURE_SCENARIOS.keys()),
        ids=lambda sid: f"{sid}: {FIXTURE_SCENARIOS[sid][1]}",
    )
    def test_check_outcome(self, scenario_id, fresh_repo):
        setup_fn, _ = FIXTURE_SCENARIOS[scenario_id]
        meta = setup_fn(fresh_repo)

        asset_ids = [meta["filter_asset"]] if "filter_asset" in meta else None
        checker = ProtocolChecker(str(fresh_repo))
        report = checker.execute(asset_ids=asset_ids)

        if meta.get("expected_check_success") == "true":
            assert report.success is True
        else:
            assert report.success is False

        if "expected_drifted" in meta:
            expected_drifted_key = "filter_expected_drifted" if "filter_asset" in meta else "expected_drifted"
            expected_drifted = int(meta[expected_drifted_key])
            assert report.summary["drifted"] == expected_drifted

        if "expected_missing" in meta:
            asset_ids_in_report = [a["id"] for a in report.assets]
            drifted_ids = [a["id"] for a in report.assets if a["status"] != "aligned"]
            assert meta["expected_missing"] in drifted_ids

        if "expected_legacy" in meta:
            drifted = [a for a in report.assets if a["status"] != "aligned"]
            legacy_ids = [a["id"] for a in drifted if a["status"] == "legacy"]
            assert meta["expected_legacy"] in legacy_ids

        if "expected_stale" in meta:
            drifted = [a for a in report.assets if a["status"] != "aligned"]
            stale_ids = [a["id"] for a in drifted if a["status"] == "stale"]
            assert meta["expected_stale"] in stale_ids

        if "expected_tampered" in meta:
            drifted = [a for a in report.assets if a["status"] != "aligned"]
            tampered_ids = [a["id"] for a in drifted if a["status"] == "tampered"]
            assert meta["expected_tampered"] in tampered_ids

        if "expected_unparseable" in meta:
            unparseable_ids = [a["id"] for a in report.assets if a["status"] == "unparseable"]
            assert meta["expected_unparseable"] in unparseable_ids


class TestProtocolSyncFixtures:
    """Parametrized sync tests using fixture scenarios F02-F10."""

    @pytest.mark.parametrize(
        "scenario_id",
        ["F02", "F03", "F04", "F05", "F06", "F10"],
        ids=lambda sid: f"{sid}: {FIXTURE_SCENARIOS[sid][1]}",
    )
    def test_sync_rewrites_drifted(self, scenario_id, fresh_repo):
        setup_fn, _ = FIXTURE_SCENARIOS[scenario_id]
        meta = setup_fn(fresh_repo)

        syncer = ProtocolSyncer(str(fresh_repo))
        report = syncer.execute(dry_run=False)

        drifted_assets = [a for a in report.assets if a["action"] == "rewrite"]
        assert len(drifted_assets) >= 1

        # Second sync should be all noop
        r2 = syncer.execute(dry_run=False)
        assert r2.summary["noop"] == r2.summary["total"]

    @pytest.mark.parametrize(
        "scenario_id",
        ["F07"],
        ids=lambda sid: f"{sid}: {FIXTURE_SCENARIOS[sid][1]}",
    )
    def test_sync_refuses_tampered_without_force(self, scenario_id, fresh_repo):
        setup_fn, _ = FIXTURE_SCENARIOS[scenario_id]
        meta = setup_fn(fresh_repo)

        syncer = ProtocolSyncer(str(fresh_repo))
        report = syncer.execute(dry_run=False, force=False)
        tampered_assets = [a for a in report.assets if a["action"] == "refuse"]
        assert len(tampered_assets) >= 1

    @pytest.mark.parametrize(
        "scenario_id",
        ["F08", "F09", "F16", "F17"],
        ids=lambda sid: f"{sid}: {FIXTURE_SCENARIOS[sid][1]}",
    )
    def test_sync_always_refuses_unparseable(self, scenario_id, fresh_repo):
        setup_fn, _ = FIXTURE_SCENARIOS[scenario_id]
        meta = setup_fn(fresh_repo)

        syncer = ProtocolSyncer(str(fresh_repo))
        report = syncer.execute(dry_run=False, force=True)
        refused = [a for a in report.assets if a["action"] == "refuse"]
        assert len(refused) >= 1


class TestIdempotency:
    """F14: Second sync is idempotent (no writes)."""

    def test_sync_twice_is_idempotent(self, fresh_repo):
        from tests.fixtures.protocol.conftest import setup_f02_missing_agents_md

        setup_f02_missing_agents_md(fresh_repo)
        syncer = ProtocolSyncer(str(fresh_repo))

        r1 = syncer.execute(dry_run=False)
        assert r1.summary["rewritten"] >= 1

        r2 = syncer.execute(dry_run=False)
        assert r2.summary["noop"] == r2.summary["total"]
        assert r2.applied is False


class TestDeterminism:
    """F15: Identical logical repo states produce identical data payloads."""

    def test_check_determinism(self, tmp_path):
        from tests.fixtures.protocol.conftest import setup_f04_legacy_agents_md

        dir_a = tmp_path / "repo_a"
        dir_b = tmp_path / "repo_b"
        dir_a.mkdir()
        dir_b.mkdir()

        setup_f04_legacy_agents_md(dir_a)
        setup_f04_legacy_agents_md(dir_b)

        checker_a = ProtocolChecker(str(dir_a))
        checker_b = ProtocolChecker(str(dir_b))

        report_a = checker_a.execute()
        report_b = checker_b.execute()

        # Compare serializable fields
        assert report_a.summary == report_b.summary
        assert report_a.success == report_b.success

        # Compare asset statuses (sorted for deterministic order)
        assets_a = sorted(report_a.assets, key=lambda a: a["id"])
        assets_b = sorted(report_b.assets, key=lambda a: a["id"])
        assert assets_a == assets_b

    def test_sync_determinism(self, tmp_path):
        from tests.fixtures.protocol.conftest import setup_f02_missing_agents_md

        dir_a = tmp_path / "repo_a"
        dir_b = tmp_path / "repo_b"
        dir_a.mkdir()
        dir_b.mkdir()

        setup_f02_missing_agents_md(dir_a)
        setup_f02_missing_agents_md(dir_b)

        syncer_a = ProtocolSyncer(str(dir_a))
        syncer_b = ProtocolSyncer(str(dir_b))

        report_a = syncer_a.execute(dry_run=False)
        report_b = syncer_b.execute(dry_run=False)

        # Compare non-volatile fields
        assert report_a.summary == report_b.summary
        assert report_a.success == report_b.success

        assets_a = sorted(report_a.assets, key=lambda a: a["id"])
        assets_b = sorted(report_b.assets, key=lambda a: a["id"])
        assert assets_a == assets_b
