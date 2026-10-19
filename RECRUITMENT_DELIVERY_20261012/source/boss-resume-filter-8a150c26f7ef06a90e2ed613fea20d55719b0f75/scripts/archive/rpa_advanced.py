"""
真正的RPA（机器人流程自动化）解决方案
使用更高级的模拟技术来实现BOSS直聘职位信息自动获取
"""
import time
import random
import json
from pathlib import Path
import asyncio
from datetime import datetime

# 为RPA方案引入selenium，因为它对反检测有更好的支持
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.action_chains import ActionChains
    import undetected_chromedriver as uc
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("警告: 未安装selenium或undetected_chromedriver，无法使用高级RPA方案")


def run_rpa_solution():
    """
    运行真正的RPA解决方案
    这个方案将使用高级的浏览器伪装技术来避免被检测
    """
    if not SELENIUM_AVAILABLE:
        print("错误: 缺少必要的依赖包")
        print("请运行: pip install selenium undetected-chromedriver")

        # 提供手动解决方案
        print("\n当前可选的解决方案:")
        print("1. 安装所需的依赖包")
        print("2. 使用浏览器控制台手动提取（推荐）")
        print("3. 手动复制职位信息到文档")

        # 提供浏览器控制台代码
        print("\n浏览器控制台提取代码:")
        print("""
// 在BOSS直聘职位管理页面的控制台中执行
(function() {
    // 模拟人工滚动
    window.scrollTo(0, document.body.scrollHeight);
    setTimeout(() => {
        // 提取职位信息
        const jobs = [];
        const cards = document.querySelectorAll('.job-card, .position-card, .job-item, [class*="job"]');

        cards.forEach(card => {
            const title = card.querySelector('.job-name, .position-name, h3, a')?.textContent?.trim();
            if (title && title.length > 2) {
                const job = {
                    job_id: card.dataset.jobid || card.querySelector('a')?.href?.split('/').pop()?.split('?')[0] || 'unknown',
                    job_name: title,
                    department: card.querySelector('.department, .company')?.textContent?.trim() || '未知部门',
                    city: card.querySelector('.city')?.textContent?.trim() || '未知城市',
                    salary: card.querySelector('.salary')?.textContent?.trim() || '面议',
                    experience: card.querySelector('.experience')?.textContent?.trim() || '经验不限',
                    education: card.querySelector('.education')?.textContent?.trim() || '学历不限',
                    status: '招聘中'
                };
                jobs.push(job);
            }
        });

        const result = { status: 'success', jobs, count: jobs.length };
        console.log(JSON.stringify(result, null, 2));
        return result;
    }, 2000);
})();
        """)
        return False

    print("正在启动高级RPA自动化解决方案...")

    # 配置Chrome选项以避免检测
    options = uc.ChromeOptions()
    options.add_argument("--no-first-run")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-web-security")
    options.add_argument("--disable-features=VizDisplayCompositor")

    # 设置用户代理伪装
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

    driver = None
    try:
        # 使用undetected-chromedriver来规避检测
        driver = uc.Chrome(options=options)

        print("正在打开BOSS直聘网站...")
        driver.get("https://www.zhipin.com/")

        print("请在30秒内手动完成登录:")
        print("- 扫描二维码登录")
        print("- 或输入账号密码登录")
        print("- 登录后不要进行其他操作")

        # 等待用户登录（30秒）
        time.sleep(30)

        # 检查是否登录成功（简单检测）
        current_url = driver.current_url
        if "zhipin.com" in current_url and "login" not in current_url:
            print("检测到可能已登录，正在导航到职位管理页面...")
            driver.get("https://www.zhipin.com/web/geek/jobs")

            # 等待页面加载
            time.sleep(5)

            # 模拟人类滚动行为
            print("正在模拟人类滚动行为...")
            for i in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))

            # 随机等待
            time.sleep(random.uniform(3, 6))

            # 使用JavaScript提取职位信息
            print("正在提取职位信息...")
            js_code = """
            (function() {
                const jobs = [];

                // 查找职位卡片
                const cards = document.querySelectorAll('.job-card, .position-card, .job-item, [class*="job"]') || [];

                cards.forEach((card, index) => {
                    try {
                        // 提取职位名称
                        let jobName = '';
                        const titleSelectors = ['.job-name', '.position-name', 'h3', 'h4', 'a', '.name'];

                        for(const selector of titleSelectors) {
                            const titleEl = card.querySelector(selector);
                            if(titleEl) {
                                jobName = titleEl.textContent.trim();
                                if(jobName.length > 2) break;
                            }
                        }

                        // 如果没找到标题，从卡片文本中提取
                        if(!jobName || jobName.length <= 2) {
                            jobName = card.textContent.substring(0, 50).trim();
                        }

                        // 验证是否为有效职位名称
                        const validKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生',
                                             '顾问', '设计师', '开发', '技术', '产品', '运营', '市场',
                                             '销售', '财务', '人事', '行政', '客服', '测试', '运维',
                                             '架构师', '分析师', '策划', 'Java', 'Python', 'C++',
                                             '前端', '后端', '算法', 'AI', '数据'];

                        const isValid = validKeywords.some(keyword => jobName.includes(keyword));

                        if(isValid && jobName.length > 2) {
                            const job = {
                                job_id: card.dataset.jobid ||
                                       card.querySelector('a')?.href?.match(/\\/([^\\/?#]+)/)?.[1] ||
                                       `auto_${index}_${Date.now()}`,
                                job_name: jobName,
                                department: card.querySelector('.department, .company')?.textContent?.trim() || '未知部门',
                                city: card.querySelector('.city')?.textContent?.trim() || '未知城市',
                                salary: card.querySelector('.salary')?.textContent?.trim() || '面议',
                                experience: card.querySelector('.experience')?.textContent?.trim() || '经验不限',
                                education: card.querySelector('.education')?.textContent?.trim() || '学历不限',
                                status: '招聘中'
                            };

                            jobs.push(job);
                        }
                    } catch(e) {
                        console.warn('提取职位信息时出错:', e);
                    }
                });

                return {
                    status: 'success',
                    jobs: jobs,
                    count: jobs.length,
                    extraction_method: 'rpa_selenium_js'
                };
            })();
            """

            try:
                result = driver.execute_script(js_code)
                print("RESULT:" + json.dumps(result, ensure_ascii=False, indent=2))
                return True
            except Exception as e:
                print(f"执行JavaScript时出错: {e}")

        else:
            print("未检测到登录状态，请确保已成功登录")

    except Exception as e:
        print(f"RPA解决方案执行出错: {e}")
        import traceback
        print(traceback.format_exc())

    finally:
        if driver:
            print("浏览器将保持打开状态，您可以在其中继续操作...")
            # 不关闭driver，让用户可以继续使用

    return False


if __name__ == "__main__":
    print("BOSS直聘职位信息自动提取 - 高级RPA方案")
    print("="*50)

    success = run_rpa_solution()

    if not success:
        print("\n如果RPA方案仍无法工作，建议使用手动提取方法:")
        print("1. 在职位管理页面按F12打开开发者工具")
        print("2. 切换到Console标签")
        print("3. 粘贴并执行之前提供的JavaScript代码")
        print("4. 将结果保存为JSON文件")
        print("5. 在系统中使用'上传需求文档'功能")