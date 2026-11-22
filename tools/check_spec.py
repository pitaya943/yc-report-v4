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
    case counts, and every bold totals row;
  * a sentence in a living document states a total in one of the checked
    wordings and the number is wrong. The wordings are listed in
    TOTAL_WORDINGS below; "N 個 feature" on its own is one of them, so a
    count of some features belongs in a table or is written without a digit;
  * the spec says "已開啟 N 條" and N is not the number of rule IDs listed in
    tests/implemented_rules.txt, or that list names a rule the spec lacks;
  * the spec states how many definitions (AD-n) it has and the number is not
    the number of rows in docs/spec/definitions.md;
  * a table that lists most of the features leaves one out.

Records of a moment are not checked for totals, because they say what was
true when they were written and must stay as written when the spec grows:
each task's brief.md, plan.md, tickets/ and reports/, and
spec-baseline-diff.md. Every other
Markdown file in the repository is a living document and is checked.

The wordings are a list, not a proof: a total written in a wording that is
not on the list is not caught. The rule that keeps this small is in
docs/spec/conventions.md: the totals are written only in docs/spec/index.md.

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
# "共 N 個領域、N 個 feature、N 條規則、N 個 scenario、N 個例子"
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
# "| | **合計** | **N** | **N** | **N** | **N** | |": features, rules, scenarios, cases
TOTALS_ROW_RE = re.compile(
    r"\*\*合計\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\* \| \*\*(\d+)\*\*"
)


IMPLEMENTED = Path("tests/implemented_rules.txt")
# Wordings that state a total of the whole spec, and which total each states.
TOTAL_WORDINGS = [
    (re.compile(r"(\d+) 條規則中"), ("rules",)),
    (re.compile(r"全部 (\d+) 條(?:規則|都在)"), ("rules",)),
    (re.compile(r"規格有 (\d+) 條規則"), ("rules",)),
    (re.compile(r"(?:共有?|總共) ?(\d+) 條規則"), ("rules",)),
    (re.compile(r"全部 (\d+) 個例子"), ("cases",)),
    (re.compile(r"(?:共有?|總共) ?(\d+) 個例子"), ("cases",)),
    (re.compile(r"(?:全部|共有?|總共) ?(\d+) 個 scenario"), ("scenarios",)),
    # On its own, with or without 全部 in front: features are never counted in
    # prose outside the spec's front page.
    (re.compile(r"(\d+) 個 feature(?!、)"), ("features",)),
    (re.compile(r"(?<!共 )(\d+) 個領域"), ("areas",)),
    # The same in English, as tickets and code comments write it.
    (re.compile(r"\b(\d+) feature files\b"), ("features",)),
    (re.compile(r"\ball (\d+) features\b"), ("features",)),
    (re.compile(r"\ball (\d+) rules\b"), ("rules",)),
    (re.compile(r"\ball (\d+) scenarios\b"), ("scenarios",)),
    (re.compile(r"\ball (\d+) cases\b"), ("cases",)),
    (
        re.compile(r"(\d+) 個 feature、(\d+) 條規則、(\d+) 個 scenario、(\d+) 個(?:可執行的)?例子"),
        ("features", "rules", "scenarios", "cases"),
    ),
]
OPEN_RULES_RE = re.compile(r"已開啟 (\d+) 條")
# The spec's own definitions (AD-1, AD-2, ...) are counted from the rows of
# definitions.md; these wordings state how many there are.
DEFINITIONS = SPEC / "definitions.md"
DEFINITION_ROW_RE = re.compile(r"^\| AD-\d+ \|", re.M)
DEFINITION_WORDINGS = [
    re.compile(r"(\d+) 條定義"),
    re.compile(r"已同意的 (\d+) 條規則"),
    re.compile(r"同意全部 (\d+) 條"),
    re.compile(r"有 (\d+) 個地方"),
    re.compile(r"定義的 (\d+) 條規則"),
    # The range of their IDs, as in "AD-1–AD-13".
    re.compile(r"AD-1–AD-(\d+)"),
]


def is_record(path: Path) -> bool:
    """A record says what was true when it was written; its totals are not checked."""
    parts = path.parts
    return (
        path.name in ("brief.md", "plan.md", "spec-baseline-diff.md")
        or "reports" in parts
        or "tickets" in parts
    )


def living_documents() -> list[Path]:
    """Every Markdown file in the repository that is not a record of a moment."""
    skipped = {".git", ".venv", "node_modules", "worktrees"}
    return [
        path
        for path in sorted(Path(".").rglob("*.md"))
        if not skipped.intersection(path.parts) and not is_record(path)
    ]


def check_sentences(found, rule_ids, problems):
    """Totals stated in prose, and the count of rules the spec says are built."""
    totals = dict(zip(("features", "rules", "scenarios", "cases"), found))
    totals["areas"] = len({path.parent.name for path in SPEC.glob("*/*.feature")})
    definitions = (
        len(DEFINITION_ROW_RE.findall(DEFINITIONS.read_text(encoding="utf-8"))) if DEFINITIONS.exists() else 0
    )
    for path in sorted(SPEC.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        for wording in DEFINITION_WORDINGS:
            for match in wording.finditer(text):
                if int(match.group(1)) != definitions:
                    problems.append(
                        f"{path}: 「{match.group(0)}」 states {match.group(1)} definitions, "
                        f"but {DEFINITIONS} has {definitions} rows"
                    )
    for path in living_documents():
        text = path.read_text(encoding="utf-8")
        for wording, names in TOTAL_WORDINGS:
            for match in wording.finditer(text):
                for name, written in zip(names, match.groups()):
                    if int(written) != totals[name]:
                        problems.append(
                            f"{path}: 「{match.group(0)}」 states {written} {name}, "
                            f"but the feature files contain {totals[name]}"
                        )

    built: list[str] = []
    if IMPLEMENTED.exists():
        built = [
            line.strip()
            for line in IMPLEMENTED.read_text(encoding="utf-8").splitlines()
            # Same reading as tests/support/spec.py: strip first, then skip
            # blank lines and comments, indented ones included.
            if line.strip() and not line.strip().startswith("#")
        ]
    for rule_id in built:
        if rule_id not in rule_ids:
            problems.append(f"{IMPLEMENTED}: {rule_id} is listed as built but no rule in the spec has that ID")
    stated = [
        (path, int(match.group(1)))
        for path in sorted(SPEC.rglob("*.md"))
        for match in OPEN_RULES_RE.finditer(path.read_text(encoding="utf-8"))
    ]
    if built and not stated:
        problems.append(f"{SPEC}/index.md: {len(built)} rules are listed as built but the spec does not say how many are")
    for path, written in stated:
        if written != len(set(built)):
            problems.append(
                f"{path}: says 已開啟 {written} 條, but {IMPLEMENTED} lists {len(set(built))} rules"
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
        # A table that lists most features is meant to list them all.
        if len(sums) > len(actual) / 2:
            for feature_id in sorted(set(actual) - set(sums)):
                problems.append(f"{path}: lists {len(sums)} of the {len(actual)} features; {feature_id} is missing")
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
    check_sentences(found, rule_ids, problems)

    for problem in problems:
        print("PROBLEM:", problem)
    print("spec check:", "FAILED" if problems else "ok")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
