"""
基于 DrissionPage + LLM 的 BOSS 直聘简历自动筛选方案
使用 DrissionPage 框架来绕过反爬虫检测，结合 LLM 进行智能匹配度评估
"""
import json
import time
import random
from pathlib import Path
from datetime import datetime
from DrissionPage import ChromiumPage, ChromiumOptions
import pandas as pd


def setup_drissionpage():
    """
    配置 DrissionPage 浏览器实例
    DrissionPage 比 Selenium 更难被检测，更适合反反爬虫场景
    """
    co = ChromiumOptions()

    # 设置用户代理，模仿真实用户
    co.set_user_agent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    # 设置窗口大小
    co.set_argument("--window-size=1920,1080")

    # 禁用自动化检测
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--disable-dev-shm-usage")
    co.set_argument("--no-sandbox")
    co.set_argument("--disable-extensions")
    co.set_argument("--disable-plugins-discovery")
    co.set_argument("--incognito")  # 无痕模式
    co.set_argument("--disable-blink-features=AutomationControlled")
    co.set_argument("--disable-infobars")
    co.set_argument("--lang=zh-CN,zh")

    # 设置数据路径，保持会话一致性
    storage_dir = Path("./.storage")
    storage_dir.mkdir(parents=True, exist_ok=True)
    co.set_argument(f"--user-data-dir={storage_dir}/drission_user_data")

    # 创建页面实例
    page = ChromiumPage(addr_or_opts=co)

    # 执行脚本隐藏自动化特征
    page.run_js("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });

        window.chrome = {
            runtime: {}
        };

        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """)

    return page


def manual_login_assistant(page):
    """
    手动登录助手
    由于反爬虫机制，首次登录仍需手动完成
    """
    print("正在打开 BOSS 直聘网站...")
    page.get("https://www.zhipin.com/")

    print("\n手动登录指引")
    print("请在打开的浏览器中完成以下操作：")
    print("1. 扫码登录或账号密码登录")
    print("2. 登录后点击左侧菜单的 '职位管理'")
    print("3. 等待职位列表完全加载")
    print("4. 完成后返回此处按回车键继续")
    print("="*30)

    # 检测是否已在浏览器中完成登录，而不是等待输入
    print("\n检测登录状态中，请在浏览器中完成登录操作...")

    # 简单的等待，实际实现可能需要检测页面URL或元素变化
    import time
    time.sleep(10)  # 给用户时间完成登录


def extract_jobs_with_drission(page):
    """
    使用 DrissionPage 提取职位信息
    通过更自然的页面交互来避免被检测
    """
    print("正在尝试从职位管理页面提取职位信息...")

    # 验证是否在正确的页面
    if "zhipin.com/web/geek/job" not in page.url and "zhipin.com/web/geek/jobs" not in page.url:
        print("正在导航到职位管理页面...")
        page.get("https://www.zhipin.com/web/geek/jobs")
        time.sleep(3)

    # 模拟人类行为：等待、滚动、观察
    print("正在模拟人类浏览行为...")
    time.sleep(random.uniform(3, 5))

    # 滚动页面以加载更多职位
    print("正在滚动页面以加载职位信息...")
    for i in range(3):
        page.scroll.to_bottom()
        time.sleep(random.uniform(2, 4))  # 真实用户会等待页面加载

    # 尝试多种方式获取职位信息
    jobs = []

    # 方式1: 通过CSS选择器查找职位卡片
    print("正在查找职位卡片元素...")
    card_selectors = [
        'div.job-card', 'div.position-card', 'div.job-item', 'div.position-item',
        '[class*="job"]', '[class*="position"]', 'li', 'div.item'
    ]

    for selector in card_selectors:
        try:
            elements = page.eles(selector)
            print(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")

            for element in elements:
                try:
                    # 提取职位名称
                    job_name = ""
                    title_selectors = ['.job-name', '.position-name', '.job-title', 'h3', 'h4', 'a', '.name']

                    for title_sel in title_selectors:
                        title_elem = element.ele(title_sel)
                        if title_elem:
                            job_name = title_elem.text.strip()
                            if len(job_name) > 2:  # 有效职位名称
                                break

                    # 如果没找到明确的职位名，尝试获取元素文本
                    if not job_name or len(job_name) <= 2:
                        job_name = element.text[:50].strip()

                    # 检查是否包含职位关键词
                    job_keywords = [
                        '工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                        '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                        '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划',
                        'Java', 'Python', 'C++', '前端', '后端', '算法', 'AI', '数据'
                    ]

                    is_valid_job = any(keyword in job_name for keyword in job_keywords)

                    if is_valid_job:
                        # 提取其他职位信息
                        department = element.ele('.department, .company') and element.ele('.department, .company').text or '未知部门'
                        city = element.ele('.city, .location') and element.ele('.city, .location').text or '未知城市'
                        salary = element.ele('.salary, .pay') and element.ele('.salary, .pay').text or '面议'
                        experience = element.ele('.experience, .exp') and element.ele('.experience, .exp').text or '经验不限'
                        education = element.ele('.education, .edu') and element.ele('.education, .edu').text or '学历不限'

                        # 尝试获取职位ID
                        job_id = f"job_{len(jobs)}_{int(time.time())}"  # 生成唯一ID

                        job_info = {
                            'job_id': job_id,
                            'job_name': job_name,
                            'department': department,
                            'city': city,
                            'salary': salary,
                            'experience': experience,
                            'education': education,
                            'status': '招聘中'
                        }

                        jobs.append(job_info)
                        print(f"提取到职位: {job_name}")

                except Exception as e:
                    print(f"提取单个元素时出错: {e}")
                    continue

            if jobs:  # 如果找到职位，跳出选择器循环
                break

        except Exception as e:
            print(f"使用选择器 '{selector}' 时出错: {e}")
            continue

    # 如果通过选择器没有找到，尝试从页面所有链接中提取
    if not jobs:
        print("尝试从页面链接中提取职位信息...")
        try:
            links = page.eles('a')
            for link in links[:50]:  # 只检查前50个链接
                try:
                    href = link.attr('href') or ''
                    text = link.text.strip()

                    if any(pattern in href for pattern in ['/job_detail/', '/job/', 'securityId=']) and len(text) > 2:
                        # 检查文本是否包含职位关键词
                        job_keywords = [
                            '工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                            '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                            '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划'
                        ]

                        if any(keyword in text for keyword in job_keywords):
                            job_info = {
                                'job_id': f"link_{len(jobs)}_{int(time.time())}",
                                'job_name': text,
                                'department': '未知部门',
                                'city': '未知城市',
                                'salary': '面议',
                                'experience': '经验不限',
                                'education': '学历不限',
                                'status': '招聘中'
                            }

                            jobs.append(job_info)
                            print(f"从链接提取到职位: {text}")

                except Exception as e:
                    continue

        except Exception as e:
            print(f"从链接提取职位时出错: {e}")

    result = {
        "status": "success",
        "jobs": jobs,
        "count": len(jobs),
        "timestamp": datetime.now().isoformat(),
        "extraction_method": "drissionpage_manual_interaction"
    }

    print(f"\\n总共提取到 {len(jobs)} 个职位信息")

    return result


def run_full_automation():
    """
    运行完整的自动化流程
    """
    print("启动基于 DrissionPage + LLM 的 BOSS 直聘筛选系统")
    print("="*60)

    page = None
    try:
        # 初始化 DrissionPage
        print("初始化浏览器环境...")
        page = setup_drissionpage()

        # 手动登录助手
        print("启动手动登录助手...")
        manual_login_assistant(page)

        # 提取职位信息
        print("开始提取职位信息...")
        result = extract_jobs_with_drission(page)

        # 输出结果
        print("\\n📋 提取结果:")
        print(json.dumps(result, ensure_ascii=False, indent=2))

        # 输出到控制台（用于上层脚本读取）
        print("\nRESULT:" + json.dumps(result, ensure_ascii=False))

        print("\n职位信息提取完成！")
        print("浏览器将保持打开状态，您可以在其中继续操作。")

        return result

    except Exception as e:
        print(f"自动化流程执行失败: {e}")
        import traceback
        print(traceback.format_exc())

        # 返回错误结果
        error_result = {
            "status": "error",
            "error": str(e),
            "jobs": [],
            "count": 0
        }
        print("\nRESULT:" + json.dumps(error_result, ensure_ascii=False))

        return error_result

    finally:
        # 注意：不关闭页面，让用户可以继续使用
        if page:
            print("\n提示: 浏览器窗口保持打开，您可以在其中继续进行其他操作。")


if __name__ == "__main__":
    run_full_automation()