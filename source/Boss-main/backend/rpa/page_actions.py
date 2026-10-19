"""BOSS recruiter browser actions. Chat and attachment collection are not implemented."""
from __future__ import annotations
import asyncio
import json
from rpa.chrome_connection import RECOMMEND_URL, inspect_page, is_boss_url
from rpa.human_simulator import random_delay

_notify_callback = None


def set_notify_callback(cb):
    global _notify_callback
    _notify_callback = cb


async def recommend_frame(page):
    for frame in page.frames:
        if frame == page.main_frame or is_boss_url(frame.url):
            if await frame.locator('li.card-item').count():
                return frame
    return None


async def ensure_logged_in(page):
    if (await inspect_page(page))['state'] != 'logged_in':
        raise RuntimeError('BOSS 账号未登录或需要验证，请在 Chrome 中处理后重试')
    if '/web/chat/recommend' not in page.url:
        await page.goto(RECOMMEND_URL, wait_until='domcontentloaded', timeout=30000)
    for _ in range(15):
        if await recommend_frame(page):
            return
        await asyncio.sleep(1)
    raise RuntimeError('未找到牛人推荐卡片，请检查当前账号、岗位及网页是否已加载')


async def navigate_to_recommend(page):
    await ensure_logged_in(page)


async def get_candidate_cards(page, force_refresh=False):
    frame = await recommend_frame(page)
    if not frame:
        return []
    return await frame.locator('li.card-item').evaluate_all('''cards => cards.map((card, i) => {
        const t = sel => card.querySelector(sel)?.textContent?.trim() || '';
        return {
            card_index: i, greet_btn_index: i,
            geek_id: card.querySelector('.card-inner')?.getAttribute('data-geekid') || '',
            name: t('.name'), active: t('.active-text'), salary: t('.salary-wrap span'),
            base_info: t('.base-info'), expect: t('.expect-wrap .content'),
            expect_city: t('.expect-wrap .content'), advantages: t('.geek-desc .content'),
            work_experience: [...card.querySelectorAll('.work-experience, .work-item')].map(x => x.textContent.trim()),
            tags: [...card.querySelectorAll('.tag-item')].map(x => x.textContent.trim()),
            _search_text: card.innerText
        };
    }).filter(c => c.name && c.geek_id)''')


async def click_greet_button(page, geek_id, greet_btn_index=None):
    if not geek_id:
        return False
    if (await inspect_page(page))['state'] != 'logged_in':
        raise RuntimeError('登录状态已变化，已停止打招呼')
    frame = await recommend_frame(page)
    if not frame:
        return False
    # JSON quoting prevents an ID from changing the selector; never use list index.
    inner = frame.locator('.card-inner[data-geekid=' + json.dumps(geek_id) + ']')
    if await inner.count() != 1:
        return False
    card = inner.locator('xpath=ancestor::li[contains(@class,"card-item")]')
    button = card.get_by_role('button', name='打招呼', exact=True)
    if await button.count() != 1 or not await button.is_visible() or not await button.is_enabled():
        return False
    # One click only. A timeout after sending is ambiguous and must not be retried.
    await button.click(timeout=5000)
    for _ in range(10):
        if await card.get_by_text('继续沟通', exact=True).count():
            return True
        await asyncio.sleep(.5)
    raise RuntimeError('已点击打招呼，但无法确认发送结果。任务停止，请人工检查，避免重复发送')


async def dismiss_greet_dialog(page):
    # Do not accept arbitrary confirmation or purchase dialogs.
    return False


async def scroll_to_load_more(page):
    frame = await recommend_frame(page)
    if frame:
        await frame.locator('li.card-item').last.scroll_into_view_if_needed()
    await random_delay(1.5, 3)


async def get_candidate_profile(page):
    cards = await get_candidate_cards(page)
    return cards[0] if cards else {}


async def navigate_to_chat(page):
    await page.goto('https://www.zhipin.com/web/chat', wait_until='domcontentloaded')


async def get_unread_messages(page):
    raise NotImplementedError('浏览器模式尚未实现聊天回复读取')


async def send_chat_message(page, message):
    raise NotImplementedError('浏览器模式尚未实现聊天消息发送')


async def check_for_resume_attachment(page):
    raise NotImplementedError('浏览器模式尚未实现附件读取')
