"""Native plugin contracts; run with Hermes' PM launcher and stdlib unittest."""
import importlib
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Context:
    def __init__(self):
        self.factories = []
    def register_platform_handler(self, platform, factory):
        self.factories.append((platform, factory))


class App:
    def __init__(self):
        self.commands, self.actions, self.views = {}, {}, {}
    def command(self, key):
        return lambda fn: self.commands.setdefault(key, fn)
    def action(self, key):
        return lambda fn: self.actions.setdefault(key, fn)
    def view(self, key):
        return lambda fn: self.views.setdefault(key, fn)


class Adapter:
    def __init__(self, allowed=False):
        self.allowed = allowed
        self.auth_calls = []
    def _is_interactive_user_authorized(self, user_id, **kwargs):
        self.auth_calls.append((user_id, kwargs))
        return self.allowed
    def __getattr__(self, name):
        raise AssertionError('Unauthorized adapter access: ' + name)


class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_every_entrypoint_denies_before_reading_or_writing(self):
        from slack_board import wire_slack
        from unittest.mock import AsyncMock
        app, adapter = App(), Adapter()
        wire_slack(app, adapter)
        body = {'user': {'id': 'Ubad'}, 'team': {'id': 'T1'}, 'channel': {'id': 'C1'}}
        ack = AsyncMock()
        await app.commands['/board'](ack, {'user_id': 'Ubad', 'channel_id': 'C1', 'team_id': 'T1'})
        await next(iter(app.actions.values()))(ack, body, {'action_id': 'hermes_board_refresh'})
        for callback, handler in app.views.items():
            modal_body = {key: value for key, value in body.items() if key != 'channel'}
            await handler(ack, modal_body, {'callback_id': callback, 'private_metadata': '{"channel_id":"C1"}'})
        self.assertEqual(ack.await_count, 6)
        self.assertEqual(len(adapter.auth_calls), 6)
        self.assertTrue(all(u == 'Ubad' and kw['channel_id'] == 'C1' and kw['team_id'] == 'T1'
                            for u, kw in adapter.auth_calls))

    async def test_auth_failure_fails_closed(self):
        from slack_board import wire_slack
        from unittest.mock import AsyncMock
        app = App()
        wire_slack(app, object())
        ack = AsyncMock()
        await app.commands['/board'](ack, {'user_id': 'U1'})
        ack.assert_awaited_once()


class WorkspaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_duplicate_action_does_not_release_another_requests_lock(self):
        from slack_board.controller import BoardController
        from unittest.mock import AsyncMock
        board = BoardController(Adapter(True))
        key = board._board_action_lock_key('C1', '1')
        self.assertTrue(board._try_acquire_board_action_lock(key))
        await board._handle_board_action(AsyncMock(), {'channel': {'id': 'C1'}, 'message': {'ts': '1'}},
                                        {'action_id': 'hermes_board_refresh', 'value': '{}'})
        self.assertIn(key, board._board_action_locks)

    async def test_slash_uses_explicit_workspace_without_mutating_adapter(self):
        from slack_board import wire_slack
        from unittest.mock import AsyncMock
        from types import SimpleNamespace, MappingProxyType
        client = SimpleNamespace(chat_postEphemeral=AsyncMock())
        adapter = Adapter(True)
        adapter._app = object()
        adapter._channel_team = MappingProxyType({})
        adapter.build_source = lambda **kw: SimpleNamespace(**kw, thread_id=None)
        calls = []
        def get_client(channel, team_id=None):
            calls.append((channel, team_id))
            return client
        adapter._get_client = get_client
        app = App()
        wire_slack(app, adapter)
        await app.commands['/board'](AsyncMock(), {
            'user_id': 'U1', 'channel_id': 'C1', 'team_id': 'T2', 'text': '--help'})
        client.chat_postEphemeral.assert_awaited_once()
        self.assertEqual(calls, [('C1', 'T2')])


class RegistrationTests(unittest.TestCase):
    def test_registers_scoped_slack_factory(self):
        plugin = importlib.import_module('slack_board')
        ctx = Context()
        plugin.register(ctx)
        self.assertEqual([x[0] for x in ctx.factories], ['slack'])
        app = App()
        ctx.factories[0][1](app, object())
        self.assertIn('/board', app.commands)
        self.assertEqual(set(app.views), {
            'hermes_board_task_create', 'hermes_board_task_detail',
            'hermes_board_task_move', 'hermes_board_task_request_changes'})
        self.assertEqual(len(app.actions), 1)
        pattern = next(iter(app.actions))
        self.assertTrue(pattern.match('hermes_board_refresh'))
        self.assertIsNone(pattern.match('hermes_approve'))
