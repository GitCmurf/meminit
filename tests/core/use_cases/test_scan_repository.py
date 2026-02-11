from meminit.core.use_cases.scan_repository import ScanRepositoryUseCase


def test_scan_suggests_type_directory_for_adr(tmp_path):
    docs_root = tmp_path / "docs"
    (docs_root / "adrs").mkdir(parents=True)
    (docs_root / "adrs" / "adr-001-test.md").write_text("# ADR test\n")

    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.docs_root == "docs"
    assert report.suggested_type_directories.get("ADR") == "adrs"
    assert report.markdown_count == 1


def test_scan_reports_missing_docs_root(tmp_path):
    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.docs_root is None
    assert report.markdown_count == 0
    assert report.notes


def test_scan_reports_ambiguous_type_directories(tmp_path):
    docs_root = tmp_path / "docs"
    (docs_root / "adrs").mkdir(parents=True)
    (docs_root / "decisions").mkdir(parents=True)
    (docs_root / "adrs" / "adr-001.md").write_text("# ADR 1\n", encoding="utf-8")
    (docs_root / "decisions" / "decision-001.md").write_text("# Decision 1\n", encoding="utf-8")

    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert "ADR" in report.ambiguous_types
    assert sorted(report.ambiguous_types["ADR"]) == ["adrs", "decisions"]


def test_scan_uses_configured_type_directories(tmp_path):
    (tmp_path / "docs" / "decisions").mkdir(parents=True)
    (tmp_path / "docops.config.yaml").write_text(
        "type_directories:\n  ADR: decisions\n",
        encoding="utf-8",
    )

    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert "ADR" not in report.suggested_type_directories
    assert "ADR" not in report.ambiguous_types


def test_scan_suggests_namespaces_for_packages_docs(tmp_path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "packages" / "phyla" / "docs").mkdir(parents=True)
    (tmp_path / "packages" / "phyla" / "docs" / "note.md").write_text("# Note\n", encoding="utf-8")

    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()

    assert report.suggested_namespaces
    assert any(ns["docs_root"] == "packages/phyla/docs" for ns in report.suggested_namespaces)


def test_scan_does_not_suggest_configured_namespace(tmp_path):
    (tmp_path / "docs").mkdir(parents=True)
    (tmp_path / "packages" / "phyla" / "docs").mkdir(parents=True)
    (tmp_path / "packages" / "phyla" / "docs" / "note.md").write_text("# Note\n", encoding="utf-8")
    (tmp_path / "docops.config.yaml").write_text(
        "namespaces:\n  - name: phyla\n    docs_root: packages/phyla/docs\n    repo_prefix: PHYLA\n",
        encoding="utf-8",
    )

    use_case = ScanRepositoryUseCase(str(tmp_path))
    report = use_case.execute()
    assert not any(ns["docs_root"] == "packages/phyla/docs" for ns in report.suggested_namespaces)


def test_scan_reports_configured_namespaces_and_overlaps(tmp_path):
    # Configure two namespaces, one nested inside the other (overlap).
    (tmp_path / "docs" / "00-governance" / "org").mkdir(parents=True, exist_ok=True)
    (tmp_path / "docs" / "readme.md").write_text("# Root doc\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "org" / "org-gov-001.md").write_text(
        "# ORG doc\n", encoding="utf-8"
    )

    (tmp_path / "docops.config.yaml").write_text(
        "project_name: Example\n"
        "repo_prefix: EXAMPLE\n"
        "docops_version: '2.0'\n"
        "namespaces:\n"
        "  - name: repo\n"
        "    repo_prefix: EXAMPLE\n"
        "    docs_root: docs\n"
        "  - name: org\n"
        "    repo_prefix: ORG\n"
        "    docs_root: docs/00-governance/org\n",
        encoding="utf-8",
    )

    report = ScanRepositoryUseCase(str(tmp_path)).execute()

    assert report.configured_namespaces
    assert any(ns.get("namespace") == "repo" for ns in report.configured_namespaces)
    assert any(ns.get("namespace") == "org" for ns in report.configured_namespaces)
    assert report.overlapping_namespaces
    assert any(
        o.get("parent_docs_root") == "docs" and o.get("child_docs_root") == "docs/00-governance/org"
        for o in report.overlapping_namespaces
    )
