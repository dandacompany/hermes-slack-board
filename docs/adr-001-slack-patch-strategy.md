# ADR 001 — In-place `slack.py` patch vs. upstream Block Kit hook

- Status: Accepted
- Date: 2026-05-30
- Context version: Hermes Agent 0.15.1

## Context

The `/board` UI is installed by patching Hermes's git-tracked
`gateway/platforms/slack.py` in place (string-marker splices) plus copying an
untracked overlay module `gateway/platforms/slack_kanban_board.py`.

Hermes tracks `origin/main` and `hermes update` stashes local changes before
pulling, then offers a restore that conflicts (or is declined) across large
updates. So every update reverts the tracked-file patch while leaving the
untracked overlay orphaned. This is structural: it cannot be fixed by editing
`slack.py` more carefully.

## Decision

Keep the in-place patch for the 0.15.x cycle. Do **not** pivot to an upstream
Block Kit extension hook now.

Rationale:

- The patch surface is healthy on 0.15.1: all `slack.py` string markers and the
  `hermes_cli.kanban_db` API the overlay depends on survive the v0.15.0
  "Velocity Release" Kanban overhaul.
- An upstream extension hook is a large, upstream-dependency-bound effort with no
  guaranteed hook to target — a multi-release bet, not a hotfix.
- The structural weakness (`hermes update` reverting tracked files) is mitigated
  operationally: the installer is idempotent, and re-running it is the
  documented post-update step.

Design direction: keep shrinking the tracked-`slack.py` footprint, keep logic in
the untracked overlay (which survives updates, only going stale), and treat
re-install as the update contract.

## Consequences

- Users must re-run the installer after every `hermes update`
  (documented in `SKILL.md` and `references/troubleshooting.md`).
- Revisit the upstream-hook pivot if a future Hermes release breaks the markers
  or removes `kanban_db` symbols.

## Verification (2026-05-30, Hermes 0.15.1)

- The installer patch applies and `py_compile`s against real 0.15.1 `slack.py`
  on both the clean-install and re-install paths
  (`tests/test_install_patch.py`).
- A regression that produced a body-less duplicate `_handle_slash_confirm_action`
  (opaque `IndentationError` at install time) was removed, and the installer now
  asserts a single, bodied handler before writing.
- The bundled overlay test suite passes against 0.15.1 `kanban_db` (18 tests).
- 0.15.x added Kanban statuses (`scheduled`, `review`, `archived`); the board now
  renders a `Review` column and surfaces other column-less statuses as an
  `other` count instead of dropping them.
- `tests/test_install_patch.py` reads the local Hermes checkout
  (`HERMES_ROOT`, default `~/.hermes/hermes-agent`) and `pytest.skip`s when
  absent, so this coverage is local/dev-machine only — CI without a checkout
  skips it rather than failing.
