from unittest.mock import patch

from meminit.core.use_cases.context_repository import ContextRepositoryUseCase


def _write_config(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "\n".join(
            [
                "project_name: Test",
                "repo_prefix: TST",
                "docops_version: '2.0'",
                "default_owner: TeamA",
                "namespaces:",
                "  - name: default",
                "    docs_root: docs",
                "    repo_prefix: TST",
                "    docops_version: '2.0'",
                "  - name: nested",
                "    docs_root: docs/nested",
                "    repo_prefix: NST",
                "    docops_version: '2.0'",
                "  - name: other",
                "    docs_root: docs-other",
                "    repo_prefix: OTH",
                "    docops_version: '2.0'",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_context_repository_execute_shallow(tmp_path):
    _write_config(tmp_path)
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "nested" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs-other" / "00-governance").mkdir(parents=True)

    use_case = ContextRepositoryUseCase(root_dir=tmp_path)
    result = use_case.execute(deep=False)

    assert "allowed_types" in result.data
    assert "ADR" in result.data["allowed_types"]
    assert result.data["config_path"] == "docops.config.yaml"
    assert result.data["default_owner"] == "TeamA"
    assert result.data["project_name"] == "Test"

    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["docs_root"] == "docs"
    assert namespaces[1]["docs_root"] == "docs/nested"
    assert namespaces[2]["docs_root"] == "docs-other"
    assert "document_count" not in namespaces[0]

    assert result.warnings == []


def test_context_repository_execute_deep_counts_documents(tmp_path):
    _write_config(tmp_path)
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "templates").mkdir(parents=True)
    (tmp_path / "docs" / "nested" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs-other" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "b.md").write_text("# B\n", encoding="utf-8")
    (tmp_path / "docs" / "WIP-notes.md").write_text("# WIP\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "templates" / "tmpl.md").write_text(
        "# Template\n", encoding="utf-8"
    )
    (tmp_path / "docs-other" / "00-governance" / "c.md").write_text("# C\n", encoding="utf-8")
    (tmp_path / "docs" / "nested" / "00-governance" / "d.md").write_text(
        "# D\n", encoding="utf-8"
    )

    use_case = ContextRepositoryUseCase(root_dir=tmp_path)
    result = use_case.execute(deep=True)

    assert result.data["deep_incomplete"] is False
    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["document_count"] == 2
    assert namespaces[1]["document_count"] == 1
    assert namespaces[2]["document_count"] == 1
    assert result.warnings == []


def test_context_repository_execute_deep_budget_exhaustion(tmp_path):
    _write_config(tmp_path)
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs-other" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "docs-other" / "00-governance" / "c.md").write_text("# C\n", encoding="utf-8")

    use_case = ContextRepositoryUseCase(root_dir=tmp_path)

    def monotonic_values(values):
        it = iter(values)
        last = values[-1]

        def _fn():
            nonlocal last
            last = next(it, last)
            return last

        return _fn

    # Allow first namespace to complete, then hit the budget before the next.
    with patch(
        "meminit.core.use_cases.context_repository.time.monotonic",
        new=monotonic_values([0.0, 0.0, 0.0, 0.0, 2.1]),
    ):
        result = use_case.execute(deep=True)

    assert result.data["deep_incomplete"] is True
    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["document_count"] == 1
    assert namespaces[1]["document_count"] is None
    assert namespaces[2]["document_count"] is None
    assert result.warnings == [
        {
            "code": "DEEP_BUDGET_EXCEEDED",
            "message": (
                "Deep scan performance budget (2s) exceeded; "
                "some namespace counts are incomplete."
            ),
            "path": "docops.config.yaml",
        }
    ]


def test_context_repository_execute_deep_budget_exceeded_mid_count(tmp_path):
    _write_config(tmp_path)
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "nested" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs-other" / "00-governance").mkdir(parents=True)
    # Multiple files so the counter loop runs more than once.
    (tmp_path / "docs" / "00-governance" / "a.md").write_text("# A\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "b.md").write_text("# B\n", encoding="utf-8")
    (tmp_path / "docs-other" / "00-governance" / "c.md").write_text("# C\n", encoding="utf-8")

    use_case = ContextRepositoryUseCase(root_dir=tmp_path)

    def monotonic_after(calls_before_deadline: int):
        calls = 0

        def _fn():
            nonlocal calls
            calls += 1
            return 0.0 if calls <= calls_before_deadline else 2.1

        return _fn

    # Exceed budget during the first namespace count.
    with patch(
        "meminit.core.use_cases.context_repository.time.monotonic",
        new=monotonic_after(2),
    ):
        result = use_case.execute(deep=True)

    assert result.data["deep_incomplete"] is True
    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["document_count"] is None
    assert namespaces[1]["document_count"] is None
    assert namespaces[2]["document_count"] is None
    assert result.warnings and result.warnings[0]["code"] == "DEEP_BUDGET_EXCEEDED"
