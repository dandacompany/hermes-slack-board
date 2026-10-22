"""Blocking review regressions on the installed v0.22.4 SQLite lifecycle."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hermes_cli import kanban_db as kb
from hermes_cli.kanban_db_connect import connect_closing
from slack_board.renderer import BoardFilters, move_task_status


class RuntimeRegressions(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(dir=ROOT / 'tests')
        self.addCleanup(temp.cleanup)
        env = patch.dict(os.environ, {
            'HERMES_HOME': temp.name, 'HERMES_KANBAN_HOME': temp.name,
            'HERMES_KANBAN_DB': str(Path(temp.name) / 'kanban.db'),
            'HERMES_KANBAN_BOARD': '', 'HERMES_KANBAN_TASK': '',
            'HERMES_DELEGATED_CHILD_CONTEXT': '',
        })
        env.start()
        self.addCleanup(env.stop)
        kb.init_db()

    def test_move_done_preserves_native_completion_lifecycle(self):
        # One transition contract, exercised against real v0.22.4 persistence.
        with self.subTest(case='incomplete ancestor cannot be bypassed'):
            with connect_closing() as conn:
                parent = kb.create_task(conn, title='Open ancestor')
                child = kb.create_task(conn, title='Waiting child', parents=[parent])
                grandchild = kb.create_task(conn, title='Waiting grandchild', parents=[child])
                self.assertFalse(kb.complete_task(conn, child, result='Native refusal'))
            notice = move_task_status(child, 'done', BoardFilters())
            with connect_closing() as conn:
                kb.recompute_ready(conn)
                self.assertEqual(kb.get_task(conn, child).status, 'todo')
                self.assertIsNone(kb.get_task(conn, child).completed_at)
                self.assertEqual(kb.get_task(conn, grandchild).status, 'todo')
                self.assertIsNone(kb.claim_task(conn, grandchild))
                self.assertFalse(any(e.kind == 'completed' for e in kb.list_events(conn, child)))
            self.assertIn('Could not complete', notice)

        with self.subTest(case='valid completion retains native audit and promotion'):
            with connect_closing() as conn:
                task_id = kb.create_task(conn, title='Manual completion')
                dependent = kb.create_task(conn, title='Released child', parents=[task_id])
            notice = move_task_status(task_id, 'done', BoardFilters())
            with connect_closing() as conn:
                task = kb.get_task(conn, task_id)
                self.assertEqual(task.status, 'done')
                self.assertIsNotNone(task.completed_at)
                self.assertEqual(task.result, 'Completed from Slack /board.')
                run = kb.latest_run(conn, task_id)
                self.assertIsNotNone(run, 'manual completion needs a native audit run')
                self.assertEqual(run.outcome, 'completed')
                self.assertEqual(run.summary, task.result)
                completed = [e for e in kb.list_events(conn, task_id) if e.kind == 'completed']
                self.assertEqual(len(completed), 1)
                self.assertEqual(completed[0].run_id, run.id)
                self.assertFalse(any(e.kind == 'moved' for e in kb.list_events(conn, task_id)))
                self.assertEqual(kb.get_task(conn, dependent).status, 'ready')
                self.assertIsNotNone(kb.claim_task(conn, dependent))
            self.assertIn('done', notice)

        with self.subTest(case='live worker ownership error is preserved'):
            import subprocess
            from hermes_cli import kanban_db_dispatch as dispatch
            worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
            def cleanup():
                if worker.poll() is None:
                    worker.kill()
                worker.wait(timeout=10)
            self.addCleanup(cleanup)
            with connect_closing() as conn:
                task_id = kb.create_task(conn, title='Live completion guard')
                claim = kb.claim_task(conn, task_id)
                self.assertIsNotNone(claim)
                dispatch._set_worker_pid(conn, task_id, worker.pid)
                with self.assertRaises(kb.LiveClaimError):
                    kb.complete_task(conn, task_id, result='Native refusal')
            with self.assertRaises(kb.LiveClaimError):
                move_task_status(task_id, 'done', BoardFilters())
            with connect_closing() as conn:
                task = kb.get_task(conn, task_id)
                self.assertEqual(task.status, 'running')
                self.assertEqual(task.claim_lock, claim.claim_lock)
                self.assertEqual(task.current_run_id, claim.current_run_id)
                self.assertEqual(task.worker_pid, worker.pid)
                self.assertIsNone(task.completed_at)
                self.assertIsNone(kb.latest_run(conn, task_id).outcome)
                self.assertFalse(any(e.kind == 'completed' for e in kb.list_events(conn, task_id)))
            self.assertIsNone(worker.poll())

    def test_done_parent_reopen_invalidates_descendants_before_worker_termination(self):
        import subprocess
        from hermes_cli import kanban_db_dispatch as dispatch
        worker = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
        def cleanup():
            if worker.poll() is None:
                worker.kill()
            worker.wait(timeout=10)
        self.addCleanup(cleanup)
        with connect_closing() as conn:
            parent = kb.create_task(conn, title='Completed parent')
            self.assertTrue(kb.complete_task(conn, parent, result='done'))
            done_child = kb.create_task(conn, title='Completed child', parents=[parent])
            self.assertTrue(kb.complete_task(conn, done_child, result='done'))
            running = kb.create_task(conn, title='Running grandchild', parents=[done_child])
            claim = kb.claim_task(conn, running)
            self.assertIsNotNone(claim)
            dispatch._set_worker_pid(conn, running, worker.pid)
            ready = kb.create_task(conn, title='Ready child', parents=[parent])
            review = kb.create_task(conn, title='Review child', parents=[parent])
            self.assertTrue(kb.request_review(conn, review, summary='Review pending'))
        terminated = []
        terminate = kb._terminate_reclaimed_worker
        def terminate_after_commit(pid, claim_lock, *, started_at=None):
            with connect_closing() as side:
                self.assertEqual(kb.get_task(side, parent).status, 'ready')
                self.assertIsNone(kb.get_task(side, parent).completed_at)
                for tid in (done_child, running, ready, review):
                    task = kb.get_task(side, tid)
                    self.assertEqual(task.status, 'todo')
                    self.assertIsNone(task.current_run_id)
                    self.assertIsNone(task.claim_lock)
                    self.assertIsNone(task.completed_at)
                    events = kb.list_events(side, tid)
                    self.assertTrue(any(e.kind == 'descendant_invalidated' and e.payload['ancestor'] == parent for e in events))
                    self.assertTrue(any(parent in c.body for c in kb.list_comments(side, tid)))
                self.assertEqual(kb.latest_run(side, running).outcome, 'reclaimed')
            terminated.append((pid, claim_lock, started_at))
            return terminate(pid, claim_lock, started_at=started_at)
        with patch.object(kb, '_terminate_reclaimed_worker', side_effect=terminate_after_commit):
            move_task_status(parent, 'ready', BoardFilters())
        self.assertEqual(len(terminated), 1, 'active grandchild must be terminated after commit')
        self.assertEqual(terminated[0][0], worker.pid)
        self.assertEqual(terminated[0][1], claim.claim_lock)
        worker.wait(timeout=10)
        self.assertIsNotNone(worker.returncode)
        with connect_closing() as conn:
            kb.recompute_ready(conn)
            self.assertIsNone(kb.claim_task(conn, running))
            self.assertFalse(kb.complete_task(conn, running, result='stale', expected_run_id=claim.current_run_id))

    def test_creation_never_exposes_ready_before_manual_hold(self):
        from slack_board.renderer import create_task_for_status
        create = kb.create_task
        observations = []
        claims = []
        def interleaved_create(conn, **kwargs):
            task_id = create(conn, **kwargs)
            # Deterministic dispatcher interleaving exactly at the old commit
            # gap. This is a second real SQLite connection, not a fake claim.
            with connect_closing() as dispatcher:
                visible = kb.get_task(dispatcher, task_id)
                observations.append(visible.status if visible else None)
                if visible and visible.status == 'ready':
                    claims.append(kb.claim_task(dispatcher, task_id))
            return task_id
        with patch.object(kb, 'create_task', side_effect=interleaved_create):
            task_id, _ = create_task_for_status(status='todo', title='Not queued')
        with connect_closing() as conn:
            task = kb.get_task(conn, task_id)
            self.assertFalse(claims, 'dispatcher claimed during create/final-state gap')
            self.assertNotIn('ready', observations)
            self.assertEqual(task.status, 'blocked')
            self.assertIsNone(task.current_run_id)
            self.assertIsNone(task.claim_lock)
            for _ in range(3):
                kb.recompute_ready(conn)
                self.assertEqual(kb.get_task(conn, task_id).status, 'blocked')
                self.assertIsNone(kb.claim_task(conn, task_id))
            created = next(e for e in kb.list_events(conn, task_id) if e.kind == 'created')
            self.assertEqual(created.payload['status'], 'blocked')
        move_task_status(task_id, 'ready', BoardFilters())
        with connect_closing() as conn:
            self.assertIsNotNone(kb.claim_task(conn, task_id))

    def test_done_reopen_all_manual_destinations_regate_descendants(self):
        for requested, expected in (('todo', 'blocked'), ('blocked', 'blocked'), ('triage', 'triage'), ('ready', 'ready')):
            with self.subTest(requested=requested):
                with connect_closing() as conn:
                    parent = kb.create_task(conn, title='Parent')
                    self.assertTrue(kb.complete_task(conn, parent, result='done'))
                    child = kb.create_task(conn, title='Child', parents=[parent])
                    self.assertTrue(kb.complete_task(conn, child, result='done'))
                move_task_status(parent, requested, BoardFilters())
                with connect_closing() as conn:
                    self.assertEqual(kb.get_task(conn, parent).status, expected)
                    self.assertIsNone(kb.get_task(conn, parent).completed_at)
                    kb.recompute_ready(conn)
                    self.assertEqual(kb.get_task(conn, child).status, 'todo')
                    self.assertIsNone(kb.claim_task(conn, child))

    def test_failed_descendant_invalidation_rolls_back_entire_reopen(self):
        with connect_closing() as conn:
            parent = kb.create_task(conn, title='Parent')
            self.assertTrue(kb.complete_task(conn, parent, result='done'))
            child = kb.create_task(conn, title='Child', parents=[parent])
            claim = kb.claim_task(conn, child)
        invalidate = kb.invalidate_descendants_for_parent_reopen
        def fail_after_invalidation(*args, **kwargs):
            invalidate(*args, **kwargs)
            raise RuntimeError('injected invalidation failure')
        with patch.object(kb, 'invalidate_descendants_for_parent_reopen', side_effect=fail_after_invalidation), patch.object(kb, '_terminate_reclaimed_worker') as terminate:
            with self.assertRaisesRegex(RuntimeError, 'injected invalidation failure'):
                move_task_status(parent, 'ready', BoardFilters())
            terminate.assert_not_called()
        with connect_closing() as conn:
            self.assertEqual(kb.get_task(conn, parent).status, 'done')
            self.assertIsNotNone(kb.get_task(conn, parent).completed_at)
            self.assertEqual(kb.get_task(conn, child).status, 'running')
            self.assertEqual(kb.get_task(conn, child).current_run_id, claim.current_run_id)
            self.assertIsNone(kb.latest_run(conn, child).outcome)
            self.assertFalse(any(e.kind == 'descendant_invalidated' for e in kb.list_events(conn, child)))

    def test_manual_creation_hold_survives_parent_completion(self):
        from slack_board.renderer import create_task_for_status
        with connect_closing() as conn:
            parent = kb.create_task(conn, title='Open parent')
        child, _ = create_task_for_status(status='todo', title='Manual child', parents=[parent])
        with connect_closing() as conn:
            self.assertEqual(kb.parent_ids(conn, child), [parent])
            self.assertEqual(kb.get_task(conn, child).status, 'blocked')
            self.assertTrue(kb.complete_task(conn, parent, result='done'))
            kb.recompute_ready(conn)
            self.assertEqual(kb.get_task(conn, child).status, 'blocked')
            self.assertIsNone(kb.claim_task(conn, child))
        move_task_status(child, 'ready', BoardFilters())
        with connect_closing() as conn:
            self.assertIsNotNone(kb.claim_task(conn, child))

    def test_ready_selection_retains_dependency_gate(self):
        from slack_board.renderer import create_task_for_status
        with connect_closing() as conn:
            parent = kb.create_task(conn, title='Open parent')
        child, _ = create_task_for_status(status='todo', title='Manual child', parents=[parent])
        move_task_status(child, 'ready', BoardFilters())
        with connect_closing() as conn:
            self.assertEqual(kb.get_task(conn, child).status, 'todo')
            self.assertIsNone(kb.claim_task(conn, child))
            self.assertTrue(kb.complete_task(conn, parent, result='done'))
            kb.recompute_ready(conn)
            self.assertEqual(kb.get_task(conn, child).status, 'ready')
            self.assertIsNotNone(kb.claim_task(conn, child))

    def test_manual_todo_and_blocked_survive_dispatcher_until_explicit_ready(self):
        from slack_board.renderer import build_board_blocks
        # Runtime Todo means dependency wait, not an operator hold. Slack Todo
        # must safely park in sticky Blocked instead of pretending it can hold.
        for requested in ('todo', 'blocked'):
            with self.subTest(requested=requested):
                with connect_closing() as conn:
                    task_id = kb.create_task(conn, title='Manual ' + requested)
                notice = move_task_status(task_id, requested, BoardFilters())
                self.assertIn('Moved', notice)
                build_board_blocks(BoardFilters())
                with connect_closing() as conn:
                    for _ in range(3):
                        kb.recompute_ready(conn)
                        self.assertEqual(kb.get_task(conn, task_id).status, 'blocked')
                        self.assertIsNone(kb.claim_task(conn, task_id))
                    self.assertTrue(any(e.kind == 'blocked' for e in kb.list_events(conn, task_id)))
                move_task_status(task_id, 'ready', BoardFilters())
                with connect_closing() as conn:
                    self.assertEqual(kb.get_task(conn, task_id).status, 'ready')
                    self.assertIsNotNone(kb.claim_task(conn, task_id))

    def test_manual_hold_reclaims_active_worker_after_durable_block(self):
        from hermes_cli import kanban_db_dispatch as dispatch
        with connect_closing() as conn:
            task_id = kb.create_task(conn, title='Active work')
            claim = kb.claim_task(conn, task_id)
            dispatch._set_worker_pid(conn, task_id, 424242)
        def after_commit(pid, claim_lock, *, started_at=None):
            self.assertEqual(pid, 424242)
            self.assertEqual(claim_lock, claim.claim_lock)
            with connect_closing() as side:
                task = kb.get_task(side, task_id)
                self.assertEqual(task.status, 'blocked')
                self.assertIsNone(task.current_run_id)
                self.assertIsNone(task.claim_lock)
                self.assertEqual(kb.latest_run(side, task_id).outcome, 'blocked')
                self.assertTrue(any(e.kind == 'blocked' for e in kb.list_events(side, task_id)))
            return {'terminated': True}
        with patch.object(kb, '_terminate_reclaimed_worker', side_effect=after_commit) as terminate:
            move_task_status(task_id, 'blocked', BoardFilters())
            terminate.assert_called_once()

    def test_manual_hold_escalation_still_terminates_active_worker(self):
        from hermes_cli import kanban_db_dispatch as dispatch
        with connect_closing() as conn:
            task_id = kb.create_task(conn, title='Repeated manual hold')
        for _ in range(kb.BLOCK_RECURRENCE_LIMIT - 1):
            move_task_status(task_id, 'blocked', BoardFilters())
            move_task_status(task_id, 'ready', BoardFilters())
        with connect_closing() as conn:
            self.assertIsNotNone(kb.claim_task(conn, task_id))
            dispatch._set_worker_pid(conn, task_id, 424242)
        with patch.object(kb, '_terminate_reclaimed_worker', return_value={'terminated': True}) as terminate:
            move_task_status(task_id, 'blocked', BoardFilters())
            terminate.assert_called_once()
        with connect_closing() as conn:
            self.assertEqual(kb.get_task(conn, task_id).status, 'triage')
            kb.recompute_ready(conn)
            self.assertIsNone(kb.claim_task(conn, task_id))

    def test_move_option_size_fallback_never_drops_board_identity(self):
        from slack_board.renderer import move_action_value, parse_move_action_value
        value = move_action_value('t_12345678', 'ready', BoardFilters(board='alpha', tenant='x' * 200))
        self.assertLessEqual(len(value), 150)
        self.assertEqual(parse_move_action_value(value)[2].board, 'alpha')
