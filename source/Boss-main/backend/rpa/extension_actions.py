"""Browser actions for an already running Chrome connected through the extension."""
from rpa.human_simulator import random_delay


def set_notify_callback(cb):
    pass


async def ensure_logged_in(page):
    state = await page.call('inspect')
    if state.get('state') != 'logged_in':
        raise RuntimeError('请在已连接的 Chrome 中登录 BOSS 招聘者账号')
    if '/web/chat/recommend' not in state.get('url', ''):
        raise RuntimeError('请在已连接的原标签页打开牛人推荐，然后重试任务')


async def get_candidate_cards(page, force_refresh=False):
    return await page.call('cards')


async def click_greet_button(page, geek_id, greet_btn_index=None):
    return await page.call('greet', {'geek_id': geek_id})


async def dismiss_greet_dialog(page):
    return False


async def scroll_to_load_more(page):
    await page.call('scroll')
    await random_delay(1.5, 3)
