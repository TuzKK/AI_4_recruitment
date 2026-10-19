"""Read-only local UI smoke check. Never launch a visible browser or login flow."""
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright
from rpa.chrome_connection import find_chrome

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(executable_path=find_chrome(), headless=True)
        page = await browser.new_page(viewport={'width':1440,'height':1050})
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        response=await page.goto('http://127.0.0.1:8000/settings',wait_until='networkidle')
        assert response.status==200
        await page.get_by_role('button',name='首次接入：获取扩展配对信息',exact=True).click()
        await page.get_by_label('扩展文件夹',exact=True).wait_for()
        folder=await page.get_by_label('扩展文件夹',exact=True).input_value()
        assert Path(folder,'manifest.json').is_file()
        token=await page.get_by_label('扩展配对码',exact=True).input_value()
        assert len(token)>20
        await page.get_by_role('button',name='检测已打开的 Chrome',exact=True).click()
        await page.get_by_text('个普通 Chrome 主进程。',exact=False).wait_for(timeout=20000)
        await page.get_by_text('接入现有 Chrome · 保留当前登录',exact=True).scroll_into_view_if_needed()
        await page.screenshot(path='data/logs/existing-chrome-extension-settings.png',full_page=True)
        assert not errors,errors
        print({'settings_status':response.status,'pairing_field_present':True,'extension_folder_exists':True,'page_errors':len(errors)})
        await browser.close()

asyncio.run(main())

