"""Attach task execution to the selected account; detach on completion."""
from rpa.chrome_connection import ChromeConnection, inspect_page


class BrowserEngine:
    def __init__(self, cdp_url: str, target_id: str):
        self.connection = ChromeConnection(cdp_url, target_id)

    async def launch(self):
        page = await self.connection.open()
        if (await inspect_page(page))['state'] != 'logged_in':
            await self.close()
            raise RuntimeError('所选 BOSS 招聘页面未登录或需要验证，请到设置中重新检测接入')
        return page

    async def close(self):
        await self.connection.close()

    @property
    def context(self):
        return self.connection.page.context if self.connection.page else None

    async def new_page(self):
        if not self.context:
            raise RuntimeError('Browser is not connected')
        return await self.context.new_page()
