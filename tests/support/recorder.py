"""Snapshots of every table, and the difference between two of them.

This is how a test says "nothing is written" or "exactly this row was added".
"""

import json
from dataclasses import dataclass
from typing import Literal

import psycopg
from psycopg import sql

# Columns left out of every snapshot. Adding an entry is a design change
# (docs/tasks/skeleton-and-sign-in/design.md section 11.3).
#
# sessions.last_used_at: every signed-in request moves it; that is not what
# the spec means by "written".
IGNORED_COLUMNS: frozenset[tuple[str, str]] = frozenset({("sessions", "last_used_at")})

Snapshot = dict[str, dict[str, dict]]


@dataclass(frozen=True)
class Change:
    table: str
    kind: Literal["added", "changed", "deleted"]
    before: dict | None
    after: dict | None


def snapshot(database_url: str) -> Snapshot:
    """Every row of every table in the public schema, keyed by table and row identity."""
    result: Snapshot = {}
    with psycopg.connect(database_url) as conn:
        tables = [name for (name,) in conn.execute(
            "select tablename from pg_tables where schemaname = 'public' order by tablename"
        )]
        for table in tables:
            key_columns = [name for (name,) in conn.execute(
                """
                select a.attname
                from pg_index i
                join pg_attribute a on a.attrelid = i.indrelid and a.attnum = any(i.indkey)
                where i.indrelid = %s::regclass and i.indisprimary
                order by a.attnum
                """,
                (f'public."{table}"',),
            )]
            rows: dict[str, dict] = {}
            query = sql.SQL("select to_jsonb(t) from {} as t").format(sql.Identifier("public", table))
            for (row,) in conn.execute(query):
                for ignored_table, column in IGNORED_COLUMNS:
                    if ignored_table == table:
                        row.pop(column, None)
                # Without a primary key a row is identified by its whole content,
                # and identical rows by their count.
                identity = {c: row[c] for c in key_columns} if key_columns else row
                key = json.dumps(identity, sort_keys=True)
                if not key_columns:
                    key = f"{key}#{sum(1 for k in rows if k.startswith(key + '#'))}"
                rows[key] = row
            result[table] = rows
    return result


def diff(before: Snapshot, after: Snapshot) -> list[Change]:
    changes: list[Change] = []
    for table in sorted(before.keys() | after.keys()):
        old, new = before.get(table, {}), after.get(table, {})
        for key in sorted(old.keys() | new.keys()):
            if key not in old:
                changes.append(Change(table, "added", None, new[key]))
            elif key not in new:
                changes.append(Change(table, "deleted", old[key], None))
            elif old[key] != new[key]:
                changes.append(Change(table, "changed", old[key], new[key]))
    return changes
