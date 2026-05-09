from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _table_rows(text: str, heading: str) -> dict[str, str]:
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.strip() == heading)
    except StopIteration as exc:
        raise AssertionError(f"Missing heading: {heading}") from exc

    table_lines: list[str] = []
    for line in lines[start + 1 :]:
        if not line.startswith("|"):
            if table_lines:
                break
            continue
        table_lines.append(line)

    if len(table_lines) < 3:
        raise AssertionError(f"Heading {heading!r} does not contain a table")

    rows: dict[str, str] = {}
    for line in table_lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) >= 2:
            rows[cells[0].strip("`")] = cells[1]
    return rows


def test_prd_state_error_prefix_rule_documents_per_row_severity():
    content = (ROOT / "docs/10-prd/prd-007-project-state-dashboard.md").read_text(
        encoding="utf-8"
    )
    normalized = " ".join(content.split())

    assert "Severity is listed per row." in normalized
    assert (
        "The fatal rows in this table are `STATE_YAML_MALFORMED`, "
        "`STATE_SCHEMA_VIOLATION`, and `STATE_INVALID_FILTER_VALUE`"
        in normalized
    )
    assert "STATE_INVALID_PRIORITY" in normalized
    assert "STATE_DEPENDENCY_STATUS_CONFLICT" in normalized
    assert "the `W_` rows are warnings" in normalized
    assert "Codes prefixed `STATE_` are fatal errors" not in normalized


def test_tech_debt_register_status_model_and_td002_are_aligned():
    content = (ROOT / "TECH_DEBT.md").read_text(encoding="utf-8")

    status_rows = _table_rows(content, "## Status Model")
    assert "Narrowed" in status_rows
    assert status_rows["Narrowed"] == "Accepted debt whose scope has been reduced and re-baselined."

    td002_rows = _table_rows(
        content,
        "### TD-002: Streaming producers still materialize use-case results before emitting",
    )
    assert td002_rows["Status"] == "Narrowed"
    assert "stream_events.py" in td002_rows["Evidence"]
    assert "CoreStreamingProducer" in td002_rows["Evidence"]
    assert "CallableStreamingProducer" in td002_rows["Narrowing evidence"]
    assert "tests/cli/test_stream_emitter.py" in td002_rows["Narrowing evidence"]
    assert "Shared iterator plumbing" in td002_rows["Definition of done"]
