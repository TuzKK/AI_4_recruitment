"""Local Chrome extension management. No cookie extraction required."""
import json
import secrets
from pathlib import Path

import click

from ..browser_bridge import BridgeState, make_server
from ..browser_session import bridge_file, browser_connection, select_page
from ..client import BossClient
from ..exceptions import BossApiError
from ._common import handle_errors


@click.group()
def browser():
    """连接现有 Chrome 的本地扩展。"""


@browser.command()
@click.option('--port', default=17891, type=click.IntRange(1024, 65535))
@click.option('--allow-writes', is_flag=True, help='显式允许消息发送；默认仅允许查询')
@click.option('--reuse-token', is_flag=True, help='本机服务重启时保留原配对令牌')
def serve(port, allow_writes, reuse_token):
    """前台运行本机服务，保持此进程运行。"""
    from ..browser_session import load_bridge
    previous = load_bridge() if reuse_token else None
    state = BridgeState(previous['token'] if previous else secrets.token_urlsafe(32), allow_writes=allow_writes)
    try:
        server = make_server(state, port)
    except OSError as exc:
        raise click.ClickException(f'端口不可用：{port}；请检查已有服务或另选端口') from exc
    path = bridge_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'port': port, 'token': state.token}), encoding='utf-8')
    path.chmod(0o600)
    click.echo(f'本机服务：http://127.0.0.1:{port}')
    source_extension = Path(__file__).resolve().parents[2] / 'chrome-extension'
    extension = source_extension if source_extension.exists() else Path(__file__).resolve().parents[1] / 'browser_extension'
    click.echo(f'扩展目录：{extension}')
    click.echo(f'配对令牌（仅在本机扩展中使用）：{state.token}')
    click.echo('写操作：' + ('已启用' if allow_writes else '禁用（只读）'))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        if path.exists() and json.loads(path.read_text(encoding='utf-8')).get('token') == state.token:
            path.unlink()


def describe(probe=False):
    connection = browser_connection()
    result = connection.rpc('/status')
    result.update(transport='browser', authenticated=False, api_readable=None, pages=[])
    if result['connected']:
        result['pages'] = connection.call('discover')['pages']
        result['authenticated'] = any(p['state'] == 'logged_in' for p in result['pages'])
        if probe:
            context = click.get_current_context()
            selected = select_page(result, result['pages'], context.find_root().obj.get('browser_target'))
            connection.target = selected['target']
            connection.account_key = selected.get('account_key', '')
            try:
                with BossClient(connection) as client:
                    data = client.get_boss_chatted_jobs()
                result.update(api_readable=True, api_result_type=type(data).__name__)
            except BossApiError as exc:
                result.update(api_readable=False, api_error=str(exc))
    return result


@browser.command()
@click.option('--probe', is_flag=True, help='同时尝试招聘职位查询，不输出候选人隐私')
def status(probe):
    """分别显示扩展连接、页面登录、接口可读状态。"""
    handle_errors(lambda: click.echo(json.dumps(describe(probe), ensure_ascii=False, indent=2)))


@browser.command()
def tabs():
    """列出 BOSS 页面与 target 标识。"""
    handle_errors(lambda: click.echo(json.dumps(describe()['pages'], ensure_ascii=False, indent=2)))


@browser.command('open-login')
def open_login():
    """复用已有 BOSS 页面；没有时才打开登录页面。"""
    handle_errors(lambda: click.echo(json.dumps(browser_connection().call('open_login'), ensure_ascii=False)))


@browser.command()
def cards():
    """读取当前推荐页面卡片摘要，不打开简历详情。"""
    from ..browser_session import resolve_browser_session
    def action():
        session = resolve_browser_session()
        if not session:
            raise BossApiError('请先连接扩展并使用 --transport browser')
        session.navigate('recommend')
        click.echo(json.dumps({'ok': True, 'schema_version': '1', 'data': session.call('cards')}, ensure_ascii=False))
    handle_errors(action)


@browser.command()
@click.argument('page', type=click.Choice(['recommend', 'chat']))
def navigate(page):
    """由程序切换至推荐或沟通页面。"""
    from ..browser_session import resolve_browser_session
    def action():
        session = resolve_browser_session()
        if not session:
            raise BossApiError('需要浏览器连接')
        click.echo(json.dumps(session.navigate(page), ensure_ascii=False))
    handle_errors(action)


@browser.command('profile-snapshot')
def profile_snapshot():
    """读取当前可见简历正文和页面已发出的详情请求；包含个人资料。"""
    from ..browser_session import resolve_browser_session
    def action():
        session = resolve_browser_session()
        if not session:
            raise BossApiError('需要浏览器连接')
        click.echo(json.dumps(session.call('profile_snapshot'), ensure_ascii=False))
    handle_errors(action)


@browser.command('open-profile')
@click.argument('geek_id')
def open_profile(geek_id):
    """自动打开指定推荐卡片的简历详情，不打招呼。"""
    from ..browser_session import resolve_browser_session
    def action():
        session = resolve_browser_session()
        if not session:
            raise BossApiError('需要浏览器连接')
        session.navigate('recommend')
        click.echo(json.dumps(session.call('open_profile', {'geek_id': geek_id}), ensure_ascii=False))
    handle_errors(action)
