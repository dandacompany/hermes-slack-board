# Slack App Checklist

Use this checklist for the Hermes Slack app that will receive `/board`.

## Required Settings

```text
Socket Mode: On
Interactivity & Shortcuts: On
Slash Commands: /board
Request URL: HTTPS placeholder or existing gateway URL
Reinstall to Workspace: after every scope, event, or command change
Channel invite: /invite @Hermes Manager
```

## Bot Token Scopes

```text
chat:write
commands
app_mentions:read
channels:history
channels:read
im:history
im:write
```

For private channels:

```text
groups:history
groups:read
```

## Direct UI Steps

These steps require user confirmation in Slack:

```text
Generate App Configuration Token
Generate app-level token for Socket Mode
Install or reinstall app to workspace
Approve changed scopes
Invite the app to target channels
Copy tokens into the server environment
```

