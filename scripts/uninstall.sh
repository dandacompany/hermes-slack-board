#!/usr/bin/env bash
set -euo pipefail

HERMES_ROOT="${1:-$HOME/.hermes/hermes-agent}"
BACKUP_DIR="${2:-}"

if [[ -z "$BACKUP_DIR" ]]; then
  BACKUP_DIR="$(ls -dt "$HOME"/.hermes/backups/hermes-slack-board-* 2>/dev/null | head -n 1 || true)"
fi

if [[ -z "$BACKUP_DIR" || ! -d "$BACKUP_DIR" ]]; then
  echo "No hermes-slack-board backup found. Pass: uninstall.sh <hermes_root> <backup_dir>" >&2
  exit 2
fi

echo "restoring from $BACKUP_DIR"
for rel in \
  gateway/platforms/slack.py \
  gateway/platforms/slack_kanban_board.py \
  tests/test_slack_kanban_board.py
do
  if [[ -f "$BACKUP_DIR/$rel" ]]; then
    mkdir -p "$(dirname "$HERMES_ROOT/$rel")"
    cp "$BACKUP_DIR/$rel" "$HERMES_ROOT/$rel"
    echo "restored $rel"
  else
    rm -f "$HERMES_ROOT/$rel"
    echo "removed $rel"
  fi
done

echo "done. restart your Hermes gateway."
