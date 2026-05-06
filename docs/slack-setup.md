# Slack Setup Checklist

Use this checklist after installing the Hermes Slack Board package.

## Required Slack App Features

- Socket Mode enabled.
- Bot token configured in Hermes as `SLACK_BOT_TOKEN`.
- App-level token configured in Hermes as `SLACK_APP_TOKEN`.
- Interactivity enabled.
- Slash command `/board` added.
- App reinstalled after changing commands, scopes, or events.

## Recommended Bot Scopes

Hermes Slack setup already requires these common scopes:

- `chat:write`
- `app_mentions:read`
- `channels:history`
- `channels:read`
- `groups:history`
- `im:history`
- `im:read`
- `im:write`
- `users:read`

For private channels, invite the bot and make sure private-channel history events are configured.

## Smoke Test

In Slack:

```text
/board
```

Expected:

1. Slack immediately shows an ephemeral "Opening Kanban board..." response.
2. A Hermes Kanban Board message appears shortly after.
3. Refresh, Add, Move, and Detail controls respond without Slackbot timeout errors.

If Slack says the app did not respond, confirm the `/board` command was added to the same Slack app that the running Hermes gateway is connected to, then restart the gateway.

If buttons show warning icons or do nothing, confirm Interactivity is enabled and the Hermes gateway logs show `hermes_board_` action events.
