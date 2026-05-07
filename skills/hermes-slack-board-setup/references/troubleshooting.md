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

