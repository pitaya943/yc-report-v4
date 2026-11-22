import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core.clock import TAIPEI, SystemClock
from tests.support.cli import REPO
from tests.support.time_sources import find_time_reads

APP = REPO / "app"
CLOCK_MODULE = frozenset({Path("core/clock.py")})


def test_system_clock_is_aware_in_taipei_and_tells_the_real_time():
    before = datetime.now(timezone.utc)
    now = SystemClock().now()
    after = datetime.now(timezone.utc)

    assert now.tzinfo is TAIPEI
    assert now.utcoffset() == timedelta(hours=8)
    assert before <= now <= after


def test_system_clock_honours_the_offset():
    before = datetime.now(timezone.utc)
    now = SystemClock(offset_minutes=90).now()
    after = datetime.now(timezone.utc)

    assert now.tzinfo is TAIPEI
    assert before + timedelta(minutes=90) <= now <= after + timedelta(minutes=90)


def test_only_the_clock_module_reads_the_time():
    assert find_time_reads(APP, allowed=CLOCK_MODULE) == []


def test_migrations_use_no_database_time_function():
    assert find_time_reads(REPO / "migrations") == []


@pytest.mark.parametrize(
    ("line", "what"),
    [
        ("stamp = datetime.now()", "datetime.now"),
        ("stamp = datetime.datetime.now(tz)", "datetime.now"),
        ("stamp = datetime.utcnow()", "datetime.utcnow"),
        ("day = date.today()", "date.today"),
        ("seconds = time.time()", "time.time"),
        ('conn.execute("update t set at = now()")', "SQL now()"),
        ('conn.execute("update t set at = NOW ( )")', "SQL now()"),
        ('conn.execute("insert into t (at) values (current_timestamp)")', "SQL current_timestamp"),
        ('conn.execute("insert into t (at) values (CURRENT_TIMESTAMP)")', "SQL current_timestamp"),
    ],
)
def test_a_time_read_added_anywhere_else_under_app_is_found(tmp_path, line, what):
    copy = tmp_path / "app"
    shutil.copytree(APP, copy, ignore=shutil.ignore_patterns("__pycache__"))
    (copy / "system" / "sneaky.py").write_text(f"import datetime\n{line}\n", encoding="utf-8")

    assert find_time_reads(copy, allowed=CLOCK_MODULE) == [f"system/sneaky.py:2: {what}"]


def test_reading_the_clock_through_its_interface_is_not_flagged(tmp_path):
    (tmp_path / "service.py").write_text("moment = clock.now()\n", encoding="utf-8")
    assert find_time_reads(tmp_path) == []
