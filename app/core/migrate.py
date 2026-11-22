"""Apply migrations/NNNN_name.sql, forward only, once each."""

import hashlib
import re
from pathlib import Path

import psycopg

from app.core.clock import Clock

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
FILE_NAME = re.compile(r"^(\d{4})_[a-z0-9_]+\.sql$")
# Any constant works, as long as every process migrating this database uses the same one.
ADVISORY_LOCK_KEY = 7_203_001


class MigrationError(Exception):
    pass


def _files(directory: Path) -> dict[int, Path]:
    found: dict[int, Path] = {}
    for path in sorted(directory.glob("*.sql")):
        match = FILE_NAME.match(path.name)
        if match is None:
            raise MigrationError(f"migration 檔名不合規則（NNNN_name.sql）：{path.name}")
        version = int(match.group(1))
        if version in found:
            raise MigrationError(f"migration 版本重複：{found[version].name}、{path.name}")
        found[version] = path
    return found


def migrate(database_url: str, clock: Clock, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply every pending file in order and return the names applied.

    Holds an advisory lock for the whole run, so processes starting together
    apply each file once. Refuses to continue when an applied file is missing
    or changed, or when a pending file is older than an applied one.
    """
    files = _files(directory)
    hashes = {v: hashlib.sha256(p.read_bytes()).hexdigest() for v, p in files.items()}
    applied_now: list[str] = []

    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("select pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        conn.execute(
            """
            create table if not exists schema_migrations (
                version integer primary key,
                filename text not null,
                sha256 text not null,
                applied_at timestamptz not null
            )
            """
        )
        applied = {
            version: (filename, sha256)
            for version, filename, sha256 in conn.execute(
                "select version, filename, sha256 from schema_migrations"
            )
        }

        for version, (filename, sha256) in sorted(applied.items()):
            if version not in files:
                raise MigrationError(f"已套用的 migration 不見了：{filename}")
            if files[version].name != filename or hashes[version] != sha256:
                raise MigrationError(f"已套用的 migration 內容被改過：{filename}")

        newest = max(applied, default=0)
        pending = [v for v in sorted(files) if v not in applied]
        for version in pending:
            if version < newest:
                raise MigrationError(
                    f"migration 只能往前：{files[version].name} 比已套用的版本 {newest:04d} 舊"
                )

        for version in pending:
            path = files[version]
            with conn.transaction():
                conn.execute(path.read_bytes())
                conn.execute(
                    "insert into schema_migrations (version, filename, sha256, applied_at)"
                    " values (%s, %s, %s, %s)",
                    (version, path.name, hashes[version], clock.now()),
                )
            applied_now.append(path.name)

    return applied_now
