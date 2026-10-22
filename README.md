# Hermes Slack Board

Experimental Slack Block Kit UI for the Hermes Agent Kanban board.

This package adds a native Slack `/board` command that renders Hermes Kanban tasks as interactive Slack cards. **Hermes v0.22.4 uses the native local plugin in `slack_board/`, without core patches.** The original overlay installer remains available for legacy Hermes versions only.

## Native plugin: Hermes v0.22.4

From this repository, using the default profile:

```bash
python3 scripts/install_plugin.py --home "$HOME/.hermes"
hermes plugins enable slack-board
hermes plugins doctor slack-board --ci
# Confirm the enable command reports live callback activation.
# Restart via your normal service procedure if the gateway did not reload.
```

For a different profile, pass its **exact home** to `--home` and use the same
`HERMES_HOME` for the enable/doctor commands. The installer refuses an existing
plugin destination; it does not change config, install dependencies, restart the
gateway, or modify Slack. Do not use the legacy `install.sh` on v0.22.4.

Requires the already-configured Slack platform, Socket Mode/interactivity, and an
existing `/board` Slack slash command. This plugin requires the default
`plugins.isolation: in_process` mode; native SDK callbacks cannot run in `host`
isolation. It uses Hermes' profile-bound Slack interactive authorization on
**every slash, button/select action, and view submission**, with fail-closed
handling if that API is unavailable or raises. Kanban storage remains Hermes'
shared cross-profile coordination database by design, not a separate plugin DB.

Run the new suite through the PM-managed launcher (no pip changes):

```bash
PYTHONDONTWRITEBYTECODE=1 hermes --run-module unittest discover -s tests -p 'test_native*.py' -v
hermes plugins doctor ./slack_board --ci
```

Move → Done uses the native completion lifecycle, not a direct status update:
parent dependencies and live-worker ownership remain enforced, and successful
completion retains native run/event auditing. Manual Todo is stored as a sticky
Blocked hold until explicitly released to Ready.

See [native installation, design, and verification](docs/native-plugin.md).


## What It Adds

- `/board` native Slack slash command with immediate ACK, then async board rendering.
- Slack Block Kit board with status filtering, approvals filter, pagination, and card carousel support.
- Global task creation modal.
- Task movement modal.
- Task detail modal with editable title, description, assignee, project, archive action, run history, events, comments, worker log tail, and approval actions.
- Duplicate-click lock to reduce repeated Slack actions while a board message is repainting.
- Tests for renderer and Slack action payload behavior.

## Compatibility

The following compatibility notes describe the **legacy overlay path**. On v0.22.4,
use the native plugin above instead of patching the Slack adapter.

Legacy versions tested against:

- Hermes Agent v0.12.0 (2026.4.30) and v0.13.0 (2026.5.7).
- Python 3.11.
- Slack Bolt Socket Mode.

### Note on Hermes v0.13.0

v0.13.0 ships a baseline `gateway/platforms/slack_kanban_board.py` upstream (~924 lines), but it does not yet wire `/board` as a Slack slash command and does not expose extension hooks for Slack Bolt action/view handlers. This package replaces the upstream module with an extended version (~1,927 lines) that adds: short-option and natural-language parsing, status pagination, approval filter and approve/request-changes flow, task creation modal with dependencies and project options, edit modal, dependency/project selectors, debug detail blocks, and richer help/text output. The original upstream file is backed up under `~/.hermes/backups/hermes-slack-board-*` before replacement.

The legacy overlay was not a pure plugin: those older releases lacked the required native Slack registration hooks. Its installer patches the Slack adapter directly and creates a backup. v0.22.4 now has those hooks and uses `slack_board/` instead.

### Roadmap

The v0.22.4 local native plugin is implemented. Future work can reduce dependence on internal Kanban SQL/helpers as upstream exposes higher-level mutation APIs.

## Legacy Overlay Install (not v0.22.4)

For most users, run the install wizard on the server that runs Hermes:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash
```

The wizard auto-detects common Hermes checkout locations, shows the detected path, and asks for confirmation before patching.

If you prefer to inspect the installer before running it:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh -o /tmp/install-hermes-slack-board.sh
less /tmp/install-hermes-slack-board.sh
bash /tmp/install-hermes-slack-board.sh
```

If Hermes is installed in a custom location, pass the path:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash -s -- --hermes-root /opt/hermes-agent
```

Or use an environment variable:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | HERMES_AGENT_DIR=/opt/hermes-agent bash
```

Developers can also clone or copy this project onto the server:

```bash
git clone https://github.com/dandacompany/hermes-slack-board.git
cd hermes-slack-board
./scripts/install.sh ~/.hermes/hermes-agent
```

## Guided Setup Skill

This repository also includes a Hermes setup guide skill:

```bash
mkdir -p ~/.hermes/skills/hermes-slack-board-setup
cp -R skills/hermes-slack-board-setup/* ~/.hermes/skills/hermes-slack-board-setup/
hermes skills check
```

Use it when you want Hermes to walk through `/board` installation, Slack App setup, App Configuration Token automation, command options, and smoke tests step by step.

The installer:

1. Backs up `gateway/platforms/slack.py`, `gateway/platforms/slack_kanban_board.py`, and `tests/test_slack_kanban_board.py` under `~/.hermes/backups/hermes-slack-board-*`.
2. Copies the Slack board renderer and tests into the Hermes checkout.
3. Inserts the `/board` Slack command, Block Kit handlers, and board helper methods into `gateway/platforms/slack.py`.
4. Runs `py_compile`.
5. Runs `pytest tests/test_slack_kanban_board.py` unless `--skip-tests` is passed.

If your Hermes checkout is not at `~/.hermes/hermes-agent`, pass the path explicitly.

## Slack App Setup

The installer cannot change Slack app configuration. Add these settings in Slack:

1. Open `https://api.slack.com/apps` and select your Hermes Slack app.
2. Go to **Slash Commands**.
3. Add command `/board`.
4. Use any HTTPS request URL Slack accepts for Socket Mode manifests. Hermes receives the command over Socket Mode.
5. Go to **Interactivity & Shortcuts** and turn Interactivity on.
6. Reinstall the app to the workspace after changing commands or scopes.
7. Invite the Hermes bot to the channels where `/board` should work.

Restart Hermes gateway after install and Slack app changes:

```bash
hermes gateway restart
```

For systemd deployments:

```bash
systemctl --user restart hermes-gateway.service
```

## Usage

Open the default board:

```text
/board
/board --help
/board -h
```

Filter by project, status, approval, search query, and card limit:

```text
/board -p youtube
/board --project youtube
/board -s ready
/board --status ready
/board -a
/board --approval
/board -q "bright data"
/board -l 10
/board --assignee manager
/board --page 2
/board --archived
```

Options can be combined:

```text
/board -p youtube -s ready -a
/board --project youtube --status blocked --approval
```

Open a text report instead of the Block Kit board:

```text
/board -t
/board --text
/board -t --summary
/board -t --full
/board -t -p youtube -s blocked
/board -t --public
```

Create, edit, inspect, or archive a task from the slash command:

```text
/board -n
/board --new "AI news scrape" -p youtube -s todo
/board -e t_425b5e75
/board --edit t_425b5e75
/board --detail t_425b5e75
/board -d t_425b5e75
/board --delete t_425b5e75
```

`--delete` opens the task detail modal so the user can confirm with the Archive button.

The command also accepts simple natural-language requests:

```text
/board youtube 프로젝트 ready 텍스트로 보여줘
/board bright data 조사 추가
/board t_425b5e75 상세 보기
/board 승인 필요한 일만 요약
```

Supported option aliases:

| Long option  | Short | Purpose                                                                 |
| ------------ | ----- | ----------------------------------------------------------------------- |
| `--project`  | `-p`  | Project filter. Legacy `--tenant` still works.                          |
| `--status`   | `-s`  | Status filter.                                                          |
| `--approval` | `-a`  | Show approval-required tasks. Legacy `--approval-required` still works. |
| `--limit`    | `-l`  | Max cards/items per status.                                             |
| `--query`    | `-q`  | Search title, description, or task id.                                  |
| `--assignee` | `-u`  | Assignee/profile filter.                                                |
| `--page`     |       | Page number for long status lists.                                      |
| `--archived` |       | Include archived tasks.                                                 |
| `--text`     | `-t`  | Return a plain text report.                                             |
| `--summary`  |       | Text mode summary.                                                      |
| `--full`     |       | Text mode with descriptions.                                            |
| `--public`   |       | Post text report to the channel. Text mode is ephemeral by default.     |
| `--new`      | `-n`  | Open the new task modal, optionally with a title.                       |
| `--edit`     | `-e`  | Open the editable task detail modal.                                    |
| `--delete`   | `-d`  | Open task detail for archive confirmation.                              |
| `--help`     | `-h`  | Show command help.                                                      |

## Status Semantics

- `Triage`: rough ideas or unshaped requests. The dispatcher should not claim these until a human/specifier promotes them.
- `Todo`: task is created but not yet ready to run, often because dependencies remain.
- `Ready`: assigned and eligible for dispatcher claim.
- `In Progress`: a Hermes worker has claimed and is running the task.
- `Blocked`: human input, approval, missing config, auth failure, or circuit breaker intervention is needed.
- `Done`: completed task.

The Add modal intentionally offers only `Triage`, `Todo`, and `Ready`, because users usually should not create tasks directly into `In Progress`, `Blocked`, or `Done`.

## Uninstall

Restore the latest backup:

```bash
./scripts/uninstall.sh ~/.hermes/hermes-agent
```

Or restore a specific backup:

```bash
./scripts/uninstall.sh ~/.hermes/hermes-agent ~/.hermes/backups/hermes-slack-board-YYYYMMDD_HHMMSS
```

Restart the gateway after uninstalling.

## Known Limits

- This is a direct Slack adapter extension, not a clean third-party Hermes plugin yet.
- Slack carousel elements are limited; the UI uses status filters and pagination to avoid oversized messages.
- Slack does not support drag-and-drop Block Kit task movement. Movement is implemented through buttons and modals.
- Slack `alert` blocks may be unsupported in normal `chat.postMessage` / `chat.update` messages in some workspaces, so board section headers use standard `section` blocks.

## Phase 2 Direction

The target second phase is an upstreamable Hermes Slack UI extension point, so this board can become a normal installable plugin instead of a direct adapter patch.

- Research notes: [docs/research-phase-2.md](docs/research-phase-2.md)
- Maintainer-facing proposal: [docs/upstream-pr-proposal.md](docs/upstream-pr-proposal.md)
- Draft upstream PR description: [docs/pr-description.md](docs/pr-description.md)
- Generalization audit: [docs/generalization-audit.md](docs/generalization-audit.md)
