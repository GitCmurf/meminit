from __future__ import annotations

import json
from pathlib import Path

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.index_cache import IndexCache, _cache_key


def _write_cache_doc(root: Path, *, body: str = "Content") -> Path:
    doc_path = root / "docs" / "45-adr" / "adr-001.md"
    doc_path.parent.mkdir(parents=True, exist_ok=True)
    doc_path.write_text(body, encoding="utf-8")
    return doc_path


def _seed_cache(cache: IndexCache, doc_path: Path, context: dict[str, str]) -> None:
    fingerprint = cache.fingerprint(doc_path, rel_path="docs/45-adr/adr-001.md")
    cache.write(
        context=context,
        fingerprints={"docs/45-adr/adr-001.md": fingerprint},
        entries=[
            {
                "document_id": "EXAMPLE-ADR-001",
                "path": "docs/45-adr/adr-001.md",
            }
        ],
    )


def test_index_cache_explain_missing_manifest(tmp_path):
    summary = IndexCache(tmp_path).explain()

    assert summary == {
        "cache_path": ".meminit/cache/index/manifest.json",
        "exists": False,
    }


def test_index_cache_explain_reads_manifest_summary(tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    cache.manifest_path.write_text(
        json.dumps(
            {
                "manifest_schema_version": "1.0",
                "config_sha256": "config",
                "schema_sha256": "schema",
                "files": [{"path": "docs/a.md"}, {"path": "docs/b.md"}],
            }
        ),
        encoding="utf-8",
    )

    assert cache.explain() == {
        "cache_path": ".meminit/cache/index/manifest.json",
        "exists": True,
        "manifest_schema_version": "1.0",
        "file_count": 2,
        "config_sha256": "config",
        "schema_sha256": "schema",
    }


def test_index_cache_explain_reports_invalid_manifest(tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    cache.manifest_path.write_text("{bad json", encoding="utf-8")

    summary = cache.explain()

    assert summary["exists"] is True
    assert summary["warning"]["code"] == ErrorCode.CACHE_ENTRY_INVALID.value
    assert "JSONDecodeError" in summary["warning"]["message"]


def test_index_cache_explain_reports_non_object_manifest(tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    cache.manifest_path.write_text("[]", encoding="utf-8")

    summary = cache.explain()

    assert summary["exists"] is True
    assert summary["warning"]["code"] == ErrorCode.CACHE_ENTRY_INVALID.value
    assert "list" in summary["warning"]["message"]


def test_index_cache_explain_rejects_symlinked_manifest(tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    outside = tmp_path.parent / "outside-manifest.json"
    outside.write_text(
        '{"manifest_schema_version":"1.0","files":[]}', encoding="utf-8"
    )
    cache.manifest_path.symlink_to(outside)

    with pytest.raises(MeminitError) as exc_info:
        cache.explain()

    assert exc_info.value.code is ErrorCode.PATH_ESCAPE


def test_index_cache_clear_removes_directory(tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    cache.manifest_path.write_text("{}", encoding="utf-8")

    assert cache.clear() is True
    assert not cache.cache_dir.exists()
    assert cache.clear() is False


def test_index_cache_clear_rejects_unsafe_target(monkeypatch, tmp_path):
    cache = IndexCache(tmp_path)
    cache.manifest_path.parent.mkdir(parents=True)
    cache.manifest_path.write_text("{}", encoding="utf-8")

    def fail(*, root_dir, target_path):
        raise MeminitError(ErrorCode.PATH_ESCAPE, "unsafe")

    monkeypatch.setattr(
        "meminit.core.services.index_cache.ensure_safe_write_path",
        fail,
    )

    with pytest.raises(MeminitError) as exc_info:
        cache.clear()

    assert exc_info.value.code is ErrorCode.PATH_ESCAPE


def test_cache_key_disambiguates_sanitized_collisions():
    assert _cache_key("foo/bar") != _cache_key("foo_bar")


@pytest.mark.parametrize("changed_key", ["config_sha256", "schema_sha256", "meminit_version"])
def test_s09_s10_s11_index_cache_global_context_change_forces_full_rebuild(
    tmp_path,
    changed_key,
):
    doc_path = _write_cache_doc(tmp_path)
    cache = IndexCache(tmp_path)
    base_context = {
        "config_sha256": "config-a",
        "schema_sha256": "schema-a",
        "meminit_version": "1.0.0",
    }
    _seed_cache(cache, doc_path, base_context)

    changed_context = {**base_context, changed_key: "changed"}
    plan = cache.build_plan(
        doc_paths=[doc_path],
        context=changed_context,
        use_cache=True,
    )

    assert plan.summary() == {
        "mode": "full",
        "added": 1,
        "changed": 0,
        "removed": 0,
        "unchanged": 0,
    }


def test_s13_index_cache_missing_manifest_degrades_to_full_rebuild(tmp_path):
    doc_path = _write_cache_doc(tmp_path)
    cache = IndexCache(tmp_path)
    context = {
        "config_sha256": "config-a",
        "schema_sha256": "schema-a",
        "meminit_version": "1.0.0",
    }
    _seed_cache(cache, doc_path, context)
    cache.manifest_path.unlink()

    plan = cache.build_plan(doc_paths=[doc_path], context=context, use_cache=True)

    assert plan.manifest_warning is None
    assert plan.summary() == {
        "mode": "full",
        "added": 1,
        "changed": 0,
        "removed": 0,
        "unchanged": 0,
    }


def test_s14_index_cache_concurrent_lock_reports_cache_lock_held(tmp_path):
    cache = IndexCache(tmp_path)

    with cache.acquire_lock():
        with pytest.raises(MeminitError) as exc_info:
            with cache.acquire_lock():
                pass

    assert exc_info.value.code is ErrorCode.CACHE_LOCK_HELD
