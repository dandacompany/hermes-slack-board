# Slack App Configuration Token

Slack App Configuration Tokens work with App Manifest APIs. Use them to automate manifest export, validation, and update.

## What Can Be Automated

```text
apps.manifest.export
apps.manifest.validate
apps.manifest.update
apps.manifest.create
apps.manifest.delete
```

For `/board`, automation can update:

```text
Slash command /board
Socket Mode setting
Interactivity setting
OAuth scopes
Event subscriptions
Request URL fields required by Slack manifest validation
```

## What Still Needs User Action

```text
Generate App Configuration Token in Slack
Approve workspace install or reinstall
Generate app-level token for Socket Mode
Copy bot token and app token into Hermes server env
Invite the app to channels
Run final Slack smoke test
```

Configuration tokens are workspace/user scoped and expire. Use them soon after generation. Redact token values in all reports.

## Prompt For Claude Or Codex

```text
Slack App Configuration Token을 발급했습니다.

목표:
  Hermes Manager Slack App에 /board slash command와 Slack Block Kit interactivity를 설정해 주세요.

입력값:
  app_id: <SLACK_APP_ID>
  config_token: <SLACK_APP_CONFIGURATION_TOKEN>
  request_url: <HTTPS_REQUEST_URL_OR_PLACEHOLDER>

요청:
  1. apps.manifest.export로 현재 manifest를 백업해 주세요.
  2. /board slash command를 추가해 주세요.
  3. Socket Mode와 Interactivity를 켜 주세요.
  4. 필요한 bot scopes를 반영해 주세요.
  5. apps.manifest.validate로 검증해 주세요.
  6. 문제가 없으면 apps.manifest.update로 적용해 주세요.
  7. 사용자가 Slack UI에서 직접 해야 하는 일을 체크리스트로 알려 주세요.

주의:
  token 원문을 답변에 출력하지 말고, 실패하면 Slack API error와 manifest pointer만 요약해 주세요.
```

