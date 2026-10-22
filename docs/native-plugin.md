# Native local plugin (Hermes v0.22.4)

## Supported runtime

Verified against Hermes v0.22.4, core commit
`4d04303818b6`, using its PM-managed launcher and Python 3.14 runtime.
`plugin.yaml` deliberately restricts loading to `>=0.22.4,<0.23` because the
renderer still uses some private Kanban helpers and SQL column names.
No Hermes core files need to be copied, patched, or monkey-patched.

## Exact installation procedure

For the default profile, from the repository checkout:

```sh
cd /path/to/hermes-slack-board
python3 scripts/install_plugin.py --home "$HOME/.hermes"
HERMES_HOME="$HOME/.hermes" hermes plugins enable slack-board
HERMES_HOME="$HOME/.hermes" hermes plugins doctor slack-board --ci
```

The copy destination is `$HOME/.hermes/plugins/slack-board/`.
Only `slack_board/` is copied: `__init__.py`, `controller.py`, `renderer.py`,
and `plugin.yaml`. The installer has no pip, config-write, service, or Slack API
operations. It refuses overwriting any existing destination, including a dangling
symlink. Do not use the old overlay installer on this runtime.

For a named profile, deliberately choose its exact profile home for **all three**
commands. Never infer another profile from an assignee or a Slack payload.

Hermes' `plugins install` is a Git/catalog path, not a local-directory copier in
this release; the copy installer is intentional. For development a manually
created `plugins/slack-board` symlink pointing at the repository's `slack_board`
directory also works, but the installer itself always makes a copy.

On v0.22.4, enabling a newly installed plugin asks the running gateway to reload
plugins and wire native callbacks through its control socket. Confirm the CLI's
activation result and gateway handler-wiring logs; if no gateway answers, use the
deployment's normal restart procedure. Replacing an already-wired plugin's Python
code may still require a restart because existing SDK callbacks remain registered.
No Slack remote configuration is changed by this plugin. Existing `/board`, Socket Mode,
interactivity and Slack platform credentials are prerequisites; a user token is
not required. Credentials remain managed by Hermes, not this plugin.

The native SDK hook requires `plugins.isolation: in_process` (Hermes' default).
Do not weaken an intentionally host-isolated deployment just to load this plugin.
No `register_command('board', ...)` is necessary: the factory directly registers
Bolt's `/board` command and all views/actions, so it is Slack-only and does not
send board commands through an LLM. `/board` must already be declared in the Slack
app; no automatic manifest synchronization is attempted.

## Architecture and compatibility decisions

- `register(ctx)` uses the supported `ctx.register_platform_handler('slack', factory)`.
  The factory gets the actual Bolt `AsyncApp` and a read-only adapter reference.
- `/board`, `^hermes_board_[a-z_]+$` actions and the four specific modal callback
  IDs are registered on that app. No catch-all listener replaces core approvals,
  feedback, model picking, or other plugins.
- Every slash, action, and view submission calls the real adapter's
  `_is_interactive_user_authorized` before DB reads, writes, modal opens, or Slack
  posting. Missing API, exceptions, malformed metadata and empty user IDs deny
  access. Hermes' own gate preserves injected profile-bound authorization and
  its standard scoped allowlist fallback. Denied requests receive a silent ACK.
- Workspace context uses a per-request `ContextVar` and explicit
  `_get_client(channel, team_id=...)`. It does not mutate adapter channel caches
  or message tracking sets, and overlapping requests do not share mutable team
  selection. Board locks are controller-owned; a duplicate request cannot release
  an existing request's lock.
- The renderer preserves text flags, help, natural-language aliases, filters,
  pagination, create/dependencies/priority/project/assignee, detail/edit, move,
  archive and approval/feedback behavior. Local relative imports replace the
  removed `gateway.platforms.slack_kanban_board` path.
- v0.22.4 no longer exports `kb.connect`. All native renderer connections use
  `hermes_cli.kanban_db_connect.connect_closing`, which also closes file handles
  (SQLite's plain connection context manager does not).
- Board resolution pins the validated slug back into the request's filters
  before rendering. Every board action/option and command-opened modal carries
  that identity, including `/board -n`, edit/detail/delete, and compact move
  option fallbacks. Switching the global current board cannot redirect a form
  opened on another board. Oversized move values drop optional display filters,
  never board identity; an identity exceeding Slack's limit is refused.
- **Manual Todo is a hold, stored as sticky Blocked.** v0.22.4's actual `todo`
  is dependency-wait, and `recompute_ready()` promotes it automatically, even
  without parents. There is no durable manual Todo lane in this runtime. The
  native port therefore safely parks a Slack Todo selection in `blocked`, with
  a real `blocked` lifecycle event; it appears in the Blocked column. Create/move
  forms and notices explain the mapping. A Ready selection releases the hold
  using `unblock_task()` and retains dependency gating. Runtime CLI/tool unblock
  is also an explicit release; board rendering and dispatcher recomputation are
  not. Repeated typed blocks retain the runtime's escalation to non-dispatchable
  Triage rather than bypassing its recurrence policy.
- Creation uses `create_task(initial_status='blocked')` for manual Todo, the
  runtime's `triage=True` for Triage, and normal dependency-gated creation for
  Ready. Status, parent links, and creation/block events commit in the runtime's
  single transaction. There is no post-create unconditional status UPDATE or
  dispatchable intermediate Ready commit. The resolved board is also passed to
  `create_task` for correct board metadata/project defaults.
- Manual blocks of Ready/Running tasks use `block_task(kind='needs_input')`.
  Active worker termination uses the closed lifecycle run's retained identity
  **after commit**, including block-loop escalation, not a stale pre-lock PID.
  Generic moves retain the runtime-version-pinned SQL fallback where no public
  transition verb exists; manual holds emit `blocked`, not merely `moved`.
- Move → Done calls the actual v0.22.4 `complete_task()` before entering the
  generic move transaction, just like the existing Done action. It supplies the
  same explicit Slack completion result; it never passes `force=True` or borrows
  a worker run ID. Native parent gates, accepted source statuses, live-worker
  ownership errors, completion runs/events, child promotion and lifecycle hooks
  remain owned by the runtime. A native refusal returns “Could not complete”; a
  native exception (including `LiveClaimError`) propagates to the existing caller
  error handling rather than falling through to a SQL status update.
- Done-parent reopen runs `invalidate_descendants_for_parent_reopen()` inside
  the same writer transaction as the parent status flip. It resets completion
  timestamps, recursively retracts Done/Review/Ready/Running descendants, closes
  active descendant runs, and persists invalidation events/comments. The caller
  drains the helper's returned worker terminations only after outer commit,
  through `_terminate_reclaimed_worker` with claim/start fingerprint checks.
  Failed invalidation rolls back both parent and descendants and signals nobody.
- Kanban remains the runtime's **shared cross-profile coordination store**.
  Assignees are profile names, not permission to load another profile's config or
  change its files. Board values go through Hermes' slug validator; no payload can
  select an arbitrary DB/profile path. The plugin does not override storage roots.
- Legacy overlays, installer and legacy tests are retained unchanged. Native code
  is intentionally separate, so upgrading the modern plugin does not patch or
  break an old Hermes checkout.

## Tests and observed TDD evidence

Run from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 hermes --run-module unittest discover -s tests -p 'test_native*.py' -v
PYTHONDONTWRITEBYTECODE=1 hermes plugins doctor ./slack_board --ci
```

No packages are installed. `hermes --run-module pytest --version` reported that
pytest is absent in the immutable runtime. Stdlib unittest therefore runs the
native tests; the 18 legacy renderer assertion functions have been adapted to the
native import/connection path and wrapped with disposable SQLite/environment
fixtures. The old pytest-only overlay installer suite is retained, not claimed
as executed here. Tests create and delete temporary homes only beneath this
repository's `tests/` directory; delegation fencing is cleared only inside those
isolated fixture environments, never in the production plugin.

Observed RED → GREEN slices during implementation:

1. Native factory registration initially failed because `slack_board` did not
   exist; adding the native module/factory made its registration contract pass.
2. Authorization tests failed on unauthorized adapter access and missing-API
   exceptions. Central pre-dispatch gates made all six entrypoints deny safely.
3. Renderer regression tests failed with `kb.connect` missing on the actual
   v0.22.4 module. Migrating to `connect_closing` passed all 18 renderer cases.
4. Workspace test failed trying to mutate an immutable adapter channel map.
   Per-request explicit team routing passed without adapter mutation.
5. Installer test failed because the new local installer did not exist; the
   copy-only installer/manifest passed with overwrite refusal.
6. Real-adapter UI test caught writes to the adapter's message-tracking set.
   Removing those writes preserved UI behavior and the read-only adapter seam.
7. Duplicate action test caught another request's lock being released by an
   early-returning duplicate. Tracking acquisition ownership fixed it.

Final native suite after blocking-review fixes: **41 tests passed**. Real Bolt registration and the actual
v0.22.4 Slack adapter are exercised. Native callback integration tests create,
read back, edit, move, archive, request changes and approve real SQLite tasks;
only outbound Slack network calls are test doubles. Tests also cover denied
view resubmission, actor attribution, public/private text and UI/modal rendering.

### Blocking-review RED → GREEN evidence

Each primary regression was written and executed against the installed runtime
before changing the corresponding production path. The observed failures were:

| Defect / regression | Observed RED | Verified GREEN |
| --- | --- | --- |
| `FlowTests.test_implicit_board_is_pinned_across_current_board_switch` | Refresh action carried `board:null`: `None != 'alpha'` | All action/option payloads and command modals pin alpha; board-button and command New Task submissions still create in alpha after switching current to bravo; bravo remains empty. |
| `RuntimeRegressions.test_manual_todo_and_blocked_survive_dispatcher_until_explicit_ready` | Both subcases promoted: `'ready' != 'blocked'` | Three real `recompute_ready()` passes and real claim refusals preserve the hold; explicit Ready permits a claim. |
| `RuntimeRegressions.test_creation_never_exposes_ready_before_manual_hold` | A second SQLite connection claimed a real Running task in the old create/final-state gap | Deterministic interleaving at the return of real `kb.create_task`: no intermediate Ready, no claim, final Blocked with no active run/claim, creation event says Blocked. |
| `RuntimeRegressions.test_done_parent_reopen_invalidates_descendants_before_worker_termination` | Termination count `0 != 1`; active grandchild was not invalidated | A separate connection observes the committed parent reopen, all recursive descendant retractions and reclaimed run **inside the termination callback**; the real runtime termination helper ends a disposable sleeping subprocess. Stale run completion is refused. |

Additional regression-first failures caught compact move fallback dropping the
board (`None != 'alpha'`), UI notices claiming Todo instead of Blocked, and
missing active-worker termination on both normal manual block and runtime
block-loop escalation. All now pass. Supplemental tests cover each manual
Done-reopen destination, atomic rollback after injected invalidation failure,
manual creation hold surviving parent completion, and Ready release still
waiting for incomplete parents. Persistence, claims, lifecycle transitions and
descendant invalidation are real v0.22.4 APIs, not synthesized responses; the
creation wrapper only inserts the deterministic second-connection interleaving.
Worker identity tests use a signal-boundary spy; the parent-reopen test also
calls the actual termination helper on its own disposable process.

The two inherited renderer assertions that expected a literal manual Todo row
and Todo column were changed to require Blocked, reflecting the explicit safe
mapping above, not accepting automatic promotion. The dependency-wait Todo
assertion is unchanged. The new tests assert the stronger dispatcher/claim gate.

### Final Done-transition RED → GREEN evidence

`RuntimeRegressions.test_move_done_preserves_native_completion_lifecycle` was
added and run before the completion routing change. Its three real-runtime
subcases all failed: incomplete-parent child became Done (`'done' != 'todo'`),
valid manual completion had no result (`None != 'Completed from Slack /board.'`),
and an actual sleeping worker's live claim did not raise `LiveClaimError`.
After routing Move → Done to `complete_task()`, the same test passed. It verifies:

- Refused completion leaves the dependency-wait child incomplete with no
  completion timestamp/event; after `recompute_ready()`, its grandchild remains
  Todo and cannot be claimed.
- Valid completion persists the Slack result, a completed synthetic native run
  with its summary, and exactly one linked `completed` event (not a generic
  `moved` event); native recomputation releases its child for a real claim.
- The same `LiveClaimError` as direct native completion propagates for a real
  disposable worker, leaving Running status, claim/run/PID, open run outcome and
  worker process intact. Cleanup only kills this test-owned subprocess.

Targeted RED: `Ran 1 test in 0.346s` / `FAILED (failures=3)`.
Targeted GREEN: `Ran 1 test in 0.348s` / `OK`.
Observed final full execution: `Ran 41 tests in 3.273s` / `OK`, followed by plugin
doctor success. This executes only native tests; it is not a claim that the
legacy overlay pytest suite, an installed gateway, or live Slack was tested.
No production installation, restart, credentials, or core edits were used.

Pre-fix Slack messages/modals that omitted a board slug cannot have their
original board reconstructed: discard them and render fresh `/board` messages.
Existing externally created `todo` rows keep runtime dependency-wait semantics;
this patch does not migrate production tasks or change dispatcher policy.

Plugin doctor result:

```text
manifest: slack-board 0.2.0 (standalone)
OK: runtime discovery, manifest parsing, import, and registration passed
registrations: 0 tool(s), 0 hook(s)
```

Zero tools/hooks is expected: the registration is a native platform factory,
not an LLM tool or lifecycle hook. No live Slack round trip has been tested;
after installation/reload, an authorized user should smoke-test `/board`, text,
create/edit/move/archive and both approval actions in Slack.
