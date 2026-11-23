---
name: try-yc-report
description: Use to start the real YC daily report app and use it the way a person would (sign in, see a page, sign out), and to capture evidence of it. For verifying a change, writing "how to try it" steps, or looking at a page.
---

# Try YC report

## Surface

1. **Web pages** in a browser (server-rendered HTML with HTMX): `/sign-in`,
   `/reports` (USER), `/review` and `/status` (ADMIN, OWNER), `/health`.
2. **Commands**: `python -m app check-config | migrate | serve | create-owner | seed-demo`.

## Run

Once per checkout (Python 3.13; keep the environment outside tracked files,
`.venv/` is ignored):

```sh
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Then one command starts everything, from the repository root:

```sh
.venv/bin/python .claude/skills/try-yc-report/try.py --evidence docs/tasks/<slug>/evidence/<what-you-did>
```

It creates an empty database (on `TEST_DATABASE_URL` if set; otherwise it
starts a throwaway PostgreSQL from the local binaries, as the tests do, also
when run as root), runs `migrate` and `seed-demo`, starts `python -m app
serve` on a free port, and drives it. It drives only the server it started,
stops it, waits for it to exit, and exits non-zero when a step fails.

- `--group admin --name Admin1`: act as someone else. The demo accounts are
  the nine of `docs/spec/background.md` (`Old` is archived); the password of
  all of them is printed by `seed-demo` (`app/accounts/demo.py`).
- `--port 8000`: a fixed port; the script fails if it is taken.
- `--keep`: after the browser run, leave the server up at the printed address
  until Ctrl-C, to drive it yourself.

To run the app against your own database instead, follow `README.md`.

## Drive

- **Sign in and sign out**: what `try.py` does, through
  `tests/browser/smoke.cjs` (Node's Playwright and Chromium, found through
  `NODE_PATH` and `PLAYWRIGHT_BROWSERS_PATH`; this environment has them under
  `/opt/node-tools/node_modules` and `/opt/pw-browsers`, do not install
  others). To do more in the browser, copy that script and extend it; it reads
  `BASE_URL`, `GROUP`, `NAME`, `PASSWORD` and `SCREENSHOT_DIR`.
- **Any other request**: with `--keep`, plain HTTP against the printed
  address. Sign in with `POST /sign-in` (form fields `group`, `name`,
  `password`), keep the `session` cookie, and send the page's `csrf_token`
  with every request that is not a GET (header `X-CSRF-Token` or form field
  `csrf_token`). With `Accept: application/json` a refusal answers
  `{"outcome": ..., "message": ...}`.
- **Try the idle timeout**: start the app yourself with
  `CLOCK_OFFSET_MINUTES` (see `README.md`).
- **Create the owner**: `python -m app create-owner` on a database with no
  owner; it asks for the name and the password on the terminal.

## Observe

`--evidence <dir>` writes one screenshot per step (`1-sign-in-page.png` …
`5-landing-page-asks-to-sign-in-again.png`) and `transcript.txt` (the steps
that held, and the exit status). Keep them under
`docs/tasks/<slug>/evidence/`. For HTTP requests, keep the command and the
response.

## Known limits

- The container image cannot be built or run where there is no Docker daemon;
  the image job of the CI workflow does that.
- Nothing here looks at how a page looks; a person judges that from the
  screenshots.
- `create-owner` needs a terminal; the suite drives it through a pseudo-terminal
  (`tests/unit/test_commands.py`).
