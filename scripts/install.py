#!/usr/bin/env python3
"""Install the experimental Slack /board UI into a Hermes Agent checkout."""

from __future__ import annotations

import argparse
import datetime as dt
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

SUPPORTED_VERSIONS = ("0.12.0", "0.13.0")


def detect_hermes_version(hermes_root: Path) -> str | None:
    pyproject = hermes_root / "pyproject.toml"
    if not pyproject.exists():
        return None
    for line in pyproject.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("version") and "=" in stripped:
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    return None


BOARD_COMMAND_SNIPPET = '''\
            @self._app.command("/board")
            async def handle_board_command(ack, command):
                await ack(
                    response_type="ephemeral",
                    text="Opening Kanban board...",
                )
                logger.info("[Slack] Received /board command from %s in %s", command.get("user_id"), command.get("channel_id"))
                asyncio.create_task(self._handle_board_slash_background(dict(command)))

'''


BOARD_ACTION_SNIPPET = '''\
            # Register Block Kit action handlers for the Slack Kanban board.
            self._app.action(_re.compile(r"^hermes_board_"))(self._handle_board_action)
            self._app.view("hermes_board_task_create")(self._handle_board_create_view)
            self._app.view("hermes_board_task_move")(self._handle_board_move_view)
            self._app.view("hermes_board_task_detail")(self._handle_board_detail_view)
            self._app.view("hermes_board_task_request_changes")(self._handle_board_request_changes_view)

'''


LOCK_SNIPPET = '''\
        # Kanban board message locks: prevent repeated clicks from executing
        # multiple mutations while Slack is still repainting the message.
        self._board_action_locks: Dict[str, float] = {}
'''


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def git_dirty_files(cwd: Path) -> list[str]:
    if not (cwd / ".git").exists():
        return []
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "gateway/platforms/slack.py"],
        cwd=cwd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def backup_file(path: Path, backup_root: Path, hermes_root: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(hermes_root)
    dest = backup_root / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dest)


def copy_overlay(src_rel: str, dst_rel: str, hermes_root: Path) -> None:
    src = ROOT / "overlays" / src_rel
    dst = hermes_root / dst_rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"copied {dst_rel}")


def patch_slack_py(slack_py: Path) -> list[str]:
    warnings: list[str] = []
    text = slack_py.read_text()

    if "_board_action_locks" not in text:
        marker = "        self._slash_command_contexts: Dict[Tuple[str, str], Dict[str, Any]] = {}\n"
        if marker not in text:
            raise RuntimeError("Could not find SlackAdapter slash-command context marker.")
        text = text.replace(marker, marker + LOCK_SNIPPET, 1)

    if '@self._app.command("/board")' not in text:
        marker = "            import re as _re\n\n"
        if marker not in text:
            raise RuntimeError("Could not find Slack command registration import marker.")
        text = text.replace(marker, marker + BOARD_COMMAND_SNIPPET, 1)

    single_line = "            _slash_names = [name for name, _d, _h in slack_native_slashes()]\n"
    filtered = '''\
            _slash_names = [
                name for name, _d, _h in slack_native_slashes()
                if name != "board"
            ]
'''
    if single_line in text:
        text = text.replace(single_line, filtered, 1)
    elif 'if name != "board"' not in text:
        warnings.append("Could not auto-filter /board out of the generic slash regex; review slack.py manually.")

    if "hermes_board_task_create" not in text:
        marker = "            # Start Socket Mode handler in background\n"
        if marker not in text:
            raise RuntimeError("Could not find Socket Mode start marker.")
        text = text.replace(marker, BOARD_ACTION_SNIPPET + marker, 1)

    methods = (ROOT / "overlays/gateway/platforms/slack_board_methods.pyfrag").read_text().rstrip()
    methods_start = "    async def send_kanban_board"
    methods_end = "    async def _handle_slash_confirm_action"
    if methods_end not in text:
        raise RuntimeError("Could not find slash confirm handler insertion marker.")
    if methods_start in text:
        start = text.index(methods_start)
        end = text.index(methods_end, start)
        text = text[:start] + methods + "\n\n" + text[end:]
    else:
        text = text.replace(methods_end, methods + "\n\n" + methods_end, 1)

    slack_py.write_text(text)
    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Hermes Slack /board UI.")
    parser.add_argument(
        "hermes_root",
        nargs="?",
        default=str(Path.home() / ".hermes/hermes-agent"),
        help="Hermes Agent checkout root. Defaults to ~/.hermes/hermes-agent",
    )
    parser.add_argument("--skip-tests", action="store_true", help="Skip pytest after install.")
    parser.add_argument(
        "--skip-git-check",
        action="store_true",
        help="Do not warn when gateway/platforms/slack.py has local changes.",
    )
    args = parser.parse_args()

    hermes_root = Path(args.hermes_root).expanduser().resolve()
    slack_py = hermes_root / "gateway/platforms/slack.py"
    if not slack_py.exists():
        print(f"error: {slack_py} does not exist", file=sys.stderr)
        return 2

    detected = detect_hermes_version(hermes_root)
    if detected:
        print(f"detected Hermes Agent version: {detected}")
        if detected not in SUPPORTED_VERSIONS:
            print(
                f"warning: this installer was tested against {', '.join(SUPPORTED_VERSIONS)}; "
                f"{detected} may have shifted slack.py markers."
            )
    else:
        print("warning: could not detect Hermes Agent version (pyproject.toml missing)")

    if not args.skip_git_check:
        dirty = git_dirty_files(hermes_root)
        if dirty:
            print("warning: gateway/platforms/slack.py has local changes:")
            for line in dirty:
                print(f"  {line}")
            print("The installer will back it up before patching. Use --skip-git-check to hide this warning.")

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = Path.home() / ".hermes/backups" / f"hermes-slack-board-{stamp}"
    for rel in (
        "gateway/platforms/slack.py",
        "gateway/platforms/slack_kanban_board.py",
        "tests/test_slack_kanban_board.py",
    ):
        backup_file(hermes_root / rel, backup_root, hermes_root)
    print(f"backup: {backup_root}")

    warnings = patch_slack_py(slack_py)
    copy_overlay("gateway/platforms/slack_kanban_board.py", "gateway/platforms/slack_kanban_board.py", hermes_root)
    copy_overlay("tests/test_slack_kanban_board.py", "tests/test_slack_kanban_board.py", hermes_root)

    python = hermes_root / "venv/bin/python"
    if not python.exists():
        python = Path(sys.executable)

    run([str(python), "-m", "py_compile", "gateway/platforms/slack.py", "gateway/platforms/slack_kanban_board.py"], hermes_root)
    if not args.skip_tests:
        run([str(python), "-m", "pytest", "tests/test_slack_kanban_board.py"], hermes_root)

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")

    print("\nInstalled Hermes Slack /board UI.")
    print("Next: add /board to your Slack app slash commands, enable Interactivity, reinstall the app, then restart the Hermes gateway.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
