"""Reads docs/spec: its rules, its steps, the shared background, and which rules are built."""

import re
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from gherkin.parser import Parser

from tests.support.cli import REPO

SPEC = REPO / "docs" / "spec"
IMPLEMENTED_RULES = REPO / "tests" / "implemented_rules.txt"
NOT_BUILT = "尚未建置"

_RULE_ID = re.compile(r"^([A-Z]{3}-R\d+)\b")
_KEYWORD = {"Context": "Given", "Action": "When", "Outcome": "Then"}


def rule_id(rule_name: str) -> str | None:
    """``IAM-R01`` from ``IAM-R01 The name list shows only …``."""
    match = _RULE_ID.match(rule_name)
    return match.group(1) if match else None


@dataclass(frozen=True)
class SpecStep:
    area: str  # the folder under docs/spec
    keyword: str  # Given, When or Then; And and But take the keyword before them
    text: str
    table: tuple[tuple[str, ...], ...] | None = None


def feature_files(spec: Path = SPEC) -> list[Path]:
    return sorted(spec.glob("*/*.feature"))


def _steps_of(children: list[dict]):
    for child in children:
        if "rule" in child:
            yield from _steps_of(child["rule"]["children"])
        else:
            yield from (child.get("background") or child["scenario"])["steps"]


def _resolve(area: str, steps) -> list[SpecStep]:
    resolved: list[SpecStep] = []
    keyword = "Given"
    for step in steps:
        keyword = _KEYWORD.get(step["keywordType"], keyword)
        table = step.get("dataTable")
        rows = tuple(tuple(cell["value"] for cell in row["cells"]) for row in table["rows"]) if table else None
        resolved.append(SpecStep(area, keyword, step["text"], rows))
    return resolved


def steps(spec: Path = SPEC) -> list[SpecStep]:
    """Every step of every feature file, as written (outline placeholders unfilled)."""
    found: list[SpecStep] = []
    for path in feature_files(spec):
        feature = Parser().parse(path.read_text(encoding="utf-8"))["feature"]
        found += _resolve(path.parent.name, _steps_of(feature["children"]))
    return found


def rule_ids(spec: Path = SPEC) -> set[str]:
    found: set[str] = set()
    for path in feature_files(spec):
        feature = Parser().parse(path.read_text(encoding="utf-8"))["feature"]
        for child in feature["children"]:
            if "rule" in child and (found_id := rule_id(child["rule"]["name"])):
                found.add(found_id)
    return found


def background(spec: Path = SPEC) -> list[SpecStep]:
    """The steps of the shared background in background.md, which every scenario starts from."""
    text = (spec / "background.md").read_text(encoding="utf-8")
    blocks = re.findall(r"```gherkin\n(.*?)```", text, re.S)
    if len(blocks) != 1:
        raise ValueError(f"background.md should hold exactly one gherkin block, found {len(blocks)}")
    feature = Parser().parse("Feature: shared background\n" + blocks[0])["feature"]
    return _resolve("", _steps_of(feature["children"]))


def read_implemented(path: Path = IMPLEMENTED_RULES) -> list[str]:
    """The rule IDs listed as built, one per line; blank lines and # comments are not entries."""
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def implemented_problems(listed: list[str], known: set[str]) -> list[str]:
    """What is wrong with a list of built rules: an ID the spec does not have, or a repeat."""
    problems = [f"{rule} is not a rule of the spec" for rule in sorted(set(listed) - known)]
    problems += [f"{rule} is listed more than once" for rule in sorted({r for r in listed if listed.count(r) > 1})]
    return problems


# The numbers of the runner and of the check tool

def collected_cases(root: Path = REPO) -> int:
    """How many spec cases pytest collects from tests/test_spec.py in the checkout at ``root``."""
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/test_spec.py", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=root,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        raise RuntimeError(f"collecting the spec failed:\n{done.stdout}\n{done.stderr}")
    return sum(1 for line in done.stdout.splitlines() if line.startswith("tests/test_spec.py::"))


def counted_cases(root: Path = REPO) -> int:
    """The ``cases=`` total that tools/check_spec.py prints for the checkout at ``root``."""
    done = subprocess.run([sys.executable, "tools/check_spec.py"], cwd=root, capture_output=True, text=True)
    return int(re.search(r"^total .* cases=(\d+)$", done.stdout, re.M).group(1))


def uncollected_cases_problem(root: Path = REPO) -> str | None:
    """Says so when pytest collects a different number of cases than the spec holds.

    pytest-bdd binds scenarios by name and silently keeps one of two that
    share a name in a feature; this is where that shows.
    """
    collected, counted = collected_cases(root), counted_cases(root)
    if collected == counted:
        return None
    return f"pytest collects {collected} spec cases, but tools/check_spec.py counts {counted}"


# The list of step phrasings in tests/steps/common/README.md

COMMON_STEPS_README = REPO / "tests" / "steps" / "common" / "README.md"
LIST_BEGINS = "<!-- step-phrasings: generated by `python -m tests.support.spec`, do not edit by hand -->"
LIST_ENDS = "<!-- step-phrasings: end -->"


def phrasing(text: str) -> str:
    """A step text with its values taken out: quoted text, outline placeholders and numbers."""
    text = re.sub(r'"[^"]*"', '"…"', text)
    text = re.sub(r"<[^>]+>", "<…>", text)
    return re.sub(r"\d[\d,.:]*", "N", text)


def phrasings_table(spec: Path = SPEC) -> str:
    """Every step phrasing of the spec, the ones used by the most areas first."""
    areas: dict[tuple[str, str], Counter[str]] = {}
    for step in steps(spec):
        areas.setdefault((step.keyword, phrasing(step.text)), Counter())[step.area] += 1
    rows = sorted(areas.items(), key=lambda item: (-len(item[1]), -sum(item[1].values()), item[0]))
    shared = sum(1 for used in areas.values() if len(used) > 1)
    lines = [
        f"共 {len(rows)} 種句型，其中 {shared} 種出現在兩個以上的領域。",
        "",
        "| 句型 | 關鍵字 | 領域數 | 次數 | 出現的領域 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for (keyword, text), used in rows:
        where = "、".join(f"{area} {count}" for area, count in sorted(used.items()))
        lines.append(f"| `{text.replace('|', '¦')}` | {keyword} | {len(used)} | {sum(used.values())} | {where} |")
    return "\n".join(lines)


def readme_with_current_list(readme: str, spec: Path = SPEC) -> str:
    """``readme`` with the list between its two markers replaced by the current one."""
    head, rest = readme.split(LIST_BEGINS)
    _, tail = rest.split(LIST_ENDS)
    return f"{head}{LIST_BEGINS}\n{phrasings_table(spec)}\n{LIST_ENDS}{tail}"


if __name__ == "__main__":
    COMMON_STEPS_README.write_text(
        readme_with_current_list(COMMON_STEPS_README.read_text(encoding="utf-8")), encoding="utf-8"
    )
