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
  * a number written anywhere under docs/ disagrees with the feature files:
    the totals in docs/spec/index.md (both the comment and the sentence a
    person reads), the per-area counts in its table, every table row that
    starts with a link to a feature file followed by its rule, scenario and
    case counts, and every bold totals row.

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
DOCS = Path("docs")
# "共 9 個領域、31 個 feature、137 條規則、254 個 scenario、502 個例子"
SENTENCE_RE = re.compile(
    r"共 (\d+) 個領域、(\d+) 個 feature、(\d+) 條規則、(\d+) 個 scenario、(\d+) 個例子"
)
# "| [身分與帳戶](accounts/index.md)（IAM） | 用途 | 7 | 53 |"
AREA_ROW_RE = re.compile(r"^\| \[[^\]]+\]\(([a-z]+)/index\.md\)[^|]*\|[^|]*\| (\d+) \| (\d+) \|", re.M)
# "| [IAM-F01 登入](IAM-F01-sign-in.feature)… | 3 | 4 | 10 |": a row may add a
# note after the link (for a feature split between tasks); the rows of one
# feature in one file must add up to the feature's real counts.
FEATURE_ROW_RE = re.compile(
    r"^\| \[([A-Z]{3}-F\d\d)[^\]]*\]\([^)]*\)[^|]*\| (\d+) \| (\d+) \| (\d+) \|", re.M
)
# "| | **合計** | **31** | **137** | **254** | **502** | |"
TOTALS_ROW_RE = re.compile(
    r"\*\*合計\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\*"
)


def check_written_numbers(per_feature, found, problems):
    """Compare every count written in the documents with the feature files."""
    actual = {path.name[:7]: (c["rules"], c["scenarios"], c["cases"]) for path, c in per_feature}
    by_area: dict[str, Counter[str]] = {}
    for path, counts in per_feature:
        area = by_area.setdefault(path.parent.name, Counter())
        area["features"] += 1
        area["scenarios"] += counts["scenarios"]

    index = SPEC / "index.md"
    text = index.read_text(encoding="utf-8") if index.exists() else ""
    sentence = SENTENCE_RE.search(text)
    if not sentence:
        problems.append(f"{index}: the sentence giving the totals is missing")
    else:
        written = tuple(int(n) for n in sentence.groups())
        if written != (len(by_area),) + found:
            problems.append(
                f"{index}: the sentence says areas=%d features=%d rules=%d scenarios=%d cases=%d, " % written
                + "but the feature files contain areas=%d features=%d rules=%d scenarios=%d cases=%d"
                % ((len(by_area),) + found)
            )
    listed = set()
    for area, features, scenarios in AREA_ROW_RE.findall(text):
        listed.add(area)
        real = by_area.get(area, Counter())
        if (int(features), int(scenarios)) != (real["features"], real["scenarios"]):
            problems.append(
                f"{index}: area {area} is listed with {features} features and {scenarios} scenarios, "
                f"but has {real['features']} and {real['scenarios']}"
            )
    for area in sorted(set(by_area) - listed):
        problems.append(f"{index}: area {area} is missing from the table of areas")

    for path in sorted(DOCS.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        sums: dict[str, list[int]] = {}
        for feature_id, rules, scenarios, cases in FEATURE_ROW_RE.findall(text):
            total = sums.setdefault(feature_id, [0, 0, 0])
            for i, value in enumerate((rules, scenarios, cases)):
                total[i] += int(value)
        for feature_id, total in sorted(sums.items()):
            if feature_id not in actual:
                problems.append(f"{path}: {feature_id} is listed but there is no such feature file")
            elif tuple(total) != actual[feature_id]:
                problems.append(
                    f"{path}: {feature_id} is listed with rules=%d scenarios=%d cases=%d, " % tuple(total)
                    + "but the feature file has rules=%d scenarios=%d cases=%d" % actual[feature_id]
                )
        for groups in TOTALS_ROW_RE.findall(text):
            if tuple(int(n) for n in groups) != found:
                problems.append(
                    f"{path}: a totals row says features=%s rules=%s scenarios=%s cases=%s, " % groups
                    + "but the feature files contain features=%d rules=%d scenarios=%d cases=%d" % found
                )



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
    per_feature: list[tuple[Path, Counter[str]]] = []

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
        per_feature.append((path, mine))

    for rule_id, where in sorted(rule_ids.items()):
        if len(where) > 1:
            problems.append(f"rule ID {rule_id} is used {len(where)} times: {', '.join(where)}")

    for path, mine in per_feature:
        print(f"{path.name[:7]}  rules={mine['rules']:<3} scenarios={mine['scenarios']:<3} cases={mine['cases']}")
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

    check_written_numbers(per_feature, found, problems)

    for problem in problems:
        print("PROBLEM:", problem)
    print("spec check:", "FAILED" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
