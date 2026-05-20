from unittest.mock import patch

from meminit.core.use_cases.context_repository import (
    ContextRepositoryUseCase,
    _resolve_default_owner,
)


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
    (tmp_path / "docs" / "00-governance" / "a.md").write_text(
        "---\n"
        "document_id: DOC-A\n"
        "type: ADR\n"
        "title: A\n"
        "---\n\n# A\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "00-governance" / "b.md").write_text(
        "---\n"
        "document_id: DOC-B\n"
        "type: ADR\n"
        "title: B\n"
        "---\n\n# B\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "WIP-notes.md").write_text("# WIP\n", encoding="utf-8")
    (tmp_path / "docs" / "00-governance" / "templates" / "tmpl.md").write_text(
        "# Template\n", encoding="utf-8"
    )
    (tmp_path / "docs-other" / "00-governance" / "c.md").write_text(
        "---\n"
        "document_id: DOC-C\n"
        "type: ADR\n"
        "title: C\n"
        "---\n\n# C\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "nested" / "00-governance" / "d.md").write_text(
        "---\n"
        "document_id: DOC-D\n"
        "type: ADR\n"
        "title: D\n"
        "---\n\n# D\n",
        encoding="utf-8",
    )

    use_case = ContextRepositoryUseCase(root_dir=tmp_path)
    result = use_case.execute(deep=True)

    assert result.data["deep_incomplete"] is False
    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["document_count"] == 2
    assert namespaces[1]["document_count"] == 1
    assert namespaces[2]["document_count"] == 1
    assert result.documents == [
        {
            "document_id": "DOC-A",
            "namespace": "default",
            "path": "docs/00-governance/a.md",
            "title": "A",
            "type": "ADR",
        },
        {
            "document_id": "DOC-B",
            "namespace": "default",
            "path": "docs/00-governance/b.md",
            "title": "B",
            "type": "ADR",
        },
        {
            "document_id": "DOC-C",
            "namespace": "other",
            "path": "docs-other/00-governance/c.md",
            "title": "C",
            "type": "ADR",
        },
        {
            "document_id": "DOC-D",
            "namespace": "nested",
            "path": "docs/nested/00-governance/d.md",
            "title": "D",
            "type": "ADR",
        },
    ]
    assert result.warnings == []


def test_context_repository_execute_deep_uses_document_id_for_same_root_namespaces(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "\n".join(
            [
                "project_name: Test",
                "repo_prefix: TST",
                "docops_version: '2.0'",
                "namespaces:",
                "  - name: root",
                "    docs_root: docs",
                "    repo_prefix: TEST",
                "  - name: phyla",
                "    docs_root: docs",
                "    repo_prefix: PHYLA",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "00-governance" / "root.md").write_text(
        "---\n"
        "document_id: TEST-ADR-001\n"
        "type: ADR\n"
        "title: Root\n"
        "---\n\n# Root\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "00-governance" / "phyla.md").write_text(
        "---\n"
        "document_id: PHYLA-ADR-001\n"
        "type: ADR\n"
        "title: Phyla\n"
        "---\n\n# Phyla\n",
        encoding="utf-8",
    )

    result = ContextRepositoryUseCase(root_dir=tmp_path).execute(deep=True)

    namespaces = {ns["name"]: ns["document_count"] for ns in result.data["namespaces"]}
    assert namespaces == {"root": 1, "phyla": 1}
    assert result.documents == [
        {
            "document_id": "PHYLA-ADR-001",
            "namespace": "phyla",
            "path": "docs/00-governance/phyla.md",
            "title": "Phyla",
            "type": "ADR",
        },
        {
            "document_id": "TEST-ADR-001",
            "namespace": "root",
            "path": "docs/00-governance/root.md",
            "title": "Root",
            "type": "ADR",
        },
    ]


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
        new=monotonic_values([0.0, 0.0, 0.0, 0.0, 10.1]),
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
                "Deep scan performance budget (10s) exceeded; "
                "some namespace counts are incomplete."
            ),
            "path": ".",
        }
    ]


def test_resolve_default_owner_prefers_namespace_key():
    config = {
        "default_owner": "Fallback",
        "namespaces": [
            {"namespace": "default", "default_owner": "TeamN"},
        ],
    }
    assert _resolve_default_owner(config, "default") == "TeamN"


def test_context_repository_execute_deep_budget_exceeded_mid_count(tmp_path):
    _write_config(tmp_path)
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs" / "nested" / "00-governance").mkdir(parents=True)
    (tmp_path / "docs-other" / "00-governance").mkdir(parents=True)
    use_case = ContextRepositoryUseCase(root_dir=tmp_path)
    partial_documents = [
        {
            "document_id": "DOC-A",
            "namespace": "default",
            "path": "docs/00-governance/a.md",
            "title": "A",
            "type": "ADR",
        }
    ]

    def fake_count(layout, ns, *, deadline=None):
        if ns.namespace == "default":
            return None, partial_documents
        return 0, []

    with patch(
        "meminit.core.use_cases.context_repository._count_governed_markdown",
        side_effect=fake_count,
    ):
        result = use_case.execute(deep=True)

    assert result.data["deep_incomplete"] is True
    namespaces = result.data["namespaces"]
    assert [ns["name"] for ns in namespaces] == ["default", "nested", "other"]
    assert namespaces[0]["document_count"] is None
    assert namespaces[1]["document_count"] is None
    assert namespaces[2]["document_count"] is None
    assert result.documents == partial_documents
    assert result.warnings and result.warnings[0]["code"] == "DEEP_BUDGET_EXCEEDED"


def test_context_repository_default_owner_none_when_missing(tmp_path):
    (tmp_path / "docops.config.yaml").write_text(
        "\n".join(
            [
                "project_name: Test",
                "repo_prefix: TST",
                "docops_version: '2.0'",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "docs" / "00-governance").mkdir(parents=True)
    use_case = ContextRepositoryUseCase(root_dir=tmp_path)
    result = use_case.execute(deep=False)
    assert result.data["default_owner"] is None
