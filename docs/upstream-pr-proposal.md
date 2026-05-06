# Upstream PR Proposal: Slack Block Kit Extension Hooks for Hermes

## Summary

Hermes already has a strong Kanban system and a Slack Socket Mode gateway. The missing piece is a clean way for Hermes plugins to register Slack-native interactive UI: slash command ACK handlers, Block Kit action handlers, and modal view handlers.

This proposal recommends adding a small Slack extension registry to Hermes core. The first consumer would be the `/board` Kanban UI, but the extension point is intentionally generic so other plugins can build Slack-native workflows without patching `gateway/platforms/slack.py`.

## User Problem

The current `/kanban` command is functional, but Slack users need a visual control-plane surface for:

- seeing task status without opening the dashboard;
- creating tasks from Slack;
- moving tasks across Kanban states;
- opening task detail modals;
- approving or requesting changes when a worker blocks on human input;
- reviewing run history, comments, events, and worker failure context.

A plain text slash command cannot provide this. A Slack Block Kit UI can.

## Current Constraint

Hermes plugins can register session slash commands with `ctx.register_command(...)`. That is sufficient for text commands in CLI/gateway sessions, but not for a Slack-native Block Kit workflow.

The Slack board requires:

- immediate `ack()` for `/board` to avoid Slack timeout UX;
- background `chat.postMessage` / `chat.update` rendering;
- `app.action(...)` handlers for `action_id` payloads;
- `app.view(...)` handlers for modal submissions;
- access to the Slack adapter client/context in a controlled way.

Today those registrations live inside `gateway/platforms/slack.py`, so third-party UI features have to patch the adapter directly.

## Proposed Core Shape

Add a small registry, for example:

```python
@dataclass
class SlackSlashCommand:
    name: str
    description: str
    handler: Callable
    ack_text: str = "Working..."

@dataclass
class SlackActionHandler:
    action_id: str | Pattern[str]
    handler: Callable

@dataclass
class SlackViewHandler:
    callback_id: str
    handler: Callable

class PluginContext:
    def register_slack_extension(
        self,
        *,
        slash_commands: Sequence[SlackSlashCommand] = (),
        actions: Sequence[SlackActionHandler] = (),
        views: Sequence[SlackViewHandler] = (),
    ) -> None:
        ...
```

The Slack adapter would consume the registry during `connect()`:

```python
for command in slack_extension_registry.slash_commands:
    self._app.command(f"/{command.name}")(command.handler)

for action in slack_extension_registry.actions:
    self._app.action(action.action_id)(action.handler)

for view in slack_extension_registry.views:
    self._app.view(view.callback_id)(view.handler)
```

## Collision Rules

- Slash command names should follow the same sanitation and collision rules as `slack_native_slashes()`.
- Action IDs and callback IDs should be namespaced by plugin name unless explicitly declared global.
- On collision, Hermes should log a warning and keep the first registration.
- Built-in Slack handlers should always win over plugin handlers.

## Security Model

Only trusted local code can register Slack interactive handlers:

- bundled plugins under `<repo>/plugins/`;
- user plugins under `~/.hermes/plugins/` when explicitly enabled;
- project plugins only when `HERMES_ENABLE_PROJECT_PLUGINS=true`.

This matches the existing plugin trust model.

## Manifest Generation

If plugin-provided Slack slash commands are enabled at manifest generation time, `hermes slack manifest --write` should include them.

If a command is installed after the Slack app manifest was created, Hermes should show a clear setup message:

```text
Plugin "kanban-board" registered Slack command /board.
Regenerate and reinstall the Slack app manifest:
  hermes slack manifest --write
```

## First PR Scope

Keep the first upstream PR small and generic:

- Add Slack extension registry data structures.
- Add `PluginContext.register_slack_extension(...)`.
- Wire registered commands/actions/views into `SlackAdapter.connect()`.
- Add tests with a fake extension:
  - registers `/example`;
  - registers `example_action`;
  - registers `example_view`;
  - rejects or warns on collisions.
- Update plugin documentation.

The full Kanban `/board` UI can be a second PR or bundled plugin once the extension point is accepted.

## Why Not Just Add `/board` Directly?

Adding `/board` directly to Hermes core would solve Kanban, but it would not solve the broader extension problem. Other Slack-native workflows would still need to patch `slack.py`.

The extension hook is a small general primitive. The board UI becomes the proof that the primitive is useful.

## Reference Implementation

This repository contains a working version-pinned implementation:

- `overlays/gateway/platforms/slack_kanban_board.py`: Kanban-specific rendering and mutation helpers.
- `overlays/gateway/platforms/slack_board_methods.pyfrag`: current direct Slack adapter methods.
- `scripts/install.py`: patch installer used only until Hermes exposes the extension hook.

The reference implementation has already surfaced practical constraints:

- Slack slash commands must ACK immediately.
- Normal Slack messages may reject newer `alert` blocks even if examples show them in modal contexts.
- Carousel/card limits require pagination and status filters.
- Drag-and-drop is not available in Slack Block Kit; movement needs buttons/selects/modals.
- Approval tasks need a human-in-the-loop UI, not only a status label.

## Draft PR

Draft upstream PR:

- https://github.com/NousResearch/hermes-agent/pull/20936

The PR intentionally proposes only the generic Slack extension hook. The Kanban `/board` UI should follow as a second PR or as a plugin after the hook is accepted.

## Acceptance Criteria for `/board`

When implemented through the extension hook:

- `/board` returns an immediate Slack ACK.
- The board renders without Slack `invalid_blocks` errors.
- Add, Move, Detail, Archive, Approve, and Request Changes work from Slack.
- Duplicate clicks do not execute repeated mutations.
- Cards remain within Slack block limits.
- Tests cover block generation, payload parsing, task creation, movement, detail updates, dependency selection, approval actions, and pagination.
