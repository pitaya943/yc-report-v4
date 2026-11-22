import subprocess
import sys
from pathlib import Path

import psycopg
import pytest

from app.core.migrate import MigrationError, migrate
from tests.support.cli import REPO, app_environ, run_app


def write(directory: Path, name: str, sql: str) -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def query(database_url: str, sql: str) -> list[tuple]:
    with psycopg.connect(database_url) as conn:
        return conn.execute(sql).fetchall()


def applied(database_url: str) -> list[str]:
    return [name for (name,) in query(database_url, "select filename from schema_migrations order by version")]


@pytest.fixture
def directory(tmp_path: Path) -> Path:
    # The second file only works if the first ran before it.
    write(tmp_path, "0001_first.sql", "create table first (n integer); insert into first values (1);")
    write(tmp_path, "0002_second.sql", "create table second as select n + 1 as n from first;")
    return tmp_path


def test_pending_files_are_applied_once_in_order(empty_database, clock, directory):
    assert migrate(empty_database, clock, directory) == ["0001_first.sql", "0002_second.sql"]

    assert query(empty_database, "select n from second") == [(2,)]
    assert query(empty_database, "select version, filename, applied_at from schema_migrations order by version") == [
        (1, "0001_first.sql", clock.now()),
        (2, "0002_second.sql", clock.now()),
    ]


def test_running_again_changes_nothing(empty_database, clock, directory):
    migrate(empty_database, clock, directory)

    assert migrate(empty_database, clock, directory) == []
    assert query(empty_database, "select n from first") == [(1,)]
    assert applied(empty_database) == ["0001_first.sql", "0002_second.sql"]


def test_only_the_new_file_is_applied_later(empty_database, clock, directory):
    migrate(empty_database, clock, directory)
    write(directory, "0003_third.sql", "create table third (n integer);")

    assert migrate(empty_database, clock, directory) == ["0003_third.sql"]
    assert applied(empty_database) == ["0001_first.sql", "0002_second.sql", "0003_third.sql"]


def test_an_applied_file_whose_content_changed_is_refused(empty_database, clock, directory):
    migrate(empty_database, clock, directory)
    write(directory, "0001_first.sql", "create table first (n bigint);")
    write(directory, "0003_third.sql", "create table third (n integer);")

    with pytest.raises(MigrationError, match="0001_first.sql"):
        migrate(empty_database, clock, directory)
    assert applied(empty_database) == ["0001_first.sql", "0002_second.sql"]


def test_an_applied_file_that_disappeared_is_refused(empty_database, clock, directory):
    migrate(empty_database, clock, directory)
    (directory / "0002_second.sql").unlink()

    with pytest.raises(MigrationError, match="0002_second.sql"):
        migrate(empty_database, clock, directory)


def test_a_pending_file_older_than_an_applied_one_is_refused(empty_database, clock, tmp_path):
    write(tmp_path, "0002_second.sql", "create table second (n integer);")
    migrate(empty_database, clock, tmp_path)
    write(tmp_path, "0001_first.sql", "create table first (n integer);")

    with pytest.raises(MigrationError, match="0001_first.sql"):
        migrate(empty_database, clock, tmp_path)
    assert applied(empty_database) == ["0002_second.sql"]


def test_a_file_that_fails_leaves_nothing_of_itself_behind(empty_database, clock, directory):
    write(directory, "0003_broken.sql", "create table third (n integer); select 1 / 0;")

    with pytest.raises(psycopg.Error):
        migrate(empty_database, clock, directory)

    assert applied(empty_database) == ["0001_first.sql", "0002_second.sql"]
    assert query(empty_database, "select to_regclass('third')") == [(None,)]


def test_a_file_name_outside_the_pattern_is_refused(empty_database, clock, tmp_path):
    write(tmp_path, "first.sql", "create table first (n integer);")

    with pytest.raises(MigrationError, match="first.sql"):
        migrate(empty_database, clock, tmp_path)


def test_two_processes_migrating_together_apply_each_file_exactly_once(empty_database, tmp_path):
    # The sleep keeps the first process inside the migration while the second arrives.
    write(tmp_path, "0001_once.sql", "create table once (n integer); insert into once values (1); select pg_sleep(1.5);")
    script = (
        "import sys; from pathlib import Path;"
        "from app.core.clock import SystemClock; from app.core.migrate import migrate;"
        "migrate(sys.argv[1], SystemClock(), Path(sys.argv[2]))"
    )
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, empty_database, str(tmp_path)],
            cwd=REPO, env=app_environ(), stderr=subprocess.PIPE, text=True,
        )
        for _ in range(2)
    ]
    results = [(p.wait(timeout=60), p.stderr.read()) for p in processes]

    assert [code for code, _ in results] == [0, 0], results
    assert query(empty_database, "select n from once") == [(1,)]
    assert applied(empty_database) == ["0001_once.sql"]


def test_the_migrate_command_applies_the_project_migrations_and_is_repeatable(empty_database):
    first = run_app("migrate", DATABASE_URL=empty_database)
    second = run_app("migrate", DATABASE_URL=empty_database)

    assert (first.returncode, second.returncode) == (0, 0), first.stderr + second.stderr
    on_disk = sorted(path.name for path in (REPO / "migrations").glob("*.sql"))
    assert on_disk and applied(empty_database) == on_disk
    for name in on_disk:
        assert name in first.stdout and name not in second.stdout
