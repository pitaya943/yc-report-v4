# AGENTS.md

## Working with shilaycow

This repository uses the shilaycow harness. Its settings are in
`.shilaycow/`; read `.shilaycow/config.yml` before starting any work.

- **Only the owner merges `main`.** `main` changes only through a pull
  request that the owner (`pitaya943`) approves and merges. Agents act as the
  bot account (`bullet-bots`); they never push to `main`, never merge into it,
  and cannot approve their own pull requests.
- **Branch classes.**
  - `task/<slug>`: one task's integration branch. Its pull request into
    `main` is what the owner merges.
  - `work/<slug>/<ticket>`: a single ticket's work, merged into its task
    branch.
  - `spike/<name>`: throwaway experiments. Never merged.
- **Ask before what cannot be undone.** Repository settings, workflows,
  secrets, deploys, and paid or external calls need the owner: open an issue
  labelled `needs-owner` with the options and a recommendation.
