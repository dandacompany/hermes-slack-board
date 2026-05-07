---
name: hermes-slack-board-setup
description: Guided setup skill for installing and configuring the Hermes Slack /board Kanban UI after Hermes Agent and Slack are available. Use when the user wants step-by-step /board installation, Slack App manifest setup, App Configuration Token automation, command option guidance, smoke tests, or troubleshooting.
version: 0.1.0
author: Dante Labs
license: MIT
platforms: [macos, linux]
prerequisites:
  commands: [hermes, python3, curl]
metadata:
  hermes:
    tags: [Hermes, Slack, Kanban, Board, Block Kit]
    requires_toolsets: [terminal]
---

# Hermes Slack Board Setup

Use this skill to guide a user from an existing Hermes Agent installation to a working Slack `/board` Kanban UI.

This skill is a setup guide. It does not grant Slack workspace permissions, create Slack tokens, or replace the Hermes gateway. It helps the agent and user install the `/board` package, configure the Slack app, validate settings, and run smoke tests.

## Operating Rules

- Start from this baseline: Hermes Agent is installed on a server, one Hermes Slack app can connect, and the user has Slack app configuration access.
- Do not assume local paths, Slack app IDs, channel IDs, or tokens.
- Never print full Slack tokens. Redact configuration, bot, app-level, and refresh tokens in reports.
- Prefer deterministic steps: install script, manifest export, manifest validate, manifest update, config check, gateway restart, smoke test.
- Treat Slack App Configuration Token generation, workspace install or reinstall approval, app-level token generation, bot token placement, and channel invitation as guided user actions.
- Keep `/board` command behavior predictable: explicit flags are deterministic; natural-language requests are accepted only when the intent is clear.

## Workflow

### 1. Baseline Check

Run:

```bash
hermes --version
hermes config check
hermes profile list
```

Confirm the Hermes checkout path. The remote installer can auto-detect common paths, but custom deployments should pass `--hermes-root`.

### 2. Install `/board`

Run the install helper:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash
```

If Hermes is installed in a custom location:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash -s -- --hermes-root /opt/hermes-agent
```

After install, run:

```bash
hermes config check
```

### 3. Configure Slack App

Read `references/slack-app-checklist.md`.

Guide the user through:

- Socket Mode
- Interactivity & Shortcuts
- Slash command `/board`
- Request URL placeholder or gateway URL
- OAuth scopes
- Workspace reinstall
- Test channel invitation

### 4. Use App Configuration Token When Available

Read `references/app-configuration-token.md` when the user has a Slack App Configuration Token or wants Claude/Codex to automate manifest setup.

Use the token only for manifest API work:

- export current manifest
- validate edited manifest
- update app manifest

Do not claim the token can complete workspace reinstall, token generation, or channel invitation.

### 5. Verify Commands

Read `references/board-command-options.md`.

Smoke test:

```text
/board
/board -t --summary
/board -p youtube -s ready
/board -n "Test task" -p youtube -s todo
```

### 6. Restart Gateway

Restart the gateway only after Slack app changes and Hermes config validation:

```bash
systemctl --user restart hermes-gateway.service
```

For profile-specific services:

```bash
systemctl --user restart hermes-gateway-manager.service
```

### 7. Troubleshoot

Read `references/troubleshooting.md` when:

- Slack says the app did not respond
- `/board` is unknown
- buttons show warning icons
- modals fail to open
- Slack rejects blocks
- text mode works but Block Kit does not

## Validation

Validate this skill package:

```bash
python3 skills/hermes-slack-board-setup/scripts/validate_setup.py skills/hermes-slack-board-setup
```

