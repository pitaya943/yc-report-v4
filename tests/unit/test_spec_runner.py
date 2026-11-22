"""The runner of the spec's feature files: what runs, what is skipped, and that nothing is lost."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pytest_bdd.feature import get_features
from pytest_bdd.steps import step_function_context_registry

from tests.steps import step_definitions
from tests.support import spec
from tests.support.cli import REPO


@pytest.fixture
def checkout(tmp_path) -> Path:
    """A throwaway copy of what the spec runner reads."""
    ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache")
    for directory in ("docs/spec", "tests", "tools"):
        shutil.copytree(REPO / directory, tmp_path / directory, ignore=ignore)
    shutil.copy(REPO / "pyproject.toml", tmp_path)
    return tmp_path


def run_spec(checkout: Path, pg_server: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_spec.py", "-q", "-rfs", "-p", "no:cacheprovider"],
        cwd=checkout,
        env={**os.environ, "TEST_DATABASE_URL": pg_server},
        capture_output=True,
        text=True,
    )


def test_a_rule_that_is_not_listed_is_skipped_by_name_and_a_listed_one_runs(checkout, pg_server):
    # PAY-R01 has no step definitions: its scenarios can only fail, and only if they run.
    (checkout / "tests/implemented_rules.txt").write_text("PAY-R01\n", encoding="utf-8")

    done = run_spec(checkout, pg_server)

    assert done.returncode == 1, done.stdout + done.stderr
    assert "StepDefinitionNotFoundError" in done.stdout
    failed = [line for line in done.stdout.splitlines() if line.startswith("FAILED ")]
    skipped = [line for line in done.stdout.splitlines() if line.startswith("SKIPPED ")]
    assert failed
    assert any(line.endswith("尚未建置：IAM-R01") for line in skipped)
    assert not any("PAY-R01" in line for line in skipped)
    # Every case either ran or was skipped under its rule's name.
    cases = sum(int(line.split("[")[1].split("]")[0]) for line in skipped) + len(failed)
    assert cases == spec.counted_cases(checkout)


def test_the_built_rules_run_without_being_skipped(checkout, pg_server):
    done = run_spec(checkout, pg_server)

    assert done.returncode == 0, done.stdout + done.stderr
    skipped = [line for line in done.stdout.splitlines() if line.startswith("SKIPPED ")]
    for rule in spec.read_implemented():
        assert not any(line.endswith(f"：{rule}") for line in skipped)


def test_pytest_collects_as_many_cases_as_the_spec_holds():
    assert spec.uncollected_cases_problem() is None


def test_two_scenarios_sharing_a_name_in_a_feature_are_noticed(checkout):
    feature = checkout / "docs/spec/accounts/IAM-F01-sign-in.feature"
    feature.write_text(
        feature.read_text(encoding="utf-8")
        + "\n    Scenario: Landing page by role\n      When a visitor chooses group \"admin\"\n",
        encoding="utf-8",
    )

    problem = spec.uncollected_cases_problem(checkout)

    assert problem is not None and problem.startswith("pytest collects ")


def test_every_rule_listed_as_built_is_a_rule_of_the_spec_listed_once():
    assert spec.implemented_problems(spec.read_implemented(), spec.rule_ids()) == []


@pytest.mark.parametrize(
    ("content", "problems"),
    [
        ("IAM-R01\nIAM-R99\n", ["IAM-R99 is not a rule of the spec"]),
        ("IAM-R01\nAUD-R01\nIAM-R01\n", ["IAM-R01 is listed more than once"]),
        ("iam-r01\n", ["iam-r01 is not a rule of the spec"]),
        ("# a comment\n\nIAM-R01\n  AUD-R01  \n", []),
    ],
)
def test_a_rule_that_does_not_exist_or_is_listed_twice_is_a_problem(tmp_path, content, problems):
    listing = tmp_path / "implemented_rules.txt"
    listing.write_text(content, encoding="utf-8")

    assert spec.implemented_problems(spec.read_implemented(listing), spec.rule_ids()) == problems


def test_no_step_of_the_spec_is_matched_by_two_definitions():
    """Steps are visible to every area's features, so one text must have one meaning."""
    step_definitions()
    definitions = list(step_function_context_registry.values())
    ambiguous = set()
    for feature in get_features([str(spec.SPEC)]):
        for template in feature.scenarios.values():
            examples = [context for table in template.examples for context in table.as_contexts()] or [{}]
            for example in examples:
                for step in template.render(example).steps:
                    matching = [
                        definition
                        for definition in definitions
                        if definition.type in (None, step.type) and definition.parser.is_matching(step.name)
                    ]
                    if len(matching) > 1:
                        ambiguous.add(f"{step.type}: {step.name}")

    assert sorted(ambiguous) == []


def test_the_list_of_step_phrasings_in_the_common_steps_readme_is_current():
    readme = spec.COMMON_STEPS_README.read_text(encoding="utf-8")

    assert readme == spec.readme_with_current_list(readme), "run: python -m tests.support.spec"
