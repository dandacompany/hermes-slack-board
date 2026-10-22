"""Hermes v0.22 native Slack board extension (no core overlays)."""
import json
import re


def authorized(adapter, body, view=None):
    """Use Hermes' profile-bound interactive gate; absence/errors deny access."""
    try:
        metadata = json.loads((view or body.get('view') or {}).get('private_metadata') or '{}')
        channel = body.get('channel_id') or (body.get('channel') or {}).get('id') or metadata.get('channel_id', '')
        user = body.get('user_id') or (body.get('user') or {}).get('id', '')
        team = body.get('team_id') or (body.get('team') or {}).get('id', '')
        return bool(user) and adapter._is_interactive_user_authorized(
            user, channel_id=channel, team_id=team) is True
    except Exception:
        return False


def register(ctx):
    ctx.register_platform_handler('slack', wire_slack)


def wire_slack(app, adapter):
    from .controller import BoardController
    board = BoardController(adapter)

    async def slash(ack, command):
        await ack()
        if authorized(adapter, command):
            with board.request(command):
                await board._handle_board_slash_background(command)

    async def action(ack, body, action):
        if not authorized(adapter, body):
            await ack()
            return
        with board.request(body):
            await board._handle_board_action(ack, body, action)

    def view_handler(method):
        async def submission(ack, body, view):
            if not authorized(adapter, body, view):
                await ack()
                return
            with board.request(body):
                await method(ack, body, view)
        return submission

    app.command('/board')(slash)
    app.action(re.compile(r'^hermes_board_[a-z_]+$'))(action)
    for callback, method in {
        'create': board._handle_board_create_view,
        'detail': board._handle_board_detail_view,
        'move': board._handle_board_move_view,
        'request_changes': board._handle_board_request_changes_view,
    }.items():
        app.view('hermes_board_task_' + callback)(view_handler(method))
