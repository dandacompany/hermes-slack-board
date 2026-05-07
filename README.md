# Hermes Slack Board

Experimental Slack Block Kit UI for the Hermes Agent Kanban board.

This package adds a native Slack `/board` command that renders Hermes Kanban tasks as interactive Slack cards. It is a fast-public release extracted from a working Hermes Agent v0.12.0 installation, with an installer that backs up the target checkout before applying changes.

## What It Adds

- `/board` native Slack slash command with immediate ACK, then async board rendering.
- Slack Block Kit board with status filtering, approvals filter, pagination, and card carousel support.
- Global task creation modal.
- Task movement modal.
- Task detail modal with editable title, description, assignee, project, archive action, run history, events, comments, worker log tail, and approval actions.
- Duplicate-click lock to reduce repeated Slack actions while a board message is repainting.
- Tests for renderer and Slack action payload behavior.

## Compatibility

Tested against:

- Hermes Agent v0.12.0, 2026.4.30 release line.
- Python 3.11.
- Slack Bolt Socket Mode.

This is not yet a pure Hermes plugin because Hermes plugins can register general slash commands, but the current public plugin surface does not expose Slack Bolt Block Kit action/view registration hooks. The installer patches the Slack adapter directly and creates a backup.

## Install

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

| Long option | Short | Purpose |
| --- | --- | --- |
| `--project` | `-p` | Project filter. Legacy `--tenant` still works. |
| `--status` | `-s` | Status filter. |
| `--approval` | `-a` | Show approval-required tasks. Legacy `--approval-required` still works. |
| `--limit` | `-l` | Max cards/items per status. |
| `--query` | `-q` | Search title, description, or task id. |
| `--assignee` | `-u` | Assignee/profile filter. |
| `--page` |  | Page number for long status lists. |
| `--archived` |  | Include archived tasks. |
| `--text` | `-t` | Return a plain text report. |
| `--summary` |  | Text mode summary. |
| `--full` |  | Text mode with descriptions. |
| `--public` |  | Post text report to the channel. Text mode is ephemeral by default. |
| `--new` | `-n` | Open the new task modal, optionally with a title. |
| `--edit` | `-e` | Open the editable task detail modal. |
| `--delete` | `-d` | Open task detail for archive confirmation. |
| `--help` | `-h` | Show command help. |
```

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
