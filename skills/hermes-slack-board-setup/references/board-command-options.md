# Board Command Options

## Open Board

```text
/board
/board -p youtube
/board -s ready
/board -a
/board -p youtube -s ready -a
```

## Text Reports

```text
/board -t
/board -t --summary
/board -t --full
/board -t -p youtube -s blocked
```

Text reports are ephemeral by default. Use `--public` to post to the channel.

## Task Actions

```text
/board -n
/board -n "AI news scrape" -p youtube -s todo
/board -e t_425b5e75
/board --detail t_425b5e75
/board -d t_425b5e75
```

`--delete` opens detail for archive confirmation.

## Natural Requests

```text
/board youtube 프로젝트 ready 텍스트로 보여줘
/board bright data 조사 추가
/board t_425b5e75 상세 보기
/board 승인 필요한 일만 요약
```

## Option Table

| Long option | Short | Purpose |
| --- | --- | --- |
| `--project` | `-p` | Project filter. Legacy `--tenant` works. |
| `--status` | `-s` | Status filter. |
| `--approval` | `-a` | Approval-required tasks. |
| `--limit` | `-l` | Max cards/items. |
| `--query` | `-q` | Search title, description, or task id. |
| `--assignee` | `-u` | Assignee/profile filter. |
| `--text` | `-t` | Plain text report. |
| `--new` | `-n` | New task modal. |
| `--edit` | `-e` | Editable detail modal. |
| `--delete` | `-d` | Archive confirmation path. |

