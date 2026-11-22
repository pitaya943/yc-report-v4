"""Reads docs/spec: its rules, its steps, the shared background, and which rules are built."""

import re
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
