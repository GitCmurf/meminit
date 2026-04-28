from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "codex_review_remediation_loop.py"
SPEC = importlib.util.spec_from_file_location("codex_review_remediation_loop", SCRIPT_PATH)
assert SPEC is not None
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_detect_review_status_prefers_explicit_status_line():
    assert MODULE.detect_review_status("Looks good\nREVIEW_STATUS: clear\n") == "clear"
    assert MODULE.detect_review_status("One blocker\nREVIEW_STATUS: findings\n") == "findings"


def test_detect_review_status_treats_ambiguous_output_as_unknown():
    assert MODULE.detect_review_status("This review has a detailed discussion.") == "unknown"


def test_detect_review_status_accepts_exact_clear_review_lines():
    assert MODULE.detect_review_status("No findings.\n") == "clear"
    assert MODULE.detect_review_status("summary\nNo actionable findings\n") == "clear"


def test_detect_review_status_recognizes_codex_review_findings():
    output = """The patch has a bug.

Full review comments:

- [P2] Count filtered summaries after filtering — src/example.py:10-12
  This reports misleading data.
"""
    assert MODULE.detect_review_status(output) == "findings"


def test_extract_finding_summaries_limits_codex_findings():
    output = """Full review comments:

- [P1] First bug — src/a.py:1
  Detail.
- [P2] Second bug — src/b.py:2
- [P3] Third bug — src/c.py:3
"""
    assert MODULE.extract_finding_summaries(output, limit=2) == [
        "[P1] First bug — src/a.py:1",
        "[P2] Second bug — src/b.py:2",
    ]


def test_review_model_is_top_level_codex_option(tmp_path):
    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        model="gpt-test",
    )

    command = MODULE.build_review_command(config)

    assert command[:5] == ["codex", "--model", "gpt-test", "review", "--base"]
    assert command == ["codex", "--model", "gpt-test", "review", "--base", "main"]


def test_remediation_command_uses_deterministic_output_options(tmp_path):
    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        exec_json=True,
    )

    command = MODULE.build_remediation_command(config, tmp_path / "last-message.txt")

    assert "--color" in command
    assert command[command.index("--color") + 1] == "never"
    assert "--json" in command
    assert "--output-last-message" in command
    assert command[-1] == "-"


def test_loop_stops_after_review_reports_clear(tmp_path):
    calls = []
    review_outputs = iter(
        [
            "Finding: add regression coverage.\nREVIEW_STATUS: findings\n",
            "No actionable findings.\nREVIEW_STATUS: clear\n",
        ]
    )

    def runner(args, cwd, input_text=None):
        calls.append((list(args), input_text))
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        return MODULE.CommandResult(list(args), 0, stdout="remediated\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=2,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        check_commands=("python -m pytest tests/unit",),
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["final_status"] == "clear"
    assert summary["stopped_reason"] == "review_clear"
    assert [call[0][1] for call in calls] == ["review", "exec", "-m", "review"]
    assert calls[0][1] is None
    assert (tmp_path / "artifacts" / "summary.json").exists()


def test_loop_caps_remediation_passes_and_runs_final_review(tmp_path):
    calls = []

    def runner(args, cwd, input_text=None):
        calls.append((list(args), input_text))
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout="Still failing.\nREVIEW_STATUS: findings\n")
        return MODULE.CommandResult(list(args), 0, stdout="attempted remediation\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=2,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["final_status"] == "findings"
    assert summary["stopped_reason"] == "max_iterations_reached"
    assert [call[0][1] for call in calls] == ["review", "exec", "review", "exec", "review"]
    assert len(summary["iterations"]) == 2


def test_loop_continues_after_check_failure_and_feeds_output_into_next_pass(tmp_path):
    """A failing --check must not abort the loop; its output is fed into the next remediation."""
    calls: list[tuple[list[str], str | None]] = []
    # review-1 → findings; review-2 → findings (triggers iter-2 exec); review-final → clear
    review_outputs = iter([
        "Missing coverage.\nREVIEW_STATUS: findings\n",
        "Still some gaps.\nREVIEW_STATUS: findings\n",
        "All good.\nREVIEW_STATUS: clear\n",
    ])
    # check fails after iter-1, passes after iter-2
    check_outputs = iter([(1, "1 FAILED\n"), (0, "1 passed\n")])

    def runner(args, cwd, input_text=None):
        calls.append((list(args), input_text))
        if args[0] == "codex" and args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        if args[0] == "pytest":
            rc, out = next(check_outputs)
            return MODULE.CommandResult(list(args), rc, stdout=out)
        return MODULE.CommandResult(list(args), 0, stdout="remediated\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=2,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        check_commands=("pytest tests/",),
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["final_status"] == "clear"

    # Both remediation passes ran (loop was not aborted by the check failure)
    exec_calls = [c for c in calls if c[0][0] == "codex" and c[0][1] == "exec"]
    assert len(exec_calls) == 2, f"expected 2 exec calls, got {len(exec_calls)}"

    # The second remediation prompt must include the check-failure output from iter-1
    second_prompt = exec_calls[1][1]
    assert second_prompt is not None and "1 FAILED" in second_prompt


def test_pending_check_failure_blocks_early_clear_status(tmp_path):
    """A clear review cannot finish the loop while a previous --check failure is pending."""
    calls: list[tuple[list[str], str | None]] = []
    review_outputs = iter([
        "Missing coverage.\nREVIEW_STATUS: findings\n",
        "All good.\nREVIEW_STATUS: clear\n",
        "All good.\nREVIEW_STATUS: clear\n",
    ])
    check_outputs = iter([(1, "1 FAILED\n"), (1, "still failing\n")])

    def runner(args, cwd, input_text=None):
        calls.append((list(args), input_text))
        if args[0] == "codex" and args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        if args[0] == "pytest":
            rc, out = next(check_outputs)
            return MODULE.CommandResult(list(args), rc, stdout=out)
        return MODULE.CommandResult(list(args), 0, stdout="remediated\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=2,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        check_commands=("pytest tests/",),
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["final_status"] == "findings"
    assert summary["pending_check_failures"] is True
    assert summary["stopped_reason"] == "max_iterations_reached_with_check_failures"

    exec_calls = [c for c in calls if c[0][0] == "codex" and c[0][1] == "exec"]
    assert len(exec_calls) == 2
    assert exec_calls[1][1] is not None and "1 FAILED" in exec_calls[1][1]


def test_skip_final_review_reports_unknown_status(tmp_path):
    """With --skip-final-review the loop must not report a stale pre-remediation status."""
    def runner(args, cwd, input_text=None):
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout="Issues found.\nREVIEW_STATUS: findings\n")
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        final_review=False,
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["final_status"] == "unknown", (
        "status after last remediation is unknowable without a follow-up review"
    )
    assert summary["stopped_reason"] == "max_iterations_reached"


def test_final_check_failure_prevents_clear_status(tmp_path):
    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        check_commands=("pytest tests/",),
    )

    review_outputs = iter(
        [
            "Actionable finding.\nREVIEW_STATUS: findings\n",
            "All good.\nREVIEW_STATUS: clear\n",
        ]
    )

    def sequenced_runner(args, cwd, input_text=None):
        if args[0] == "codex" and args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        if args[0] == "pytest":
            return MODULE.CommandResult(list(args), 1, stdout="1 FAILED\n")
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    summary = MODULE.run_loop(config, sequenced_runner)

    assert summary["final_status"] == "findings"
    assert summary["pending_check_failures"] is True
    assert summary["stopped_reason"] == "max_iterations_reached_with_check_failures"


def test_detect_review_status_requires_explicit_status_line():
    """Fuzzy patterns must not flip ambiguous output to clear."""
    assert MODULE.detect_review_status("no findings about style, but several about logic") == "unknown"
    assert MODULE.detect_review_status("review is clear of syntax errors but not semantic") == "unknown"
    assert MODULE.detect_review_status("") == "unknown"


def test_review_failure_detection_allows_nonzero_findings_without_stderr():
    assert (
        MODULE.review_failed_to_run(
            MODULE.CommandResult(["codex", "review"], -9, stdout="", stderr="")
        )
        is True
    )
    assert (
        MODULE.review_failed_to_run(
            MODULE.CommandResult(["codex", "review"], 1, stdout="Finding\n", stderr="")
        )
        is False
    )
    assert (
        MODULE.review_failed_to_run(
            MODULE.CommandResult(["codex", "review"], 1, stdout="", stderr="Error: thread/start failed")
        )
        is True
    )
    assert (
        MODULE.review_failed_to_run(
            MODULE.CommandResult(["codex", "review"], 2, stdout="", stderr="error: bad args")
        )
        is True
    )


def test_actionable_review_output_drops_verbose_stderr_transcript():
    output = "Full review comments:\n\n- [P1] Fix the bug\n\n[stderr]\n" + ("diff --git a/x b/x\n" * 100)

    assert MODULE.actionable_review_output(output) == "Full review comments:\n\n- [P1] Fix the bug"


def test_trim_for_prompt_caps_large_review_text():
    text = "a" * 100 + "MIDDLE" + "z" * 100

    trimmed = MODULE.trim_for_prompt(text, 80)

    assert len(trimmed) <= 80
    assert "omitted" in trimmed
    assert trimmed.startswith("a")
    assert trimmed.endswith("z")


def test_remediation_prompt_uses_actionable_output_and_cap(tmp_path):
    calls = []
    huge_stderr = "tool transcript\n" * 20_000
    review_outputs = iter(
        [
            f"Full review comments:\n\n- [P1] Fix state init\n\n[stderr]\n{huge_stderr}",
            "No findings.\n",
        ]
    )

    def runner(args, cwd, input_text=None):
        calls.append((list(args), input_text))
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        max_remediation_input_chars=200,
    )

    MODULE.run_loop(config, runner)

    exec_prompts = [prompt for args, prompt in calls if args[1] == "exec"]
    assert len(exec_prompts) == 1
    assert exec_prompts[0] is not None
    assert "[P1] Fix state init" in exec_prompts[0]
    assert "tool transcript" not in exec_prompts[0]


def test_summary_includes_latest_review_excerpt_and_artifact_paths(tmp_path):
    review_outputs = iter(
        [
            "Full review comments:\n\n- [P1] Fix init\n",
            "No findings.\n",
        ]
    )

    def runner(args, cwd, input_text=None):
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
    )

    summary = MODULE.run_loop(config, runner)

    assert summary["latest_review_excerpt"] == "No findings."
    assert "artifact_paths" in summary
    assert summary["artifact_paths"]["summary"].endswith("summary.json")


def test_terminal_summary_surfaces_latest_findings_and_paths():
    summary = {
        "artifact_dir": "tmp/run",
        "final_status": "findings",
        "stopped_reason": "max_iterations_reached",
        "iterations": [
            {"iteration": 1, "review_status": "findings", "check_failures": 0},
            {"iteration": 2, "review_status": "findings", "check_failures": 1},
        ],
        "artifact_paths": {
            "reviews": ["tmp/run/review-1.txt", "tmp/run/review-final.txt"],
            "last_messages": ["tmp/run/remediation-2-last-message.txt"],
            "checks": ["tmp/run/check-2-1.txt", "tmp/run/check-2-2.txt"],
            "summary": "tmp/run/summary.json",
        },
        "latest_review_excerpt": "Full review comments:\n\n- [P2] Fix summary counts",
    }

    text = MODULE.format_terminal_summary(summary)

    assert "Review-remediation loop: findings (max_iterations_reached)" in text
    assert "Latest review: tmp/run/review-final.txt" in text
    assert "Latest remediation summary: tmp/run/remediation-2-last-message.txt" in text
    assert "- [P2] Fix summary counts" in text


def test_progress_logs_review_and_finding_summaries(tmp_path, capsys):
    review_outputs = iter(
        [
            "Full review comments:\n\n- [P2] Fix queue parity — src/state.py:1\n",
            "No findings.\n",
        ]
    )

    def runner(args, cwd, input_text=None):
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout=next(review_outputs))
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
    )

    MODULE.run_loop(config, runner)
    captured = capsys.readouterr()

    assert "review review-1: start" in captured.err
    assert "review review-1: findings" in captured.err
    assert "[P2] Fix queue parity" in captured.err
    assert "remediation 1: start" in captured.err
    assert "remediation 1: complete" in captured.err


def test_quiet_progress_suppresses_progress_logs(tmp_path, capsys):
    def runner(args, cwd, input_text=None):
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout="No findings.\n")
        return MODULE.CommandResult(list(args), 0, stdout="fixed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
        progress=False,
    )

    MODULE.run_loop(config, runner)
    captured = capsys.readouterr()

    assert captured.err == ""


def test_loop_writes_failure_summary_when_remediation_fails(tmp_path):
    def runner(args, cwd, input_text=None):
        if args[1] == "review":
            return MODULE.CommandResult(list(args), 0, stdout="Full review comments:\n\n- [P1] Fix\n")
        return MODULE.CommandResult(list(args), 1, stderr="Error: turn/start failed\n")

    config = MODULE.LoopConfig(
        base="main",
        max_iterations=1,
        codex_bin="codex",
        cwd=tmp_path,
        artifact_dir=tmp_path / "artifacts",
    )

    try:
        MODULE.run_loop(config, runner)
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected remediation failure")

    summary = (tmp_path / "artifacts" / "summary.json").read_text(encoding="utf-8")
    assert '"final_status": "error"' in summary
    assert '"stopped_reason": "remediation_failed"' in summary
    assert '"artifact_paths"' in summary
