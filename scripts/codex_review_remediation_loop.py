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
CODEX_FINDING_RE = re.compile(r"^\s*-\s*\[P[0-3]\]\s+", re.MULTILINE)
CODEX_FINDING_LINE_RE = re.compile(r"^\s*-\s*(\[P[0-3]\]\s+.+)$")

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
    max_remediation_input_chars: int = 200_000
    terminal_excerpt_chars: int = 4_000
    progress: bool = True
    check_commands: tuple[str, ...] = field(default_factory=tuple)


Runner = Callable[[Sequence[str], Path, str | None], CommandResult]


def progress_log(config: LoopConfig, message: str) -> None:
    if not config.progress:
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)


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
    """Return clear/findings/unknown for Codex review output."""
    match = STATUS_RE.search(output)
    if match:
        return match.group(1).lower()

    if CODEX_FINDING_RE.search(output):
        return "findings"

    normalized = output.lower()
    finding_markers = (
        "review comment:",
        "review comments:",
        "full review comments:",
    )
    if any(marker in normalized for marker in finding_markers):
        return "findings"

    normalized_lines = [line.strip().lower() for line in output.splitlines()]
    clear_lines = {
        "no findings.",
        "no findings",
        "no issues found.",
        "no issues found",
        "no actionable findings.",
        "no actionable findings",
    }
    if any(line in clear_lines for line in normalized_lines):
        return "clear"
    return "unknown"


def extract_finding_summaries(output: str, limit: int = 5) -> list[str]:
    summaries: list[str] = []
    for line in actionable_review_output(output).splitlines():
        match = CODEX_FINDING_LINE_RE.match(line)
        if not match:
            continue
        summaries.append(match.group(1).strip())
        if len(summaries) >= limit:
            break
    return summaries


def build_review_command(config: LoopConfig) -> list[str]:
    command = [config.codex_bin]
    if config.model:
        command.extend(["--model", config.model])
    command.extend(["review", "--base", config.base])
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
    progress_log(config, f"review {label}: start ({shlex.join(command)})")
    if config.dry_run:
        result = CommandResult(command, 0, stdout="DRY_RUN\nREVIEW_STATUS: findings\n")
    else:
        result = runner(command, config.cwd, None)
    combined = _combined_output(result)
    write_artifact(config.artifact_dir / f"{label}.txt", combined)
    if review_failed_to_run(result):
        progress_log(config, f"review {label}: failed (exit {result.returncode})")
        raise RuntimeError(f"codex review failed for {label}; see {config.artifact_dir / f'{label}.txt'}")
    status = detect_review_status(combined)
    progress_log(config, f"review {label}: {status}")
    for finding in extract_finding_summaries(combined):
        progress_log(config, f"review {label}: {finding}")
    return status, result


def review_failed_to_run(result: CommandResult) -> bool:
    """Distinguish review invocation failures from review findings."""
    if result.returncode == 0:
        return False
    if result.returncode < 0:
        return True
    if result.returncode >= 2:
        return True

    stderr = result.stderr.lower()
    fatal_markers = (
        "error:",
        "fatal error",
        "failed to create session",
        "thread/start failed",
        "for more information, try '--help'",
    )
    return any(marker in stderr for marker in fatal_markers)


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
    prompt = f"{DEFAULT_REMEDIATION_PROMPT}\n{trim_for_prompt(review_output, config.max_remediation_input_chars)}"
    progress_log(config, f"remediation {iteration}: start ({shlex.join(command)})")
    if config.dry_run:
        result = CommandResult(command, 0, stdout="DRY_RUN remediation skipped\n")
    else:
        result = runner(command, config.cwd, prompt)
    write_artifact(config.artifact_dir / f"remediation-{iteration}.txt", _combined_output(result))
    if result.returncode != 0:
        progress_log(config, f"remediation {iteration}: failed (exit {result.returncode})")
        raise RuntimeError(
            f"codex exec remediation failed for iteration {iteration}; "
            f"see {config.artifact_dir / f'remediation-{iteration}.txt'}"
        )
    progress_log(config, f"remediation {iteration}: complete")
    return result


def run_checks(config: LoopConfig, runner: Runner, iteration: int) -> list[CommandResult]:
    results: list[CommandResult] = []
    for index, check in enumerate(config.check_commands, start=1):
        command = shlex.split(check)
        progress_log(config, f"check {iteration}.{index}: start ({check})")
        if config.dry_run:
            result = CommandResult(command, 0, stdout=f"DRY_RUN check skipped: {check}\n")
        else:
            result = runner(command, config.cwd, None)
        results.append(result)
        write_artifact(
            config.artifact_dir / f"check-{iteration}-{index}.txt",
            _combined_output(result),
        )
        if result.returncode == 0:
            progress_log(config, f"check {iteration}.{index}: passed")
        else:
            progress_log(config, f"check {iteration}.{index}: failed (exit {result.returncode})")
    return results


def _format_check_failures(check_results: list[CommandResult]) -> str:
    failures = [r for r in check_results if r.returncode != 0]
    if not failures:
        return ""
    parts = ["Check failures from the previous iteration:"]
    for r in failures:
        parts.append(f"\n$ {shlex.join(r.args)}\n{_combined_output(r)}")
    return "\n".join(parts)


def actionable_review_output(output: str) -> str:
    """Keep the review's actionable comments, not the verbose tool transcript."""
    review_text = output.split("\n[stderr]\n", 1)[0].strip()
    if not review_text:
        review_text = output.strip()
    return review_text


def trim_for_prompt(text: str, max_chars: int) -> str:
    if max_chars < 1:
        raise ValueError("max prompt characters must be positive")
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    marker = f"\n\n[... omitted {omitted} characters to stay under prompt limit ...]\n\n"
    if len(marker) >= max_chars:
        return marker[:max_chars]
    keep_total = max_chars - len(marker)
    keep_head = keep_total // 2
    keep_tail = keep_total - keep_head
    return (
        text[:keep_head]
        + marker
        + text[-keep_tail:]
    )


def excerpt_for_terminal(text: str, max_chars: int) -> str:
    text = text.strip()
    if not text:
        return ""
    return trim_for_prompt(text, max_chars)


def add_artifact_paths(summary: dict[str, object], config: LoopConfig) -> None:
    artifact_dir = config.artifact_dir
    files = sorted(path for path in artifact_dir.glob("*") if path.is_file())
    summary["artifact_paths"] = {
        "artifact_dir": str(artifact_dir),
        "summary": str(artifact_dir / "summary.json"),
        "reviews": [str(path) for path in files if path.name.startswith("review-")],
        "remediations": [
            str(path)
            for path in files
            if path.name.startswith("remediation-") and "last-message" not in path.name
        ],
        "last_messages": [
            str(path)
            for path in files
            if path.name.startswith("remediation-") and "last-message" in path.name
        ],
        "checks": [str(path) for path in files if path.name.startswith("check-")],
    }


def latest_file(artifact_dir: Path, prefix: str, suffix: str = ".txt") -> str | None:
    files = sorted(
        path for path in artifact_dir.glob(f"{prefix}*{suffix}") if path.is_file()
    )
    return str(files[-1]) if files else None


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
        last_review_output = actionable_review_output(_combined_output(review))
        iterations.append({"iteration": iteration, "review_status": status})

        if status == "clear" and not pending_check_failures:
            summary["final_status"] = "clear"
            summary["stopped_reason"] = "review_clear"
            summary["latest_review_excerpt"] = excerpt_for_terminal(
                last_review_output,
                config.terminal_excerpt_chars,
            )
            write_summary(config, summary)
            return summary

        remediation_input = last_review_output
        if pending_check_failures:
            remediation_input = pending_check_failures + "\n\n" + remediation_input

        try:
            run_remediation(config, runner, iteration, remediation_input)
        except Exception as exc:
            summary["final_status"] = "error"
            summary["stopped_reason"] = "remediation_failed"
            summary["error"] = str(exc)
            iterations[-1]["remediation_failed"] = True
            write_summary(config, summary)
            raise

        check_results = run_checks(config, runner, iteration)
        pending_check_failures = _format_check_failures(check_results)
        iterations[-1]["check_failures"] = sum(1 for result in check_results if result.returncode != 0)

    if config.final_review:
        status, final_review = run_codex_review(config, runner, "review-final")
        final_review_output = actionable_review_output(_combined_output(final_review))
        summary["latest_review_excerpt"] = excerpt_for_terminal(
            final_review_output,
            config.terminal_excerpt_chars,
        )
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
    add_artifact_paths(summary, config)
    write_artifact(config.artifact_dir / "summary.json", json.dumps(summary, indent=2, sort_keys=True))


def _combined_output(result: CommandResult) -> str:
    parts = []
    if result.stdout:
        parts.append(result.stdout.rstrip())
    if result.stderr:
        parts.append("\n[stderr]\n" + result.stderr.rstrip())
    return "\n".join(parts).strip() + "\n"


def format_terminal_summary(summary: dict[str, object]) -> str:
    artifact_dir = str(summary.get("artifact_dir") or "")
    status = str(summary.get("final_status") or "unknown")
    reason = str(summary.get("stopped_reason") or "unknown")
    lines = [
        f"Review-remediation loop: {status} ({reason})",
        f"Artifacts: {artifact_dir}",
    ]

    iterations = summary.get("iterations")
    if isinstance(iterations, list) and iterations:
        lines.append("Iterations:")
        for item in iterations:
            if not isinstance(item, dict):
                continue
            iteration = item.get("iteration")
            review_status = item.get("review_status", "unknown")
            check_failures = item.get("check_failures")
            check_text = "checks not run" if check_failures is None else f"check failures: {check_failures}"
            failed = " remediation failed" if item.get("remediation_failed") else ""
            lines.append(f"  {iteration}: review={review_status}, {check_text}{failed}")

    artifact_paths = summary.get("artifact_paths")
    if isinstance(artifact_paths, dict):
        reviews = artifact_paths.get("reviews")
        last_messages = artifact_paths.get("last_messages")
        checks = artifact_paths.get("checks")
        if isinstance(reviews, list) and reviews:
            lines.append(f"Latest review: {reviews[-1]}")
        if isinstance(last_messages, list) and last_messages:
            lines.append(f"Latest remediation summary: {last_messages[-1]}")
        if isinstance(checks, list) and checks:
            lines.append(f"Latest check outputs: {', '.join(str(path) for path in checks[-2:])}")
        summary_path = artifact_paths.get("summary")
        if summary_path:
            lines.append(f"JSON summary: {summary_path}")

    excerpt = str(summary.get("latest_review_excerpt") or "").strip()
    if excerpt:
        lines.append("")
        lines.append("Latest actionable review output:")
        lines.append(excerpt)

    if summary.get("error"):
        lines.append("")
        lines.append(f"Error: {summary['error']}")

    return "\n".join(lines)


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
    parser.add_argument(
        "--max-remediation-input-chars",
        type=int,
        default=200_000,
        help="Maximum review/check text characters passed into each remediation prompt.",
    )
    parser.add_argument(
        "--terminal-excerpt-chars",
        type=int,
        default=4_000,
        help="Maximum latest-review characters shown in terminal text summaries.",
    )
    parser.add_argument(
        "--summary-format",
        choices=("text", "json", "both"),
        default="text",
        help="Summary format printed to stdout. Full JSON is always written to summary.json.",
    )
    parser.add_argument(
        "--quiet-progress",
        action="store_true",
        help="Suppress timestamped progress logs on stderr.",
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
        max_remediation_input_chars=args.max_remediation_input_chars,
        terminal_excerpt_chars=args.terminal_excerpt_chars,
        progress=not args.quiet_progress,
        check_commands=tuple(args.check),
    )

    try:
        summary = run_loop(config)
    except Exception as exc:  # pragma: no cover - command-line reporting path
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.summary_format in {"text", "both"}:
        print(format_terminal_summary(summary))
    if args.summary_format in {"json", "both"}:
        if args.summary_format == "both":
            print()
        print(json.dumps(summary, indent=2, sort_keys=True))
    if args.dry_run:
        return 0
    return 0 if summary.get("final_status") == "clear" else 2


if __name__ == "__main__":
    raise SystemExit(main())
