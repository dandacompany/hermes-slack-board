"""Tests for ``scripts/install.py`` patching a real Hermes ``slack.py``.

These tests exercise the installer's string-marker patch against an actual
Hermes checkout (``HERMES_ROOT`` env var, default ``~/.hermes/hermes-agent``).
The checkout is only ever *read*: ``slack.py`` is copied into a temp dir and
patched there, so the live working tree is never mutated.

They reproduce the clean-install IndentationError caused by the trailing
body-less ``_handle_slash_confirm_action`` anchor in the methods fragment, and
guard the re-install (replace) path against the same regression class.
"""

from __future__ import annotations

import importlib.util
import os
import py_compile
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONFIRM_SIG = "async def _handle_slash_confirm_action("


def _load_install():
    spec = importlib.util.spec_from_file_location("install", ROOT / "scripts/install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _hermes_slack_py() -> Path | None:
    root = Path(os.environ.get("HERMES_ROOT", Path.home() / ".hermes/hermes-agent"))
    slack_py = root / "gateway/platforms/slack.py"
    return slack_py if slack_py.exists() else None


def _patched_copy(tmp_path: Path, *, applications: int = 1) -> Path:
    src = _hermes_slack_py()
    if src is None:
        pytest.skip("no Hermes checkout found (set HERMES_ROOT)")
    target = tmp_path / "slack.py"
    shutil.copy2(src, target)
    install = _load_install()
    for _ in range(applications):
        install.patch_slack_py(target)
    return target


def test_clean_install_patch_compiles(tmp_path):
    """Patching a pristine upstream slack.py must yield valid Python."""
    target = _patched_copy(tmp_path)
    py_compile.compile(str(target), doraise=True)


def test_clean_install_yields_single_confirm_handler(tmp_path):
    """The methods splice must not duplicate _handle_slash_confirm_action."""
    target = _patched_copy(tmp_path)
    assert target.read_text().count(CONFIRM_SIG) == 1


def test_reinstall_is_idempotent_and_compiles(tmp_path):
    """Re-running the installer (replace path) stays valid and single-defined."""
    target = _patched_copy(tmp_path, applications=2)
    py_compile.compile(str(target), doraise=True)
    assert target.read_text().count(CONFIRM_SIG) == 1


def test_assert_helper_accepts_single_bodied_confirm():
    install = _load_install()
    valid = (
        "    async def _handle_slash_confirm_action(self, ack, body, action) -> None:\n"
        "        await ack()\n"
    )
    install._assert_single_bodied_confirm(valid)  # must not raise


def test_supported_versions_cover_0_15_x():
    """The version gate should recognise the 0.15.x line as tested."""
    install = _load_install()
    assert "0.15.1" in install.SUPPORTED_VERSIONS
    assert "0.15.0" in install.SUPPORTED_VERSIONS


def test_assert_helper_rejects_bodyless_single():
    install = _load_install()
    bodyless = (
        "    async def _handle_slash_confirm_action(self, ack, body, action) -> None:\n"
    )
    with pytest.raises(RuntimeError):
        install._assert_single_bodied_confirm(bodyless)


def test_assert_helper_rejects_bodyless_duplicate():
    install = _load_install()
    bodyless_dup = (
        "    async def _handle_slash_confirm_action(self, ack, body, action) -> None:\n"
        "\n"
        "    async def _handle_slash_confirm_action(self, ack, body, action) -> None:\n"
        "        await ack()\n"
    )
    with pytest.raises(RuntimeError):
        install._assert_single_bodied_confirm(bodyless_dup)
