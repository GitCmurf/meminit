import tomllib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
LICENSE_PATH = REPO_ROOT / "LICENSE"
PRE_COMMIT_PATH = REPO_ROOT / ".pre-commit-config.yaml"
GITLEAKS_PATH = REPO_ROOT / ".gitleaks.toml"


def load_workflow(name: str) -> dict:
    workflow_path = REPO_ROOT / ".github" / "workflows" / name
    return yaml.safe_load(workflow_path.read_text(encoding="utf-8"))


def step_index(steps: list[dict], run_snippet: str) -> int:
    for index, step in enumerate(steps):
        if run_snippet in step.get("run", ""):
            return index
    raise AssertionError(f"Missing step containing: {run_snippet}")


def step_index_uses(steps: list[dict], uses_snippet: str) -> int:
    for index, step in enumerate(steps):
        if uses_snippet in step.get("uses", ""):
            return index
    raise AssertionError(f"Missing step using: {uses_snippet}")


def test_ci_jobs_create_a_virtual_environment_before_installing_dependencies():
    workflow = load_workflow("ci.yml")

    for job_name in ("docops", "python", "slow-scale"):
        steps = workflow["jobs"][job_name]["steps"]
        assert step_index_uses(steps, "actions/setup-python@v5") < step_index(steps, "uv venv")
        assert step_index(steps, "uv venv") < step_index(
            steps, 'uv pip install --python .venv/bin/python -e ".[dev]"'
        )


def test_gitleaks_scans_have_full_history_available():
    ci_workflow = load_workflow("ci.yml")
    ci_steps = ci_workflow["jobs"]["python"]["steps"]
    ci_checkout = next(step for step in ci_steps if step.get("uses") == "actions/checkout@v4")
    assert ci_checkout["with"]["fetch-depth"] == 0
    assert step_index_uses(ci_steps, "actions/checkout@v4") < step_index_uses(
        ci_steps, "gitleaks/gitleaks-action@v2"
    )

    release_workflow = load_workflow("release.yml")
    release_steps = release_workflow["jobs"]["build-and-verify"]["steps"]
    release_checkout = next(
        step for step in release_steps if step.get("uses") == "actions/checkout@v4"
    )
    assert release_checkout["with"]["fetch-depth"] == 0
    assert step_index_uses(release_steps, "actions/checkout@v4") < step_index_uses(
        release_steps, "gitleaks/gitleaks-action@v2"
    )


def test_prettier_hook_excludes_governed_template_trees():
    config = yaml.safe_load(PRE_COMMIT_PATH.read_text(encoding="utf-8"))
    prettier_hook = next(
        hook
        for repo in config["repos"]
        if repo["repo"] == "https://github.com/pre-commit/mirrors-prettier"
        for hook in repo["hooks"]
        if hook["id"] == "prettier"
    )

    exclude = prettier_hook.get("exclude", "")
    assert "docs/00-governance/templates/" in exclude
    assert "src/meminit/core/assets/org_profiles/default/templates/" in exclude


def test_gitleaks_config_extends_default_rules():
    config = tomllib.loads(GITLEAKS_PATH.read_text(encoding="utf-8"))

    assert config["extend"]["useDefault"] is True


def test_release_workflow_uses_the_correct_twine_and_testpypi_publish_commands():
    workflow = load_workflow("release.yml")
    triggers = workflow[True]

    dispatch_inputs = triggers["workflow_dispatch"]["inputs"]
    assert dispatch_inputs["tag_name"]["required"] is True
    assert dispatch_inputs["tag_name"]["type"] == "string"

    build_steps = workflow["jobs"]["build-and-verify"]["steps"]
    checkout_step = next(step for step in build_steps if step["name"] == "Checkout repository")
    assert checkout_step["with"]["ref"] == (
        "${{ github.event_name == 'workflow_dispatch' && inputs.tag_name || github.ref }}"
    )

    twine_step = next(
        step for step in build_steps if step["name"] == "Validate package metadata using twine"
    )
    assert "uvx twine check dist/*" in twine_step["run"]
    assert "uv pip install twine" not in twine_step["run"]

    dry_run_steps = workflow["jobs"]["dry-run-publish"]["steps"]
    publish_step = next(
        step for step in dry_run_steps if step["name"] == "Publish to TestPyPI"
    )
    assert "uv publish --publish-url https://test.pypi.org/legacy/" in publish_step["run"]
    assert "--check-url https://test.pypi.org/simple/" in publish_step["run"]
    assert "--index https://test.pypi.org/simple/" not in publish_step["run"]

    release_job_steps = workflow["jobs"]["github-release"]["steps"]
    detect_step = next(
        step for step in release_job_steps if step["name"] == "Detect prerelease tag"
    )
    assert "prerelease=true" in detect_step["run"]
    assert "prerelease=false" in detect_step["run"]

    gh_release_step = next(
        step for step in release_job_steps if step["name"] == "Create GitHub Release (Draft)"
    )
    assert (
        gh_release_step["with"]["tag_name"]
        == "${{ github.event_name == 'workflow_dispatch' && inputs.tag_name || github.ref_name }}"
    )
    assert gh_release_step["with"]["prerelease"] == "${{ steps.release-meta.outputs.prerelease }}"


def test_release_workflow_verifies_the_built_wheel_without_checkout_shadowing():
    workflow = load_workflow("release.yml")
    build_steps = workflow["jobs"]["build-and-verify"]["steps"]
    verify_step = next(
        step
        for step in build_steps
        if step["name"] == "Run verification in clean virtual environment"
    )

    run_script = verify_step["run"]
    assert "tmpdir=$(mktemp -d)" in run_script
    assert 'uv venv "$tmpdir/test_env"' in run_script
    assert 'uv pip install "${GITHUB_WORKSPACE}"/dist/*.whl' in run_script
    assert 'meminit doctor --root "$GITHUB_WORKSPACE" --format json' in run_script
    assert 'meminit check --root "$GITHUB_WORKSPACE" --format json' in run_script
    assert 'pytest -c /dev/null "${GITHUB_WORKSPACE}/tests"' in run_script
    assert 'cd "$tmpdir"' in run_script


def test_root_license_remains_apache_2_0():
    license_text = LICENSE_PATH.read_text(encoding="utf-8")

    assert license_text.lstrip().startswith("Apache License")
    assert "Version 2.0, January 2004" in license_text
    assert "for use, reproduction, or distribution of Your modifications" in license_text
    assert "provided Your use," in license_text
    assert "MIT License" not in license_text
    assert "Copyright (c) 2019 Zachary Rice" not in license_text
