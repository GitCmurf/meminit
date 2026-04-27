#!/usr/bin/env python3
"""Run a bounded Codex review/remediation loop against a base branch."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


STATUS_RE = re.compile(r"^\s*REVIEW_STATUS:\s*(clear|findings)\s*$", re.IGNORECASE | re.MULTILINE)

DEFAULT_REVIEW_PROMPT = """Review the current repository changes against the base branch.
Focus on correctness, security, behavior regressions, architecture quality, and missing tests.
Return actionable findings only.
End with exactly one status line:
REVIEW_STATUS: clear
or:
REVIEW_STATUS: findings
Use REVIEW_STATUS: clear only when there are no actionable findings to remediate.
"""

DEFAULT_REMEDIATION_PROMPT = """You are running a bounded review-remediation loop.

Review findings from the previous Codex review are included below. Remediate the valid actionable
findings to high quality while respecting this repository's AGENTS.md instructions.

Rules:
- Keep the patch focused on the review findings.
- Preserve existing user changes; do not revert unrelated work.
- Maintain the repository's Code + Documentation + Tests atomic-unit rule.
- Add or update tests for behavior changes.
- Run the most relevant verification commands before finishing.
- If a finding is invalid or impossible to fix safely, explain that in your final response.

Previous review output:
"""


@dataclass(frozen=True)
class CommandResult:
    args: list[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""


@dataclass(frozen=True)
class LoopConfig:
    base: str
    max_iterations: int
    codex_bin: str
    cwd: Path
    artifact_dir: Path
    model: str | None = None
    exec_sandbox: str = "workspace-write"
    exec_color: str = "never"
    full_auto: bool = True
    exec_json: bool = False
    output_last_message: bool = True
    dry_run: bool = False
    final_review: bool = True
    check_commands: tuple[str, ...] = field(default_factory=tuple)


Runner = Callable[[Sequence[str], Path, str | None], CommandResult]


def default_runner(args: Sequence[str], cwd: Path, input_text: str | None = None) -> CommandResult:
    completed = subprocess.run(
        list(args),
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    return CommandResult(
        args=list(args),
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def detect_review_status(output: str) -> str:
    """Return clear/findings/unknown from the explicit REVIEW_STATUS line."""
    match = STATUS_RE.search(output)
    if match:
        return match.group(1).lower()
    return "unknown"


def build_review_command(config: LoopConfig) -> list[str]:
    command = [config.codex_bin]
    if config.model:
        command.extend(["--model", config.model])
    command.extend(["review", "--base", config.base])
    command.append("-")
    return command


def build_remediation_command(config: LoopConfig, output_last_message: Path | None = None) -> list[str]:
    command = [config.codex_bin, "exec"]
    if config.full_auto:
        command.append("--full-auto")
    command.extend(["--sandbox", config.exec_sandbox])
    command.extend(["--color", config.exec_color])
    if config.exec_json:
        command.append("--json")
    if config.model:
        command.extend(["--model", config.model])
    if output_last_message:
        command.extend(["--output-last-message", str(output_last_message)])
    command.append("-")
    return command


def write_artifact(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_codex_review(config: LoopConfig, runner: Runner, label: str) -> tuple[str, CommandResult]:
    command = build_review_command(config)
    if config.dry_run:
        result = CommandResult(command, 0, stdout="DRY_RUN\nREVIEW_STATUS: findings\n")
    else:
        result = runner(command, config.cwd, DEFAULT_REVIEW_PROMPT)
    combined = _combined_output(result)
    write_artifact(config.artifact_dir / f"{label}.txt", combined)
    if result.returncode != 0:
        raise RuntimeError(f"codex review failed for {label}; see {config.artifact_dir / f'{label}.txt'}")
    return detect_review_status(combined), result


def run_remediation(
    config: LoopConfig,
    runner: Runner,
    iteration: int,
    review_output: str,
) -> CommandResult:
    last_message_path = (
        config.artifact_dir / f"remediation-{iteration}-last-message.txt"
        if config.output_last_message
        else None
    )
    command = build_remediation_command(config, last_message_path)
    prompt = f"{DEFAULT_REMEDIATION_PROMPT}\n{review_output}"
    if config.dry_run:
        result = CommandResult(command, 0, stdout="DRY_RUN remediation skipped\n")
    else:
        result = runner(command, config.cwd, prompt)
    write_artifact(config.artifact_dir / f"remediation-{iteration}.txt", _combined_output(result))
    if result.returncode != 0:
        raise RuntimeError(
            f"codex exec remediation failed for iteration {iteration}; "
            f"see {config.artifact_dir / f'remediation-{iteration}.txt'}"
        )
    return result


def run_checks(config: LoopConfig, runner: Runner, iteration: int) -> list[CommandResult]:
    results: list[CommandResult] = []
    for index, check in enumerate(config.check_commands, start=1):
        command = shlex.split(check)
        if config.dry_run:
            result = CommandResult(command, 0, stdout=f"DRY_RUN check skipped: {check}\n")
        else:
            result = runner(command, config.cwd, None)
        results.append(result)
        write_artifact(
            config.artifact_dir / f"check-{iteration}-{index}.txt",
            _combined_output(result),
        )
    return results


def _format_check_failures(check_results: list[CommandResult]) -> str:
    failures = [r for r in check_results if r.returncode != 0]
    if not failures:
        return ""
    parts = ["Check failures from the previous iteration:"]
    for r in failures:
        parts.append(f"\n$ {shlex.join(r.args)}\n{_combined_output(r)}")
    return "\n".join(parts)


def run_loop(config: LoopConfig, runner: Runner = default_runner) -> dict[str, object]:
    if config.max_iterations < 1:
        raise ValueError("--max-iterations must be at least 1")

    config.artifact_dir.mkdir(parents=True, exist_ok=True)
    iterations: list[dict[str, object]] = []
    summary: dict[str, object] = {
        "base": config.base,
        "max_iterations": config.max_iterations,
        "artifact_dir": str(config.artifact_dir),
        "iterations": iterations,
        "final_status": "unknown",
        "pending_check_failures": False,
        "stopped_reason": None,
    }

    pending_check_failures = ""
    for iteration in range(1, config.max_iterations + 1):
        status, review = run_codex_review(config, runner, f"review-{iteration}")
        last_review_output = _combined_output(review)
        iterations.append({"iteration": iteration, "review_status": status})

        if status == "clear":
            summary["final_status"] = "clear"
            summary["stopped_reason"] = "review_clear"
            write_summary(config, summary)
            return summary

        remediation_input = last_review_output
        if pending_check_failures:
            remediation_input = pending_check_failures + "\n\n" + remediation_input

        run_remediation(config, runner, iteration, remediation_input)

        check_results = run_checks(config, runner, iteration)
        pending_check_failures = _format_check_failures(check_results)
        iterations[-1]["check_failures"] = sum(1 for result in check_results if result.returncode != 0)

    if config.final_review:
        status, _ = run_codex_review(config, runner, "review-final")
        if pending_check_failures:
            summary["final_status"] = "findings"
            summary["pending_check_failures"] = True
            summary["stopped_reason"] = "max_iterations_reached_with_check_failures"
        else:
            summary["final_status"] = status
            summary["stopped_reason"] = "review_clear" if status == "clear" else "max_iterations_reached"
    else:
        # Status after the last remediation is not known without a review.
        summary["final_status"] = "unknown"
        summary["pending_check_failures"] = bool(pending_check_failures)
        summary["stopped_reason"] = "max_iterations_reached"

    write_summary(config, summary)
    return summary


def write_summary(config: LoopConfig, summary: dict[str, object]) -> None:
    write_artifact(config.artifact_dir / "summary.json", json.dumps(summary, indent=2, sort_keys=True))


def _combined_output(result: CommandResult) -> str:
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append("\n[stderr]\n" + result.stderr.rstrip())
    return "\n".join(parts).strip() + "\n"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a bounded Codex review/remediation loop against a base branch.",
    )
    parser.add_argument("--base", default="main", help="Base branch passed to codex review.")
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=2,
        help="Maximum remediation passes before stopping. Default: 2.",
    )
    parser.add_argument("--codex-bin", default="codex", help="Codex executable path/name.")
    parser.add_argument("--model", default=None, help="Optional model passed to codex.")
    parser.add_argument(
        "--exec-sandbox",
        default="workspace-write",
        choices=("read-only", "workspace-write", "danger-full-access"),
        help="Sandbox mode for codex exec remediation passes.",
    )
    parser.add_argument(
        "--exec-color",
        default="never",
        choices=("always", "never", "auto"),
        help="Color mode for codex exec remediation output. Default: never.",
    )
    parser.add_argument(
        "--exec-json",
        action="store_true",
        help="Pass --json to codex exec and capture JSONL event output.",
    )
    parser.add_argument(
        "--no-output-last-message",
        action="store_true",
        help="Do not pass --output-last-message to codex exec remediation passes.",
    )
    parser.add_argument(
        "--no-full-auto",
        action="store_true",
        help="Do not pass --full-auto to codex exec.",
    )
    parser.add_argument(
        "--check",
        action="append",
        default=[],
        help="Verification command to run after each remediation pass. Repeatable.",
    )
    parser.add_argument(
        "--artifact-dir",
        default=None,
        help="Directory for review/remediation/check transcripts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print the loop shape without running Codex.")
    parser.add_argument(
        "--skip-final-review",
        action="store_true",
        help="Do not run the final review after the last remediation pass.",
    )
    return parser.parse_args(argv)


def default_artifact_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return Path("tmp") / "codex-review-remediation-loop" / timestamp


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    artifact_dir = Path(args.artifact_dir) if args.artifact_dir else default_artifact_dir()
    config = LoopConfig(
        base=args.base,
        max_iterations=args.max_iterations,
        codex_bin=args.codex_bin,
        cwd=Path.cwd(),
        artifact_dir=artifact_dir,
        model=args.model,
        exec_sandbox=args.exec_sandbox,
        exec_color=args.exec_color,
        full_auto=not args.no_full_auto,
        exec_json=args.exec_json,
        output_last_message=not args.no_output_last_message,
        dry_run=args.dry_run,
        final_review=not args.skip_final_review,
        check_commands=tuple(args.check),
    )

    try:
        summary = run_loop(config)
    except Exception as exc:  # pragma: no cover - command-line reporting path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    return 0 if summary.get("final_status") == "clear" else 2


if __name__ == "__main__":
    raise SystemExit(main())
