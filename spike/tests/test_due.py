"""Which archives are due, decided from the clock alone (no database)."""
from datetime import date, datetime, timezone

from spike_jobs.clock import FixedClock
from spike_jobs.due import due_archives


def due(at, first=None, daily=None, monthly=None):
    last = {}
    if daily:
        last["daily"] = date.fromisoformat(daily)
    if monthly:
        last["monthly"] = date.fromisoformat(monthly)
    now = at if isinstance(at, datetime) else FixedClock(at).now()
    return [
        (kind, d.isoformat())
        for kind, d in due_archives(now, first and date.fromisoformat(first), last)
    ]


def test_nothing_is_due_one_second_before_2359():
    assert due("2026-11-15T23:58:59", first="2026-11-01", daily="2026-11-14") == []


def test_daily_archive_is_due_when_the_clock_reaches_2359():
    assert due("2026-11-15T23:59:00", first="2026-11-01", daily="2026-11-14") == [
        ("daily", "2026-11-15")
    ]


def test_2359_is_taipei_time_whatever_zone_the_instant_is_expressed_in():
    utc = datetime(2026, 11, 15, 15, 59, tzinfo=timezone.utc)  # 23:59 in Taipei
    assert due(utc, first="2026-11-01", daily="2026-11-14") == [("daily", "2026-11-15")]
    one_minute_earlier = datetime(2026, 11, 15, 15, 58, tzinfo=timezone.utc)
    assert due(one_minute_earlier, first="2026-11-01", daily="2026-11-14") == []


def test_month_is_archived_on_its_last_day():
    assert due("2026-11-30T23:59:00", first="2026-11-01", daily="2026-11-29") == [
        ("daily", "2026-11-30"),
        ("monthly", "2026-11-30"),
    ]


def test_february_ends_on_the_28th_in_2027():
    assert due(
        "2027-02-28T23:59:00", first="2026-11-01", daily="2027-02-27", monthly="2027-01-31"
    ) == [("daily", "2027-02-28"), ("monthly", "2027-02-28")]


def test_february_ends_on_the_29th_in_leap_year_2028():
    history = dict(first="2026-11-01", monthly="2028-01-31")
    assert due("2028-02-28T23:59:00", daily="2028-02-27", **history) == [
        ("daily", "2028-02-28")
    ]
    assert due("2028-02-29T23:59:00", daily="2028-02-28", **history) == [
        ("daily", "2028-02-29"),
        ("monthly", "2028-02-29"),
    ]


def test_a_trigger_that_fires_after_midnight_archives_the_day_that_ended():
    assert due("2026-11-16T00:07:00", first="2026-11-01", daily="2026-11-14") == [
        ("daily", "2026-11-15")
    ]


def test_after_days_of_downtime_every_missed_date_is_due_oldest_first():
    assert due(
        "2026-12-02T08:00:00", first="2026-11-01", daily="2026-11-27", monthly="2026-10-31"
    ) == [
        ("daily", "2026-11-28"),
        ("daily", "2026-11-29"),
        ("daily", "2026-11-30"),
        ("monthly", "2026-11-30"),
        ("daily", "2026-12-01"),
    ]


def test_first_month_end_is_due_even_though_no_monthly_archive_exists_yet():
    assert due("2026-12-02T08:00:00", first="2026-11-20", daily="2026-11-29") == [
        ("daily", "2026-11-30"),
        ("monthly", "2026-11-30"),
        ("daily", "2026-12-01"),
    ]


def test_a_fresh_install_starts_with_the_latest_due_date_and_does_not_backfill():
    assert due("2026-11-21T10:00:00") == [("daily", "2026-11-20")]
    assert due("2026-12-01T10:00:00") == [("daily", "2026-11-30"), ("monthly", "2026-11-30")]
