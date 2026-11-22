"""Finds code that reads the time anywhere but through the Clock."""

import re
from pathlib import Path

FORBIDDEN = {
    "datetime.now": re.compile(r"\bdatetime\.now\b"),
    "datetime.utcnow": re.compile(r"\butcnow\b"),
    "date.today": re.compile(r"\bdate\.today\b"),
    "time.time": re.compile(r"\btime\.time(_ns)?\b"),
    # SQL now(), but not clock.now().
    "SQL now()": re.compile(r"(?<![.\w])now\s*\(\s*\)", re.IGNORECASE),
    "SQL current_timestamp": re.compile(
        r"\b(current_timestamp|current_date|current_time|localtimestamp|localtime"
        r"|clock_timestamp|statement_timestamp|transaction_timestamp)\b",
        re.IGNORECASE,
    ),
}
TEXT_SUFFIXES = {".py", ".sql", ".html", ".txt", ".js"}


def find_time_reads(root: Path, *, allowed: frozenset[Path] = frozenset()) -> list[str]:
    """``path:line: what`` for every forbidden time read under ``root``.

    ``allowed`` holds paths relative to ``root`` that may read the time.
    """
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES or relative in allowed:
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for what, pattern in FORBIDDEN.items():
                if pattern.search(line):
                    found.append(f"{relative}:{number}: {what}")
    return found
