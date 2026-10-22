"""Full native callback flows against real v0.22 adapter/SQLite; only Slack I/O is fake."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from test_native_plugin import App


class FlowTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Real schema migrations are synchronous; keep asyncio's test-debug
        # threshold above their expected duration, not at the default 100ms.
        import asyncio
        asyncio.get_running_loop().slow_callback_duration = 2.0

    def setUp(self):
        from gateway.config import PlatformConfig
        from plugins.platforms.slack.adapter import SlackAdapter
        from slack_board import wire_slack
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.env = patch.dict(os.environ, {
            'HERMES_KANBAN_HOME': self.temp.name, 'HERMES_HOME': self.temp.name,
            'HERMES_KANBAN_DB': str(Path(self.temp.name) / 'kanban.db'),
            'HERMES_KANBAN_BOARD': '', 'HERMES_KANBAN_TASK': '',
            'HERMES_DELEGATED_CHILD_CONTEXT': '',
        })
        self.env.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.env.stop)
        self.adapter = SlackAdapter(PlatformConfig())
        self.adapter.set_authorization_check(lambda user_id, chat_type, chat_id: user_id == 'U1')
        self.client = AsyncMock()
        self.client.chat_postMessage.return_value = {'ts': '1.1'}
        self.adapter._team_clients['T1'] = self.client
        self.adapter._app = object()
        self.app = App()
        wire_slack(self.app, self.adapter)
        self.body = {'user': {'id': 'U1'}, 'team': {'id': 'T1'},
                     'channel': {'id': 'C1'}, 'trigger_id': 'trigger', 'message': {'ts': '1.1'}}
        self.action = next(iter(self.app.actions.values()))

    async def slash(self, text):
        await self.app.commands['/board'](AsyncMock(), {
            'user_id': 'U1', 'team_id': 'T1', 'channel_id': 'C1',
            'text': text, 'trigger_id': 'trigger'})

    def view(self, task_id='', fields=None):
        return {'private_metadata': json.dumps({'channel_id': 'C1', 'message_ts': '1.1',
                                               'task_id': task_id, 'filters': {}}),
                'state': {'values': {key: {'value': {'value': value}} for key, value in (fields or {}).items()}}}

    def task(self, task_id):
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        with connect_closing() as conn:
            return kb.get_task(conn, task_id)

    async def test_slash_ui_private_text_public_text_and_filters(self):
        await self.slash('')
        self.assertIn('blocks', self.client.chat_postMessage.call_args.kwargs)
        self.assertEqual(self.adapter._bot_message_ts, set())
        await self.slash('-t --summary -s todo')
        self.client.chat_postEphemeral.assert_awaited_once()
        await self.slash('-t --public')
        self.assertNotIn('blocks', self.client.chat_postMessage.call_args.kwargs)
        await self.slash('-n "Slack new"')
        modal = self.client.views_open.call_args.kwargs['view']
        self.assertEqual(modal['callback_id'], 'hermes_board_task_create')
        self.assertIn('Blocked', json.dumps(modal))

    async def test_create_edit_detail_move_archive_through_native_callbacks(self):
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        from slack_board.renderer import action_value, move_action_value, BoardFilters
        await self.app.views['hermes_board_task_create'](AsyncMock(), self.body,
                                                       self.view(fields={'title': 'Native task', 'status': 'todo'}))
        with connect_closing() as conn:
            tasks = kb.list_tasks(conn)
        self.assertEqual(len(tasks), 1)
        self.assertIn('blocked', self.client.chat_postEphemeral.call_args.kwargs['text'])
        task_id = tasks[0].id
        await self.action(AsyncMock(), self.body, {'action_id': 'hermes_board_task_show',
                                                  'value': action_value('detail', task_id, BoardFilters())})
        self.assertEqual(self.client.views_open.call_args.kwargs['view']['callback_id'], 'hermes_board_task_detail')
        await self.app.views['hermes_board_task_detail'](AsyncMock(), self.body,
                                                        self.view(task_id, {'edit_title': 'Edited', 'edit_body': 'Body'}))
        self.assertEqual(self.task(task_id).title, 'Edited')
        view = self.view(task_id)
        view['state']['values'] = {'status': {'value': {'selected_option': {
            'value': move_action_value(task_id, 'blocked', BoardFilters())}}}}
        await self.app.views['hermes_board_task_move'](AsyncMock(), self.body, view)
        self.assertEqual(self.task(task_id).status, 'blocked')
        body = {**self.body, 'view': self.view(task_id)}
        await self.action(AsyncMock(), body, {'action_id': 'hermes_board_task_delete_from_detail',
                                            'value': action_value('archive', task_id, BoardFilters())})
        with connect_closing() as conn:
            self.assertNotIn(task_id, [task.id for task in kb.list_tasks(conn)])

    async def test_authorized_user_is_rechecked_on_each_view_submission(self):
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        kb.init_db()
        self.adapter.set_authorization_check(lambda user_id, chat_type, chat_id: False)
        await self.app.views['hermes_board_task_create'](AsyncMock(), self.body,
                                                       self.view(fields={'title': 'Forbidden', 'status': 'todo'}))
        with connect_closing() as conn:
            self.assertEqual(kb.list_tasks(conn), [])

    async def test_native_approval_and_request_changes_preserve_actor(self):
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        from slack_board.renderer import action_value, BoardFilters
        with connect_closing() as conn:
            task_id = kb.create_task(conn, title='Approval pending', assignee='default')
            kb.block_task(conn, task_id, reason='Approval required before sending')
        body = {**self.body, 'view': self.view(task_id)}
        value = action_value('request_changes', task_id, BoardFilters())
        await self.action(AsyncMock(), body, {'action_id': 'hermes_board_task_request_changes', 'value': value})
        modal = self.client.views_push.call_args.kwargs['view']
        modal['state'] = {'values': {'feedback': {'value': {'value': 'Shorten the title'}}}}
        await self.app.views['hermes_board_task_request_changes'](AsyncMock(), self.body, modal)
        self.assertEqual(self.task(task_id).status, 'blocked')
        await self.action(AsyncMock(), body, {'action_id': 'hermes_board_task_approve_continue',
                                            'value': action_value('approve', task_id, BoardFilters())})
        self.assertEqual(self.task(task_id).status, 'ready')
        with connect_closing() as conn:
            comments = '\n'.join(comment.body for comment in kb.list_comments(conn, task_id))
        self.assertIn('U1', comments)
        self.assertIn('Shorten the title', comments)

    async def test_implicit_board_is_pinned_across_current_board_switch(self):
        from hermes_cli import kanban_db as kb
        from hermes_cli.kanban_db_connect import connect_closing
        from slack_board.renderer import filters_from_value
        os.environ.pop('HERMES_KANBAN_DB', None)
        kb.create_board('alpha')
        kb.create_board('bravo')
        kb.set_current_board('alpha')
        with connect_closing(board='alpha') as conn:
            task_id = kb.create_task(conn, title='Alpha task')
        await self.slash('')
        blocks = self.client.chat_postMessage.call_args.kwargs['blocks']
        def actions(value):
            if isinstance(value, dict):
                if isinstance(value.get('value'), str) and value['value'].startswith('{'):
                    yield value
                for child in value.values():
                    yield from actions(child)
            elif isinstance(value, list):
                for child in value:
                    yield from actions(child)
        rendered = list(actions(blocks))
        self.assertTrue(rendered)
        for action in rendered:
            self.assertEqual(filters_from_value(action['value']).board, 'alpha', action)
        add = next(a for a in rendered if a['action_id'] == 'hermes_board_task_add')
        kb.set_current_board('bravo')
        await self.action(AsyncMock(), self.body, add)
        modal = self.client.views_open.call_args.kwargs['view']
        self.assertEqual(json.loads(modal['private_metadata'])['filters']['board'], 'alpha')
        modal['state'] = self.view(fields={'title': 'Pinned creation', 'status': 'todo'})['state']
        await self.app.views['hermes_board_task_create'](AsyncMock(), self.body, modal)
        with connect_closing(board='alpha') as conn:
            self.assertIn('Pinned creation', [t.title for t in kb.list_tasks(conn)])
        with connect_closing(board='bravo') as conn:
            self.assertEqual(kb.list_tasks(conn), [])
        for command in ('-n Command task', f'-e {task_id}', f'--detail {task_id}', f'-d {task_id}'):
            kb.set_current_board('alpha')
            await self.slash(command)
            modal = self.client.views_open.call_args.kwargs['view']
            self.assertEqual(json.loads(modal['private_metadata'])['filters']['board'], 'alpha', command)
            if command.startswith('-n'):
                kb.set_current_board('bravo')
                modal['state'] = self.view(fields={'title': 'Pinned command creation', 'status': 'todo'})['state']
                await self.app.views['hermes_board_task_create'](AsyncMock(), self.body, modal)
                with connect_closing(board='alpha') as conn:
                    self.assertIn('Pinned command creation', [t.title for t in kb.list_tasks(conn)])
                with connect_closing(board='bravo') as conn:
                    self.assertEqual(kb.list_tasks(conn), [])
        kb.set_current_board('bravo')

    async def test_native_factory_accepts_actual_bolt_app(self):
        from slack_bolt.async_app import AsyncApp
        from slack_bolt.authorization import AuthorizeResult
        from slack_board import wire_slack
        async def authorize(enterprise_id, team_id, user_id):
            return AuthorizeResult(enterprise_id=enterprise_id, team_id=team_id, bot_user_id='B1')
        app = AsyncApp(authorize=authorize, signing_secret='local-test-only')
        wire_slack(app, self.adapter)
        self.assertEqual(len(app._async_listeners), 6)
