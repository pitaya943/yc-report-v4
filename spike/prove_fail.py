"""Break each behaviour on purpose and show that its test fails.

For every entry below: apply the edits, run the named tests, require that each
of them FAILS on an assertion or an error raised by the code under test, then
restore the files. Exit status 0 means every break was caught.

    python prove_fail.py            # all
    python prove_fail.py guard      # only entries whose name contains "guard"
"""
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
DUE = "spike_jobs/due.py"
JOBS = "spike_jobs/jobs.py"
SCHEMA = "spike_jobs/schema.sql"
TRIGGER = "spike_jobs/trigger.py"
APP = "spike_jobs/app.py"
COMMON = "spike_exports/common.py"
PDF = "spike_exports/payroll_pdf.py"
DOCX = "spike_exports/bank_docx.py"

ON_CONFLICT = '        " ON CONFLICT (kind, period_date) WHERE automatic DO NOTHING"\n'
INSERT_START = '    row = conn.execute(\n        "INSERT INTO archive'
CHECK_THEN_INSERT = (
    "    if conn.execute(\n"
    '        "SELECT 1 FROM archive WHERE automatic AND kind = %s AND period_date = %s",\n'
    "        (kind, period_date),\n"
    "    ).fetchone():\n"
    "        return False\n" + INSERT_START
)
UNIQUE_INDEX = "CREATE UNIQUE INDEX archive_one_automatic ON archive (kind, period_date) WHERE automatic;"
NO_GUARD = [
    (SCHEMA, UNIQUE_INDEX, ""),
    (JOBS, ON_CONFLICT, ""),
    (JOBS, INSERT_START, CHECK_THEN_INSERT),
]

# (name, edits [(file, old, new)], tests that must fail, how many runs)
BREAKS = [
    ("due: the day counts as ended before 23:59",
     [(DUE, "return local.date() - timedelta(days=1)", "return local.date()")],
     ["test_due.py::test_nothing_is_due_one_second_before_2359",
      "test_due.py::test_a_trigger_that_fires_after_midnight_archives_the_day_that_ended"], 1),
    ("due: 23:59 read in the instant's own zone, not Taipei",
     [(DUE, "local = now.astimezone(TAIPEI)", "local = now")],
     ["test_due.py::test_2359_is_taipei_time_whatever_zone_the_instant_is_expressed_in"], 1),
    ("due: month end fixed at the 28th or later",
     [(DUE, "return d.day == monthrange(d.year, d.month)[1]", "return d.day >= 28")],
     ["test_due.py::test_month_is_archived_on_its_last_day",
      "test_due.py::test_february_ends_on_the_29th_in_leap_year_2028",
      "test_jobs_db.py::test_leap_year_month_end_is_archived_on_29_february"], 1),
    ("due: February always ends on the 28th",
     [(DUE, "return d.day == monthrange(d.year, d.month)[1]",
       "return d.day == (28 if d.month == 2 else monthrange(d.year, d.month)[1])")],
     ["test_due.py::test_february_ends_on_the_29th_in_leap_year_2028",
      "test_jobs_db.py::test_leap_year_month_end_is_archived_on_29_february"], 1),
    ("due: February never ends on the 28th",
     [(DUE, "return d.day == monthrange(d.year, d.month)[1]",
       "return d.day == (29 if d.month == 2 else monthrange(d.year, d.month)[1])")],
     ["test_due.py::test_february_ends_on_the_28th_in_2027"], 1),
    ("due: no catch-up, only the latest date",
     [(DUE, "start = first_archived or latest", "start = latest")],
     ["test_due.py::test_after_days_of_downtime_every_missed_date_is_due_oldest_first",
      "test_jobs_db.py::test_app_down_at_2359_for_several_days_catches_up_every_missed_date"], 1),
    ("due: a fresh install back-fills from a fixed date",
     [(DUE, "start = first_archived or latest", "start = first_archived or date(2026, 11, 1)")],
     ["test_due.py::test_a_fresh_install_starts_with_the_latest_due_date_and_does_not_backfill"], 1),
    ("due: monthly needs an earlier monthly archive",
     [(DUE, "if is_month_end(d) and d > last_archived.get(MONTHLY, date.min):",
       "if is_month_end(d) and MONTHLY in last_archived and d > last_archived[MONTHLY]:")],
     ["test_due.py::test_first_month_end_is_due_even_though_no_monthly_archive_exists_yet"], 1),
    ("jobs: archive time taken from the system clock",
     [(JOBS, "        (kind, period_date, now),\n",
       "        (kind, period_date, datetime.now().astimezone()),\n")],
     ["test_jobs_db.py::test_archive_is_created_when_the_clock_reaches_2359"], 1),
    ("jobs: nothing remembers what was archived (no guard, no history check)",
     NO_GUARD + [(DUE, "if d > last_archived.get(DAILY, date.min):", "if True:"),
                 (JOBS, CHECK_THEN_INSERT.split(INSERT_START)[0], "")],
     ["test_jobs_db.py::test_running_again_after_a_restart_does_not_duplicate"], 1),
    ("jobs: row committed before its content is built",
     [(JOBS, "        with conn.transaction():\n", "        if True:\n")],
     ["test_jobs_db.py::test_a_crash_while_building_leaves_nothing_and_the_next_run_completes_it"], 1),
    ("guard removed: check-then-insert without the unique index (20 runs)",
     NO_GUARD,
     ["test_jobs_db.py::test_two_workers_in_overlapping_transactions_produce_exactly_one_archive"], 20),
    ("guard removed: eight workers at the same instant (not deterministic; 5 runs)",
     NO_GUARD,
     ["test_jobs_db.py::test_eight_workers_released_at_the_same_instant_produce_one_archive_each_round"], 5),
    ("guard covers manual archives too",
     [(SCHEMA, "(kind, period_date) WHERE automatic;", "(kind, period_date);"),
      (JOBS, "(kind, period_date) WHERE automatic DO NOTHING", "(kind, period_date) DO NOTHING")],
     ["test_jobs_db.py::test_a_manual_archive_for_the_same_date_does_not_replace_the_automatic_one"], 1),
    ("sessions: one expiring exactly now is kept",
     [(JOBS, "expires_at <= %s", "expires_at < %s")],
     ["test_jobs_db.py::test_expired_sessions_are_deleted_and_live_ones_kept"], 1),
    ("tick: session cleanup left out",
     [(JOBS, "        delete_expired_sessions(conn, clock)\n", "")],
     ["test_jobs_db.py::test_one_tick_runs_both_the_archives_and_the_session_cleanup"], 1),
    ("trigger: a failing tick ends the loop",
     [(TRIGGER, "except Exception:", "except ZeroDivisionError:")],
     ["test_trigger.py::test_the_loop_keeps_ticking_after_a_tick_fails"], 1),
    ("app: server processes do not run the loop",
     [(APP, "run_forever(lambda: tick(database_url, clock), interval)", "asyncio.sleep(3600)")],
     ["test_trigger.py::test_two_real_server_processes_and_a_restart_make_one_archive"], 1),
    ("command: one-shot command does nothing",
     [("spike_jobs/__main__.py", 'tick(os.environ["DATABASE_URL"], SystemClock())', "tick")],
     ["test_trigger.py::test_the_one_shot_command_runs_a_tick_on_the_system_clock"], 1),
    ("pdf: portrait instead of landscape",
     [(PDF, "pagesize=landscape(A4)", "pagesize=A4")],
     ["test_exports.py::test_pdf_is_one_a4_landscape_page"], 1),
    ("pdf: table drawn in Helvetica (no Chinese glyphs)",
     [(PDF, '("FONT", (0, 0), (-1, -1), FONT_NAME, 11)', '("FONT", (0, 0), (-1, -1), "Helvetica", 11)')],
     ["test_exports.py::test_pdf_text_read_back_matches_the_chinese_and_the_amounts"], 1),
    ("pdf: built-in CID font, not embedded",
     [(PDF, "pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))",
       "from reportlab.pdfbase.cidfonts import UnicodeCIDFont; pdfmetrics.registerFont(UnicodeCIDFont(FONT_NAME))"),
      (COMMON, 'FONT_NAME = "NotoSansTC"', 'FONT_NAME = "MSung-Light"')],
     ["test_exports.py::test_pdf_carries_its_own_chinese_font"], 1),
    ("amounts: no thousands separators",
     [(COMMON, 'return f"{amount:,}"', 'return f"{amount}"')],
     ["test_exports.py::test_pdf_text_read_back_matches_the_chinese_and_the_amounts",
      "test_exports.py::test_docx_text_read_back_matches_the_chinese_and_the_amounts"], 1),
    ("amounts: minus sign dropped",
     [(COMMON, 'return f"{amount:,}"', 'return f"{abs(amount):,}"')],
     ["test_exports.py::test_pdf_text_read_back_matches_the_chinese_and_the_amounts",
      "test_exports.py::test_docx_text_read_back_matches_the_chinese_and_the_amounts"], 1),
    ("docx: names forced to ASCII",
     [(DOCX, "add_row([str(n), row.account_no, row.name], row.amount)",
       'add_row([str(n), row.account_no, row.name.encode("ascii", "replace").decode()], row.amount)')],
     ["test_exports.py::test_docx_text_read_back_matches_the_chinese_and_the_amounts",
      "test_exports.py::test_docx_xml_itself_contains_the_chinese_text"], 1),
    ("docx: East Asian font not set",
     [(DOCX, '    run._element.rPr.rFonts.set(qn("w:eastAsia"), EAST_ASIAN_FONT)\n', "")],
     ["test_exports.py::test_docx_asks_for_a_chinese_font_on_every_run_and_marks_negatives_red"], 1),
    ("docx: negative amounts not red",
     [(DOCX, "red=amount < 0", "red=False")],
     ["test_exports.py::test_docx_asks_for_a_chinese_font_on_every_run_and_marks_negatives_red"], 1),
    ("docx: landscape page",
     [(DOCX, "Mm(210), Mm(297)", "Mm(297), Mm(210)")],
     ["test_exports.py::test_docx_page_is_a4_portrait"], 1),
]


def run_break(name, edits, tests, runs):
    originals = {}
    try:
        for file, old, new in edits:
            path = HERE / file
            originals.setdefault(path, path.read_text())
            text = path.read_text()
            if text.count(old) != 1:
                raise SystemExit(f"{name}: expected exactly one {old!r} in {file}")
            path.write_text(text.replace(old, new))
        failed_runs = 0
        for _ in range(runs):
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", "-rfE", "-p", "no:cacheprovider",
                 *(f"tests/{t}" for t in tests)],
                cwd=HERE, capture_output=True, text=True,
            )
            failed = set(re.findall(r"^FAILED tests/(\S+)", result.stdout, re.M))
            if "ERROR tests/" in result.stdout or "error" in result.stdout.splitlines()[-1]:
                raise SystemExit(f"{name}: setup error, not a test failure\n{result.stdout}")
            if failed == set(tests):
                failed_runs += 1
        return failed_runs
    finally:
        for path, text in originals.items():
            path.write_text(text)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ""
    missed = 0
    for name, edits, tests, runs in BREAKS:
        if only not in name:
            continue
        failed_runs = run_break(name, edits, tests, runs)
        deterministic = "not deterministic" not in name
        caught = failed_runs == runs if deterministic else failed_runs > 0
        missed += not caught
        print(f"{'caught' if caught else 'MISSED'}  {failed_runs}/{runs} runs failed  {name}")
    print("every break was caught" if not missed else f"{missed} break(s) NOT caught")
    sys.exit(1 if missed else 0)


if __name__ == "__main__":
    main()
