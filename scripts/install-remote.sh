#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_URL="${HERMES_SLACK_BOARD_ARCHIVE_URL:-https://github.com/dandacompany/hermes-slack-board/archive/refs/heads/main.tar.gz}"
HERMES_ROOT="${HERMES_AGENT_DIR:-}"
HERMES_ROOT_EXPLICIT=0
INSTALL_ARGS=()
YES=0

usage() {
  cat <<'EOF'
Install Hermes Slack /board without manually cloning the repository.

Usage:
  curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash

  bash install-remote.sh [--hermes-root PATH] [--yes] [--skip-tests] [--skip-git-check]

Environment:
  HERMES_AGENT_DIR                 Explicit Hermes checkout path.
  HERMES_SLACK_BOARD_ARCHIVE_URL   Override source archive URL.

Examples:
  curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh | bash

  curl -fsSL https://raw.githubusercontent.com/dandacompany/hermes-slack-board/main/scripts/install-remote.sh -o /tmp/install-hermes-slack-board.sh
  bash /tmp/install-hermes-slack-board.sh

  bash /tmp/install-hermes-slack-board.sh --hermes-root /opt/hermes-agent --yes
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --hermes-root)
      HERMES_ROOT="${2:?--hermes-root requires a path}"
      HERMES_ROOT_EXPLICIT=1
      shift 2
      ;;
    -y|--yes)
      YES=1
      shift
      ;;
    --skip-tests|--skip-git-check)
      INSTALL_ARGS+=("$1")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "error: required command not found: $1" >&2
    exit 127
  fi
}

need_cmd curl
need_cmd tar
need_cmd python3

say() {
  printf "%s\n" "$*"
}

ask() {
  local prompt="$1"
  local answer
  if [[ -r /dev/tty ]]; then
    printf "%s" "$prompt" > /dev/tty
    IFS= read -r answer < /dev/tty
  elif [[ -t 0 ]]; then
    printf "%s" "$prompt"
    IFS= read -r answer
  else
    echo "error: this installer needs a terminal for confirmation. Re-run with --yes and --hermes-root PATH for non-interactive use." >&2
    exit 2
  fi
  printf "%s" "$answer"
}

is_hermes_root() {
  local path="$1"
  [[ -f "$path/gateway/platforms/slack.py" ]]
}

abs_path() {
  local path="$1"
  python3 - "$path" <<'PY'
import pathlib, sys
print(pathlib.Path(sys.argv[1]).expanduser().resolve())
PY
}

candidate_root_from_slack_py() {
  local slack_py="$1"
  dirname "$(dirname "$(dirname "$(dirname "$slack_py")")")"
}

add_candidate() {
  local path="$1"
  [[ -n "$path" ]] || return 0
  path="$(abs_path "$path" 2>/dev/null || true)"
  [[ -n "$path" ]] || return 0
  is_hermes_root "$path" || return 0
  CANDIDATES+=("$path")
}

unique_candidates() {
  local seen=":"
  local item
  UNIQUE_CANDIDATES=()
  for item in "${CANDIDATES[@]}"; do
    case "$seen" in
      *":$item:"*) ;;
      *)
        UNIQUE_CANDIDATES+=("$item")
        seen="${seen}${item}:"
        ;;
    esac
  done
}

confirm_root() {
  local path="$1"
  if [[ "$YES" -eq 1 ]]; then
    HERMES_ROOT="$path"
    return 0
  fi
  local answer
  answer="$(ask "Install /board into this Hermes checkout? [$path] [Y/n] ")"
  case "$answer" in
    ""|y|Y|yes|YES)
      HERMES_ROOT="$path"
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

prompt_for_root() {
  local answer
  while true; do
    answer="$(ask "Enter Hermes Agent checkout path: ")"
    if [[ -z "$answer" ]]; then
      say "No path entered. Aborting."
      exit 2
    fi
    answer="$(abs_path "$answer")"
    if is_hermes_root "$answer"; then
      HERMES_ROOT="$answer"
      return 0
    fi
    say "Not a Hermes Agent checkout: $answer"
    say "Expected file: gateway/platforms/slack.py"
  done
}

choose_root() {
  if [[ -n "$HERMES_ROOT" ]]; then
    HERMES_ROOT="$(abs_path "$HERMES_ROOT")"
    if ! is_hermes_root "$HERMES_ROOT"; then
      echo "error: not a Hermes Agent checkout: $HERMES_ROOT" >&2
      echo "expected file: $HERMES_ROOT/gateway/platforms/slack.py" >&2
      exit 2
    fi
    if [[ "$HERMES_ROOT_EXPLICIT" -eq 1 || "$YES" -eq 1 ]]; then
      confirm_root "$HERMES_ROOT" || prompt_for_root
    else
      confirm_root "$HERMES_ROOT" || prompt_for_root
    fi
    return 0
  fi

  CANDIDATES=()
  UNIQUE_CANDIDATES=()

  add_candidate "$HOME/.hermes/hermes-agent"
  add_candidate "$HOME/.hermes/hermes"
  add_candidate "$HOME/hermes-agent"
  add_candidate "/opt/hermes-agent"
  add_candidate "/srv/hermes-agent"
  add_candidate "$(pwd)"

  if [[ -d "$HOME/.hermes" ]]; then
    while IFS= read -r slack_py; do
      add_candidate "$(candidate_root_from_slack_py "$slack_py")"
    done < <(find "$HOME/.hermes" -maxdepth 5 -type f -path "*/gateway/platforms/slack.py" 2>/dev/null)
  fi

  unique_candidates

  case "${#UNIQUE_CANDIDATES[@]}" in
    0)
      say "Could not auto-detect a Hermes Agent checkout."
      prompt_for_root
      ;;
    1)
      say "Found Hermes Agent checkout:"
      say "  ${UNIQUE_CANDIDATES[0]}"
      confirm_root "${UNIQUE_CANDIDATES[0]}" || prompt_for_root
      ;;
    *)
      say "Found multiple Hermes Agent checkouts:"
      local i answer selected
      for i in "${!UNIQUE_CANDIDATES[@]}"; do
        printf "  %d) %s\n" "$((i + 1))" "${UNIQUE_CANDIDATES[$i]}"
      done
      if [[ "$YES" -eq 1 ]]; then
        HERMES_ROOT="${UNIQUE_CANDIDATES[0]}"
        say "Using first detected checkout because --yes was passed: $HERMES_ROOT"
        return 0
      fi
      while true; do
        answer="$(ask "Choose a checkout number, or type a path: ")"
        if [[ "$answer" =~ ^[0-9]+$ ]] && (( answer >= 1 && answer <= ${#UNIQUE_CANDIDATES[@]} )); then
          selected="${UNIQUE_CANDIDATES[$((answer - 1))]}"
        else
          selected="$(abs_path "$answer")"
        fi
        if is_hermes_root "$selected"; then
          confirm_root "$selected" || prompt_for_root
          return 0
        fi
        say "Not a Hermes Agent checkout: $selected"
      done
      ;;
  esac
}

choose_root

TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

echo "Hermes Slack /board installer"
echo "source: $ARCHIVE_URL"
echo "target: $HERMES_ROOT"
echo

curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/hermes-slack-board.tar.gz"
tar -xzf "$TMP_DIR/hermes-slack-board.tar.gz" -C "$TMP_DIR"

PKG_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'hermes-slack-board-*' | head -n 1)"
if [[ -z "$PKG_DIR" || ! -x "$PKG_DIR/scripts/install.sh" ]]; then
  echo "error: could not locate installer in downloaded archive" >&2
  exit 1
fi

"$PKG_DIR/scripts/install.sh" "$HERMES_ROOT" "${INSTALL_ARGS[@]}"
