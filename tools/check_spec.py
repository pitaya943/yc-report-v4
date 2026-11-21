#!/usr/bin/env python3
"""Check that the behaviour spec under docs/spec/ is well-formed.

Run from the repository root:

    python tools/check_spec.py

It fails (exit status 1) when:
  * a .feature file is not valid Gherkin;
  * a feature's tag (@IAM-F01) does not match its file name;
  * two scenarios in one feature share a name (test runners that bind
    scenarios by name silently drop one of them);
  * a rule ID (IAM-R01) is used by more than one rule;
  * a feature is not linked from its area's index.md;
  * the totals differ from the ones recorded in docs/spec/index.md.

A "case" is one runnable example: a plain Scenario counts as one, a Scenario
Outline counts once per Examples row.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from pathlib import Path

from gherkin.errors import CompositeParserException
from gherkin.parser import Parser

SPEC = Path("docs/spec")
# The totals are recorded in index.md in a comment the tool can read, next to
# the sentence a person reads, so the two cannot drift apart unnoticed.
COUNTS_RE = re.compile(
    r"<!-- spec-counts: features=(\d+) rules=(\d+) scenarios=(\d+) cases=(\d+) -->"
)
RULE_ID_RE = re.compile(r"^([A-Z]{3}-R\d+)\b")


def walk(children, totals, names, rule_ids, path):
    """Count rules, scenarios and cases in a feature's (or rule's) children."""
    for child in children:
        if "rule" in child:
            rule = child["rule"]
            totals["rules"] += 1
            match = RULE_ID_RE.match(rule["name"])
            if match:
                rule_ids.setdefault(match.group(1), []).append(path.name)
            walk(rule["children"], totals, names, rule_ids, path)
        elif "scenario" in child:
            scenario = child["scenario"]
            totals["scenarios"] += 1
            names[scenario["name"]] += 1
            examples = scenario.get("examples", [])
            if examples:
                totals["cases"] += sum(len(e.get("tableBody", [])) for e in examples)
            else:
                totals["cases"] += 1


def main() -> int:
    problems: list[str] = []
    totals: Counter[str] = Counter()
    rule_ids: dict[str, list[str]] = {}
    per_feature: list[tuple[str, Counter[str]]] = []

    files = sorted(SPEC.glob("*/*.feature"))
    if not files:
        print(f"no .feature files found under {SPEC}/")
        return 1

    for path in files:
        try:
            document = Parser().parse(path.read_text(encoding="utf-8"))
        except CompositeParserException as error:
            problems.append(f"{path}: not valid Gherkin: {error}")
            continue
        feature = document.get("feature")
        if not feature:
            problems.append(f"{path}: no Feature found")
            continue

        feature_id = path.name[:7]  # e.g. IAM-F01
        tags = {tag["name"] for tag in feature["tags"]}
        if f"@{feature_id}" not in tags:
            problems.append(f"{path}: feature tag @{feature_id} is missing")

        mine: Counter[str] = Counter()
        names: Counter[str] = Counter()
        walk(feature["children"], mine, names, rule_ids, path)
        for name, count in names.items():
            if count > 1:
                problems.append(
                    f"{path}: {count} scenarios are named {name!r}; names must be unique within a feature"
                )

        index = path.parent / "index.md"
        if not index.exists() or path.name not in index.read_text(encoding="utf-8"):
            problems.append(f"{path}: not linked from {index}")

        totals["features"] += 1
        totals.update(mine)
        per_feature.append((path.name, mine))

    for rule_id, where in sorted(rule_ids.items()):
        if len(where) > 1:
            problems.append(f"rule ID {rule_id} is used {len(where)} times: {', '.join(where)}")

    for name, mine in per_feature:
        print(f"{name[:7]}  rules={mine['rules']:<3} scenarios={mine['scenarios']:<3} cases={mine['cases']}")
    found = (totals["features"], totals["rules"], totals["scenarios"], totals["cases"])
    print("total    features=%d rules=%d scenarios=%d cases=%d" % found)

    index_text = (SPEC / "index.md").read_text(encoding="utf-8") if (SPEC / "index.md").exists() else ""
    recorded = COUNTS_RE.search(index_text)
    if not recorded:
        problems.append(f"{SPEC}/index.md: the spec-counts line is missing")
    elif tuple(int(n) for n in recorded.groups()) != found:
        problems.append(
            f"{SPEC}/index.md records features=%s rules=%s scenarios=%s cases=%s, " % recorded.groups()
            + "but the feature files contain features=%d rules=%d scenarios=%d cases=%d" % found
        )

    for problem in problems:
        print("PROBLEM:", problem)
    print("spec check:", "FAILED" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
