"""Task draft UI regression with isolated localStorage and mocked API responses."""
import asyncio,json
from playwright.async_api import async_playwright, expect
from rpa.chrome_connection import find_chrome

async def main():
    calls={'tasks':0,'analysis':0}
    analysis={'position_id':777,'title':'草稿测试工程师','jd':{'title':'草稿测试工程师','summary':'Fixture','responsibilities':[],'requirements':[]},'keywords':{'primary_keywords':['Python'],'skill_keywords':[]},'filters':{},'scorecard':{}}
    async def mock(route):
        path=route.request.url.split('/api/',1)[1]
        if path=='boss-accounts':
            data=[{'id':901,'name':'模拟账号 A','is_logged_in':True},{'id':902,'name':'模拟账号 B','is_logged_in':True}]
        elif path=='positions/analyze':
            calls['analysis']+=1
            await asyncio.sleep(.8)
            data=analysis
        elif path=='tasks' and route.request.method=='POST':
            calls['tasks']+=1
            data={'task_id':999}
        elif path=='settings':
            data={'api_key_masked':'','has_api_key':False,'base_url':'','model':'','current_provider':'custom','boss_logged_in':False}
        elif path=='dashboard/stats':
            data={'total_positions':0,'total_tasks':0,'active_tasks':0,'total_candidates':0,'greeted':0,'resume_received':0,'qualified':0,'contact_obtained':0}
        else: data=[]
        await route.fulfill(status=200,content_type='application/json',body=json.dumps(data,ensure_ascii=False))
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(executable_path=find_chrome(),headless=True)
        page=await browser.new_page()
        await page.route('**/api/**',mock)
        errors=[]
        page.on('pageerror',lambda error:errors.append(str(error)))
        await page.goto('http://127.0.0.1:8000/tasks/new',wait_until='networkidle')
        title=page.get_by_placeholder('例如：Quant Trader、量化交易员、Java 后端开发')
        description=page.get_by_placeholder('例如：偏高频方向，base 上海，3 年以上经验，偏自营或做市背景')
        await title.fill('草稿测试工程师')
        await description.fill('岗位内容不会丢失')
        await page.locator('#boss-account').select_option('902')
        await page.get_by_role('link',name='系统设置',exact=False).click()
        await page.get_by_role('link',name='新建任务',exact=False).click()
        assert await title.input_value()=='草稿测试工程师'
        assert await description.input_value()=='岗位内容不会丢失'
        await expect(page.locator('#boss-account')).to_have_value('902')
        await page.reload(wait_until='networkidle')
        assert await title.input_value()=='草稿测试工程师'
        # Complete analysis while the form is unmounted, then restore its result.
        await page.get_by_role('button',name='开始 AI 分析',exact=True).click()
        await page.get_by_role('link',name='系统设置',exact=False).click()
        await asyncio.sleep(1.1)
        await page.get_by_role('link',name='新建任务',exact=False).click()
        await page.get_by_role('heading',name='AI 生成的 JD',exact=True).wait_for()
        await page.get_by_placeholder('添加关键词').fill('RAG')
        await page.get_by_placeholder('添加关键词').press('Enter')
        await page.get_by_role('button',name='进入参数配置',exact=True).click()
        numbers=page.locator('input[type=number]')
        await numbers.nth(0).fill('35')
        await numbers.nth(1).fill('82')
        await page.locator('input[type=time]').nth(0).fill('10:30')
        await page.locator('input[type=time]').nth(1).fill('17:30')
        await page.reload(wait_until='networkidle')
        await page.get_by_role('heading',name='运行参数配置',exact=True).wait_for()
        assert await numbers.nth(0).input_value()=='35'
        assert await numbers.nth(1).input_value()=='82'
        assert await page.locator('input[type=time]').nth(0).input_value()=='10:30'
        await expect(page.locator('#boss-account')).to_have_value('902')
        await page.get_by_role('button',name='返回关键词',exact=True).click()
        await page.get_by_text('RAG',exact=True).wait_for()
        await page.get_by_role('button',name='上一步',exact=True).click()
        await description.fill('新岗位要求，旧分析应失效')
        await page.reload(wait_until='networkidle')
        assert await description.input_value()=='新岗位要求，旧分析应失效'
        assert await page.get_by_role('heading',name='AI 生成的 JD',exact=True).count()==0
        page.once('dialog',lambda dialog:dialog.accept())
        await page.get_by_role('button',name='清空草稿',exact=True).click()
        await page.reload(wait_until='networkidle')
        assert await title.input_value()==''
        assert await description.input_value()==''
        assert calls['tasks']==0,calls
        assert calls['analysis']==1,calls
        assert not errors,errors
        print({'route_restore':True,'refresh_restore':True,'analysis_after_navigation':True,'parameters_restore':True,'clear_draft':True,'real_model_calls':0,'real_tasks_started':0,'page_errors':0})
        await browser.close()

asyncio.run(main())

