from __future__ import annotations

import json

import pytest

from meminit.core.services.error_codes import ErrorCode, MeminitError
from meminit.core.services.index_cache import IndexCache


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
