#!/usr/bin/env bash
set -euo pipefail

root="${1:-.}"
plan_path="${2:-/tmp/meminit-migration-plan.json}"

echo "Running meminit context (json) at root: ${root}"
meminit context --root "${root}" --format json

echo "Generating migration plan: ${plan_path}"
meminit scan --root "${root}" --plan "${plan_path}" --format json

echo "Running readiness checks"
meminit doctor --root "${root}" --format json
meminit check --root "${root}" --format json

echo "Preview plan-driven fixes"
meminit fix --root "${root}" --plan "${plan_path}" --format json

echo "Next:"
echo "  1) Review ${plan_path}"
echo "  2) Apply config updates if needed"
echo "  3) Run: meminit fix --root \"${root}\" --plan \"${plan_path}\" --no-dry-run --format json"
echo "  4) Re-run: meminit check --root \"${root}\" --format json"
