#!/usr/bin/env python3
"""Validate the hermes-slack-board-setup skill package."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_FILES = [
    "SKILL.md",
    "references/slack-app-checklist.md",
    "references/app-configuration-token.md",
    "references/board-command-options.md",
    "references/troubleshooting.md",
    "scripts/validate_setup.py",
]

SECRET_PATTERNS = [
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{20,}"),
    re.compile(r"xapp-[A-Za-z0-9-]{20,}"),
    re.compile(r"xoxe\.[A-Za-z0-9._-]{20,}"),
    re.compile(r"(?i)(api[_-]?key|token|secret)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{24,}"),
]


def check_frontmatter(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    errors: list[str] = []
    if not text.startswith("---\n"):
        return [f"{path}: missing YAML frontmatter"]
    end = text.find("\n---\n", 4)
    if end == -1:
        return [f"{path}: unterminated YAML frontmatter"]
    frontmatter = text[4:end]
    for key in ("name:", "description:"):
        if key not in frontmatter:
            errors.append(f"{path}: missing frontmatter key {key.rstrip(':')}")
    return errors


def scan_secrets(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            return [f"{path}: possible secret detected"]
    return []


def main() -> int:
    root = Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else Path.cwd()
    errors: list[str] = []

    for rel in REQUIRED_FILES:
        if not (root / rel).exists():
            errors.append(f"missing required file: {rel}")

    if (root / "SKILL.md").exists():
        errors.extend(check_frontmatter(root / "SKILL.md"))

    for path in root.rglob("*"):
        if path.is_file():
            errors.extend(scan_secrets(path))

    if errors:
        print("Validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"Validation passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
