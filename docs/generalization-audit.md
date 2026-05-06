# Generalization Audit

This project is intended to be reusable by any Hermes Agent operator running Slack through Socket Mode. It should not assume a specific server, Slack workspace, channel, profile roster, or business domain.

## Checked

- No hardcoded Slack tokens.
- No hardcoded Slack channel IDs.
- No private server name, local Mac path, or private host assumptions in user-facing docs.
- Default Hermes checkout path uses the standard `~/.hermes/hermes-agent`, with an explicit path argument for nonstandard installs.
- Slack app setup is documented as a manual step because Slack app commands, scopes, interactivity, and reinstall cannot be safely changed by a Hermes plugin or local installer.
- Examples use generic names such as `acme`, `writer`, `manager`, and `product-launch`.
- Tests use synthetic Slack IDs only.

## Intentional Hermes-Specific Terms

- The code uses `tenant` internally because Hermes Kanban currently models project namespaces with the `tenant` field.
- User-facing text calls this "project" where possible.
- The package targets Hermes Agent v0.12.0 because it inserts methods into the current Slack adapter shape.

## Remaining Coupling

- The installer is version-sensitive because it patches `gateway/platforms/slack.py`.
- The Slack UI is not yet a pure plugin because Hermes does not currently expose Slack Bolt action/view registration through `PluginContext`.
- Modal detail sections use Slack `alert` blocks because they are modal-specific. Board messages avoid `alert` because normal Slack messages may reject it.

## Public Release Positioning

Describe the repository as:

> A version-pinned experimental installer and reference implementation for a Slack Block Kit Kanban UI for Hermes Agent.

Avoid describing it as:

> A stable Hermes plugin.

That distinction matters. The repository is useful immediately, but the durable path is an upstream Slack UI extension hook or an in-core `/board` implementation.
