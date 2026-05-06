# Draft PR Description

## Title

Add Slack Block Kit extension hooks for plugin-provided interactive UI

## Summary

This PR proposes a small Slack extension registry so Hermes plugins can register Slack-native interactive surfaces without patching `gateway/platforms/slack.py`.

The immediate motivating use case is a Slack `/board` UI for Hermes Kanban: task cards, status movement, task creation, detail modals, approval actions, and run/debug visibility. The broader value is that future Slack-native plugins can register slash commands, Block Kit actions, and modal submissions through a supported API.

## Problem

`PluginContext.register_command()` works well for text slash commands in CLI and gateway sessions, but it is not enough for Slack Block Kit workflows. Slack-native UI needs immediate command ACKs, `chat.postMessage` / `chat.update`, `views.open`, `app.action(...)`, and `app.view(...)` handlers.

Right now those handlers must be added directly inside the Slack adapter. That makes Slack-native plugin UI hard to distribute and hard to maintain across Hermes updates.

## Proposed Change

- Add a Slack extension registry to Hermes core.
- Add `PluginContext.register_slack_extension(...)`.
- Let plugins register:
  - native Slack slash commands;
  - Block Kit action handlers;
  - modal view submission handlers.
- Let `SlackAdapter.connect()` consume the registry and register those handlers on the Bolt app.
- Add collision handling and tests.

## Out of Scope

- This first PR does not need to merge the full Kanban `/board` UI.
- This first PR does not need to change non-Slack gateway adapters.
- This first PR does not need to replace `ctx.register_command(...)`; it complements it for Slack-native interactivity.

## Reference Implementation

Reference package: https://github.com/dandacompany/hermes-slack-board

The reference implementation proves:

- `/board` must ACK immediately to avoid Slackbot timeout errors.
- Board messages should avoid unsupported block types such as `alert`.
- Carousel/card limits require pagination and status filters.
- Drag-and-drop is not available in Slack Block Kit, so state changes need buttons/selects/modals.
- Approval-required tasks need first-class human-in-the-loop controls.

## Tests

The reference package currently includes renderer and action-payload tests for:

- board argument parsing;
- Slack action value round trips;
- block rendering within Slack limits;
- task creation;
- dependencies;
- project options;
- status movement;
- detail updates;
- archive behavior;
- approval continue/request changes flow;
- pagination.
