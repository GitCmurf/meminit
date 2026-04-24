"""Tests for state_derived module — derived field computation and validation."""

from datetime import datetime, timezone

import pytest

from meminit.core.services.project_state import (
    DEFAULT_PRIORITY,
    ProjectState,
    ProjectStateEntry,
)
from meminit.core.services.sanitization import MAX_ASSIGNEE_LENGTH, MAX_NOTES_LENGTH
from meminit.core.services.state_derived import (
    DerivedEntry,
    ValidationIssue,
    check_dependency_cycle,
    check_status_conflicts,
    compute_derived_fields,
    next_selection_key,
    validate_planning_fields,
)


def _entry(
    doc_id: str = "TEST-ADR-001",
    impl_state: str = "Not Started",
    priority: str | None = None,
    depends_on: tuple = (),
    blocked_by: tuple = (),
    assignee: str | None = None,
    next_action: str | None = None,
    updated_by: str = "test",
) -> ProjectStateEntry:
    return ProjectStateEntry(
        document_id=doc_id,
        impl_state=impl_state,
        updated=datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc),
        updated_by=updated_by,
        priority=priority,
        depends_on=depends_on,
        blocked_by=blocked_by,
        assignee=assignee,
        next_action=next_action,
    )


def _state(*entries: ProjectStateEntry) -> ProjectState:
    s = ProjectState()
    for e in entries:
        s.set_entry(e)
    return s


_TS = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# compute_derived_fields
# ---------------------------------------------------------------------------

class TestComputeDerivedFields:
    def test_ready_when_not_started_and_no_deps(self):
        state = _state(_entry("A", "Not Started"))
        derived = compute_derived_fields(state, {"A"})
        assert derived["A"].ready is True
        assert derived["A"].open_blockers == ()
        assert derived["A"].unblocks == ()

    def test_not_ready_when_in_progress(self):
        state = _state(_entry("A", "In Progress"))
        derived = compute_derived_fields(state, {"A"})
        assert derived["A"].ready is False

    def test_ready_when_dep_is_done(self):
        state = _state(
            _entry("A", "Not Started", depends_on=("B",)),
            _entry("B", "Done"),
        )
        derived = compute_derived_fields(state, {"A", "B"})
        assert derived["A"].ready is True
        assert derived["A"].open_blockers == ()

    def test_not_ready_when_dep_is_in_progress(self):
        state = _state(
            _entry("A", "Not Started", depends_on=("B",)),
            _entry("B", "In Progress"),
        )
        derived = compute_derived_fields(state, {"A", "B"})
        assert derived["A"].ready is False
        assert derived["A"].open_blockers == ("B",)

    def test_not_ready_when_dep_unknown(self):
        state = _state(_entry("A", "Not Started", depends_on=("UNKNOWN-001",)))
        derived = compute_derived_fields(state, {"A"})
        assert derived["A"].ready is False
        assert derived["A"].open_blockers == ("UNKNOWN-001",)

    def test_blocked_by_same_semantics(self):
        state = _state(
            _entry("A", "Not Started", blocked_by=("B",)),
            _entry("B", "Blocked"),
        )
        derived = compute_derived_fields(state, {"A", "B"})
        assert derived["A"].ready is False
        assert derived["A"].open_blockers == ("B",)

    def test_unblocks_reverse_lookup(self):
        state = _state(
            _entry("A", "Not Started"),
            _entry("B", "Not Started", depends_on=("A",)),
            _entry("C", "Not Started", blocked_by=("A",)),
        )
        derived = compute_derived_fields(state, {"A", "B", "C"})
        assert derived["A"].unblocks == ("B", "C")

    def test_determinism(self):
        state = _state(
            _entry("A", "Not Started", depends_on=("B",)),
            _entry("B", "Done"),
        )
        known = {"A", "B"}
        d1 = compute_derived_fields(state, known)
        d2 = compute_derived_fields(state, known)
        assert d1 == d2

    def test_open_blockers_sorted(self):
        state = _state(
            _entry("A", "Not Started", depends_on=("Z-001",), blocked_by=("M-001",)),
        )
        derived = compute_derived_fields(state, {"A"})
        assert derived["A"].open_blockers == ("M-001", "Z-001")

    def test_ready_false_when_done(self):
        state = _state(_entry("A", "Done"))
        derived = compute_derived_fields(state, {"A"})
        assert derived["A"].ready is False


# ---------------------------------------------------------------------------
# validate_planning_fields
# ---------------------------------------------------------------------------

class TestValidatePlanningFields:
    def test_valid_entry_no_issues(self):
        entry = _entry(priority="P1", depends_on=("OTHER-ADR-001",))
        issues = validate_planning_fields(entry, {"TEST-ADR-001", "OTHER-ADR-001"}, {})
        assert [i for i in issues if i.severity == "fatal"] == []

    def test_invalid_priority(self):
        entry = _entry(priority="P9")
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_INVALID_PRIORITY" and i.severity == "fatal" for i in issues)

    def test_invalid_dependency_id_format(self):
        entry = _entry(depends_on=("not-a-valid-id",))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_INVALID_DEPENDENCY_ID" for i in issues)

    def test_undefined_dependency_warning(self):
        entry = _entry(depends_on=("MISSING-ADR-001",))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_UNDEFINED_DEPENDENCY" and i.severity == "warning" for i in issues)

    def test_self_dependency(self):
        entry = _entry(depends_on=("TEST-ADR-001",))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_SELF_DEPENDENCY" for i in issues)

    def test_assignee_too_long(self):
        entry = _entry(assignee="x" * (MAX_ASSIGNEE_LENGTH + 1))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_FIELD_TOO_LONG" and "assignee" in i.message for i in issues)

    def test_next_action_too_long(self):
        entry = _entry(next_action="y" * (MAX_NOTES_LENGTH + 1))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_FIELD_TOO_LONG" and "next_action" in i.message for i in issues)

    def test_blocked_by_same_validations(self):
        entry = _entry(blocked_by=("not-valid",))
        issues = validate_planning_fields(entry, {"TEST-ADR-001"}, {})
        assert any(i.code == "STATE_INVALID_DEPENDENCY_ID" for i in issues)


# ---------------------------------------------------------------------------
# check_dependency_cycle
# ---------------------------------------------------------------------------

class TestCheckDependencyCycle:
    def test_no_cycle(self):
        entries = {
            "A": _entry("A", depends_on=("B",)),
            "B": _entry("B"),
        }
        issues = check_dependency_cycle(entries)
        assert issues == []

    def test_simple_cycle(self):
        entries = {
            "A": _entry("A", depends_on=("B",)),
            "B": _entry("B", depends_on=("A",)),
        }
        issues = check_dependency_cycle(entries)
        assert any(i.code == "STATE_DEPENDENCY_CYCLE" for i in issues)

    def test_three_node_cycle(self):
        entries = {
            "A": _entry("A", depends_on=("B",)),
            "B": _entry("B", depends_on=("C",)),
            "C": _entry("C", depends_on=("A",)),
        }
        issues = check_dependency_cycle(entries)
        assert any(i.code == "STATE_DEPENDENCY_CYCLE" for i in issues)

    def test_self_cycle_via_depends_on(self):
        entries = {"A": _entry("A", depends_on=("A",))}
        issues = check_dependency_cycle(entries)
        assert any(i.code == "STATE_DEPENDENCY_CYCLE" for i in issues)

    def test_cycle_involves_blocked_by(self):
        entries = {
            "A": _entry("A", blocked_by=("B",)),
            "B": _entry("B", blocked_by=("A",)),
        }
        issues = check_dependency_cycle(entries)
        assert any(i.code == "STATE_DEPENDENCY_CYCLE" for i in issues)


# ---------------------------------------------------------------------------
# check_status_conflicts
# ---------------------------------------------------------------------------

class TestCheckStatusConflicts:
    def test_no_conflict(self):
        entries = {
            "A": _entry("A", "Done", depends_on=("B",)),
            "B": _entry("B", "Done"),
        }
        issues = check_status_conflicts(entries)
        assert issues == []

    def test_conflict_when_done_depends_on_in_progress(self):
        entries = {
            "A": _entry("A", "Done", depends_on=("B",)),
            "B": _entry("B", "In Progress"),
        }
        issues = check_status_conflicts(entries)
        assert any(i.code == "STATE_DEPENDENCY_STATUS_CONFLICT" for i in issues)
        assert issues[0].severity == "advisory"

    def test_not_done_no_conflict(self):
        entries = {
            "A": _entry("A", "In Progress", depends_on=("B",)),
            "B": _entry("B", "In Progress"),
        }
        issues = check_status_conflicts(entries)
        assert issues == []


# ---------------------------------------------------------------------------
# next_selection_key
# ---------------------------------------------------------------------------

class TestNextSelectionKey:
    def test_priority_ordering(self):
        e_p0 = _entry("A", priority="P0")
        e_p1 = _entry("B", priority="P1")
        d_a = DerivedEntry("A", True, (), ())
        d_b = DerivedEntry("B", True, (), ())
        assert next_selection_key(e_p0, d_a) < next_selection_key(e_p1, d_b)

    def test_unblocks_breaks_priority_tie(self):
        e1 = _entry("A", priority="P1")
        e2 = _entry("B", priority="P1")
        d_a = DerivedEntry("A", True, (), ("C", "D"))
        d_b = DerivedEntry("B", True, (), ("C",))
        assert next_selection_key(e1, d_a) < next_selection_key(e2, d_b)

    def test_updated_breaks_unblocks_tie(self):
        e_old = ProjectStateEntry("A", "Not Started", _TS, "test", priority="P2")
        e_new = ProjectStateEntry(
            "B", "Not Started",
            datetime(2026, 4, 22, 12, 0, 0, tzinfo=timezone.utc),
            "test", priority="P2",
        )
        d_a = DerivedEntry("A", True, (), ())
        d_b = DerivedEntry("B", True, (), ())
        assert next_selection_key(e_old, d_a) < next_selection_key(e_new, d_b)

    def test_doc_id_is_final_tiebreaker(self):
        e1 = ProjectStateEntry("AAA-001", "Not Started", _TS, "test", priority="P2")
        e2 = ProjectStateEntry("BBB-001", "Not Started", _TS, "test", priority="P2")
        d_a = DerivedEntry("AAA-001", True, (), ())
        d_b = DerivedEntry("BBB-001", True, (), ())
        assert next_selection_key(e1, d_a) < next_selection_key(e2, d_b)
