"""Finds code that reads the time anywhere but through the Clock."""

import re
from pathlib import Path

_SQL_FUNCTIONS = (
    "current_timestamp|current_date|current_time|localtimestamp|localtime"
    "|clock_timestamp|statement_timestamp|transaction_timestamp|timeofday"
)

FORBIDDEN = {
    "datetime.now": re.compile(r"\bdatetime\.now\b"),
    "datetime.utcnow": re.compile(r"\butcnow\b"),
    "datetime.today": re.compile(r"\bdatetime\.today\b"),
    "date.today": re.compile(r"\bdate\.today\b"),
    # Whatever name the class was imported under: dt.now(), d.today().
    "now() on something other than the clock": re.compile(r"(?<!clock)(?<!datetime)\.now\s*\("),
    "today() on something other than date": re.compile(r"(?<!date)(?<!datetime)\.today\s*\("),
    "time.time": re.compile(r"\btime\.time(_ns)?\b"),
    "time.monotonic": re.compile(r"\btime\.(monotonic|perf_counter|process_time)(_ns)?\b"),
    "time.localtime": re.compile(r"\btime\.(localtime|gmtime|ctime|asctime|strftime)\b"),
    # Its functions would then be called by their bare names.
    "from time import": re.compile(r"\bfrom\s+time\s+import\b"),
    # SQL now(), but not clock.now().
    "SQL now()": re.compile(r"(?<![.\w])now\s*\(\s*\)", re.IGNORECASE),
    # Not after a dot: time.localtime is Python's.
    "SQL current_timestamp": re.compile(rf"(?<!\.)\b({_SQL_FUNCTIONS})\b", re.IGNORECASE),
    # The special input strings: 'now'::timestamptz, date 'today'.
    "SQL 'now'": re.compile(r"'(now|today|tomorrow|yesterday)'", re.IGNORECASE),
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
