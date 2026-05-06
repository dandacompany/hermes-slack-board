# Phase 2 Research: Plugin and Upstream Path

Goal: turn the Slack `/board` UI from a direct Slack adapter patch into a cleanly distributable Hermes extension.

## Current Facts

Official Hermes documentation says general plugins can register tools, hooks, session slash commands, CLI commands, skills, gateway platforms, image generation providers, context engines, memory providers, and model providers.

Relevant official docs:

- Plugins overview: https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins
- Build a Hermes Plugin: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin
- Built-in plugins: https://hermes-agent.nousresearch.com/docs/user-guide/features/built-in-plugins
- Slack setup: https://hermes-agent.nousresearch.com/docs/user-guide/messaging/slack
- Slash commands reference: https://hermes-agent.nousresearch.com/docs/reference/slash-commands
- Kanban reference: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban
- Kanban tutorial: https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-tutorial

The current docs explicitly support `ctx.register_command(name, handler, description)` for `/name` commands in CLI and gateway sessions. They also support `ctx.register_platform(...)` for a new messaging platform. They do not currently document a plugin API for registering Slack Bolt `action_id` handlers or modal `callback_id` handlers against the built-in Slack adapter.

## Local Code Findings

From the Hermes checkout:

- `hermes_cli/plugins.py` defines `PluginContext`.
- `PluginContext.register_command()` feeds plugin commands into the central command registry.
- `hermes_cli/commands.py` exposes `slack_native_slashes()`, which the Slack adapter uses to register native Slack slash commands.
- `gateway/platforms/slack.py` owns the Bolt app and currently registers:
  - native slash commands through `@self._app.command(...)`
  - approval button actions
  - slash-confirm actions
  - the experimental `hermes_board_` action and view handlers added by this package
- `plugins/kanban/` provides the dashboard UI and REST API surface, but that dashboard plugin surface is separate from Slack Block Kit interactivity.

## Why a Normal Plugin Is Not Enough Yet

A plugin slash command can return text into a Hermes session, but the Slack board needs:

- immediate slash-command ACK to avoid Slackbot timeout errors;
- `chat.postMessage` / `chat.update` with custom blocks;
- `views.open` and `views.update` for modals;
- `app.action(...)` handlers for `hermes_board_*`;
- `app.view(...)` handlers for modal submissions.

Those are Slack-adapter-level concerns. Without a public adapter extension hook, a pure plugin cannot reliably own the full Block Kit lifecycle.

## Recommended Phase 2 Plan

1. Open an upstream PR adding a small Slack extension registry to Hermes core.
2. Keep all Kanban-specific rendering and mutation logic outside `slack.py`.
3. Convert this package into a normal plugin that registers its Slack extension when the Slack adapter starts.
4. Keep `/board` as native Slack slash command, not just a generic `/kanban` text command.
5. Add docs and tests for third-party Slack UI extensions.

## Proposed Core API

The minimal shape could be:

```python
ctx.register_slack_extension(
    slash_commands=[
        SlackSlashCommand(
            name="board",
            description="Open the Hermes Kanban board",
            handler=handle_board_command,
            ack_text="Opening Kanban board...",
        )
    ],
    actions=[
        SlackAction(pattern=r"^hermes_board_", handler=handle_board_action),
    ],
    views=[
        SlackView(callback_id="hermes_board_task_create", handler=handle_create_view),
        SlackView(callback_id="hermes_board_task_move", handler=handle_move_view),
        SlackView(callback_id="hermes_board_task_detail", handler=handle_detail_view),
    ],
)
```

If Hermes maintainers prefer not to expose Slack-specific plugin APIs, a narrower in-core `/board` feature may be more acceptable.

## Package Options

### Option A: Upstream `/board` Into Hermes Core

Pros:

- Best user experience.
- No patch installer.
- Manifest generation can include `/board`.
- No plugin lifecycle ambiguity.

Cons:

- Requires maintainers to accept Slack-specific UI in core.
- Iteration speed depends on upstream review.

### Option B: Upstream Slack Extension Hook, Ship `/board` as Plugin

Pros:

- Clean distribution through `hermes plugins install`.
- Opens the door for other Slack Block Kit plugins.
- Keeps Kanban-specific UI out of `slack.py`.

Cons:

- Requires a new extension surface and documentation.
- Must define security and conflict behavior for action IDs and view callback IDs.

### Option C: Continue Version-Pinned Patch Package

Pros:

- Fastest to publish.
- Works immediately for power users.

Cons:

- Patch conflicts are likely after Hermes updates.
- Not ideal for nontechnical users.
- Slack app setup remains manual.

## First Upstream PR Scope

Keep the first PR small:

- Add a `SlackExtensionRegistry`.
- Let plugins register slash commands, action handlers, and view handlers.
- Let the Slack adapter consume the registry during `connect()`.
- Add tests proving a fake extension registers:
  - one `/example` command;
  - one `example_action` handler;
  - one `example_view` handler.
- Do not include the full Kanban board UI in the same PR unless maintainers request it.

## Open Questions

- Should Slack extension plugins be enabled only for trusted local plugins?
- How should action ID collisions be handled?
- Should manifest generation include plugin-provided native Slack slash commands?
- Should extension handlers receive the `SlackAdapter` instance, a narrowed client/context object, or only raw Bolt payloads?
- Should the board UI call `kanban_db` directly or go through the existing Kanban dashboard REST layer?

## Recommendation

For public release now, use this repository as a version-pinned installer.

For durable distribution, pursue Option B first: a generic Slack extension hook. If that is rejected as too broad, fall back to Option A and upstream `/board` as a bundled Slack feature.
