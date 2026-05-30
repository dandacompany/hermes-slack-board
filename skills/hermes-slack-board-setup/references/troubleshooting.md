# Troubleshooting

## Slackbot says the app did not respond

Check:

```text
Slash command /board exists on the connected Slack app
App was reinstalled after command/scope changes
Hermes gateway is running
Gateway logs show the /board command
```

## `/board` is unknown

The slash command is not registered on that Slack app, or the workspace has not been reinstalled after adding it.

## `/board` stopped responding after `hermes update`

`hermes update` stashes local changes to tracked files before pulling, then offers to restore them — a restore that conflicts or is declined across a large update. The result: `gateway/platforms/slack.py` is reverted to clean upstream (the `/board` registration, action handlers, and methods are gone), while the untracked overlay `gateway/platforms/slack_kanban_board.py` is left behind, orphaned and possibly stale.

Re-run the installer, then restart the gateway:

```bash
curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash
systemctl --user restart hermes-gateway.service
```

Re-install is idempotent and is the supported recovery path. Do not rely on `git stash apply`.

## Tasks missing from the board on Hermes 0.15.x

Hermes 0.15.x added Kanban statuses (`scheduled`, `review`, `archived`). The board renders a `Review` column. Statuses with no column (e.g. `scheduled`) are surfaced as an `other N` count in the board header instead of being dropped. Inspect them with the `hermes kanban` CLI (or `/board -s scheduled` in UI mode, which renders that column only when such tasks exist). `archived` tasks appear only with `--archived`.

## Buttons show warning icons

Check:

```text
Interactivity & Shortcuts: On
Gateway logs show hermes_board_ action events
Action handler acks within Slack timing limits
Use the latest board message before opening modals
```

## Modal fails with expired trigger_id

Click from the latest board message or run `/board` again. Slack trigger IDs expire quickly.

## Slack rejects blocks

Use supported message blocks. Some Block Kit Builder examples include newer block types that normal `chat.postMessage` or `chat.update` surfaces may reject.

## Text mode works but UI mode fails

Run:

```text
/board -t --summary
```

If text mode works, Kanban data is readable. Focus on Slack Block Kit schema, interactivity, and gateway action handling.
