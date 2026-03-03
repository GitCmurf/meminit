from pathlib import Path

import yaml


def _split_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise AssertionError("Expected YAML frontmatter starting with ---")
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        raise AssertionError("Expected closing --- for YAML frontmatter")
    meta = yaml.safe_load("\n".join(lines[1:end])) or {}
    body = "\n".join(lines[end + 1 :])
    return meta, body


def test_codex_skill_manifest_exists_and_has_required_fields():
    skill_path = Path(".agents/skills/meminit-docops/SKILL.md")
    assert skill_path.exists()

    meta, body = _split_frontmatter(skill_path.read_text(encoding="utf-8"))
    assert meta.get("name") == "meminit-docops"
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    # Guardrails from the Codex Skills spec: short, single-line fields.
    assert "\n" not in meta["name"]
    assert "\n" not in meta["description"]
    assert len(meta["name"]) <= 100
    assert len(meta["description"]) <= 500
    assert set(meta.keys()) == {"name", "description"}
    assert "meminit scan" in body
    assert "meminit check" in body
    assert "meminit scan --plan" in body
    assert "migrate-ids --no-dry-run" in body
    assert "meminit adr new" in body
    assert "## How to Use" in body
    assert '"1.0" for others' not in body
