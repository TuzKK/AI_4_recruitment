"""
BOSS 职位提取脚本 - 使用页面内执行JS的安全方式
在用户手动登录并导航到职位管理页面后，通过执行页面内的JS来提取职位信息
"""
import json
import sys
import time
from pathlib import Path
import asyncio

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def extract_jobs_safe():
    """安全地从页面提取职位信息，通过在页面内执行JavaScript的方式"""

    print("请确保您已在BOSS直聘的职位管理页面。")
    print("页面URL应包含: /web/geek/job 或 /web/geek/jobs")
    print("")

    storage_dir = project_root / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = None

        # 使用相同的浏览器实例（确保登录状态）
        for channel in ["chrome", "msedge"]:
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(storage_dir / f"user_data_{channel}"),
                    headless=False,  # 非无头模式，更像真人操作
                    channel=channel,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                    ],
                )
                print(f"使用 {channel} 浏览器成功")
                break
            except Exception as e:
                print(f"{channel} 启动失败：{e}")
                continue

        if not browser:
            print("ERROR: 无法启动浏览器")
            print("RESULT:" + json.dumps({"status": "error", "error": "无法启动浏览器"}))
            return

        # 等待页面加载
        time.sleep(3)

        # 尝试找到职位管理页面
        page = None
        for tab in browser.pages:
            try:
                url = tab.url
                if "zhipin.com" in url and ("/web/geek/job" in url or "position" in url):
                    page = tab
                    print(f"找到职位管理页面: {url}")
                    break
            except Exception:
                continue

        if not page:
            print("未找到职位管理页面，请确保已导航到正确的页面")
            # 创建新页面并尝试导航
            page = browser.new_page()
            page.goto("https://www.zhipin.com/web/geek/jobs", timeout=10000)
            print("已导航到职位管理页面")

        # 等待页面充分加载
        time.sleep(5)

        # 在页面内执行JavaScript来提取职位信息
        # 这种方式更安全，因为是在页面上下文中执行
        print("正在通过页面内JS提取职位信息...")

        try:
            # 定义一个在页面上下文中的提取函数
            js_code = r"""
            (function() {
                // 定义要查找的职位关键词
                const jobKeywords = [
                    '工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                    '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                    '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划',
                    'Java', 'Python', 'C++', '前端', '后端', '算法', 'AI', '数据'
                ];

                // 用于存储职位信息的数组
                const jobs = [];

                // 查找页面中可能包含职位信息的元素
                const potentialElements = [
                    ...document.querySelectorAll('.job-card, .job-item, .position-card, .position-item'),
                    ...document.querySelectorAll('[class*="job"], [class*="position"]'),
                    ...document.querySelectorAll('li, div, article')
                ];

                // 遍历潜在的职位元素
                for (let i = 0; i < potentialElements.length && jobs.length < 20; i++) {
                    const element = potentialElements[i];

                    // 获取元素的文本内容
                    const text = element.textContent || element.innerText;

                    // 检查文本是否包含职位关键词
                    const containsJobKeyword = jobKeywords.some(keyword =>
                        text.includes(keyword) && text.length > 2 && text.length < 100
                    );

                    if (containsJobKeyword) {
                        // 尝试从元素中提取具体的职位信息
                        const titleSelectors = [
                            '.job-name', '.position-name', '.job-title', 'h3', 'h4', 'h5', 'a', '.name', '.title'
                        ];

                        let jobName = '';
                        for (const selector of titleSelectors) {
                            const titleEl = element.querySelector(selector);
                            if (titleEl) {
                                const title = titleEl.textContent.trim();
                                if (title.length > 2 && title.length < 50) {
                                    jobName = title;
                                    break;
                                }
                            }
                        }

                        // 如果没有找到标题，使用文本的前一部分
                        if (!jobName) {
                            jobName = text.substring(0, 50).trim();
                        }

                        // 提取其他信息
                        const department = element.querySelector('.department, .dept, .company')?.textContent?.trim() || '未知部门';
                        const salary = element.querySelector('.salary, .pay')?.textContent?.trim() || '面议';
                        const city = element.querySelector('.city, .location')?.textContent?.trim() || '未知城市';
                        const experience = element.querySelector('.experience, .exp')?.textContent?.trim() || '经验不限';
                        const education = element.querySelector('.education, .edu')?.textContent?.trim() || '学历不限';

                        // 获取可能的职位ID
                        const jobId = element.dataset.jobid ||
                                     element.dataset.positionid ||
                                     element.querySelector('a')?.href?.match(/\/job\/([^\/?#]+)/)?.[1] ||
                                     `auto_${i}_${Date.now()}`;

                        const job = {
                            job_id: jobId,
                            job_name: jobName,
                            department: department,
                            city: city,
                            salary: salary,
                            experience: experience,
                            education: education,
                            status: '招聘中'
                        };

                        // 验证职位信息的有效性
                        if (job.job_name && job.job_name.length >= 2) {
                            jobs.push(job);
                        }
                    }
                }

                // 如果常规方法没找到，尝试从所有链接中提取
                if (jobs.length === 0) {
                    const links = document.querySelectorAll('a');
                    for (let i = 0; i < links.length && jobs.length < 10; i++) {
                        const link = links[i];
                        const href = link.href;
                        const text = link.textContent.trim();

                        // 检查是否是职位相关的链接
                        if ((href.includes('/job_detail/') || href.includes('/job/')) &&
                            text.length > 2) {

                            const isJobRelated = jobKeywords.some(keyword => text.includes(keyword));

                            if (isJobRelated) {
                                const job = {
                                    job_id: `link_${i}_${Date.now()}`,
                                    job_name: text,
                                    department: '未知部门',
                                    city: '未知城市',
                                    salary: '面议',
                                    experience: '经验不限',
                                    education: '学历不限',
                                    status: '招聘中'
                                };

                                jobs.push(job);
                            }
                        }
                    }
                }

                return {
                    status: "success",
                    jobs: jobs,
                    count: jobs.length,
                    timestamp: new Date().toISOString(),
                    extraction_method: "safe_js_execution"
                };
            })();
            """

            # 在页面上下文中执行JavaScript
            result = page.evaluate(js_code)

            print("RESULT:" + json.dumps(result, ensure_ascii=False))

        except Exception as e:
            import traceback
            error_result = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()[:500]
            }
            print("RESULT:" + json.dumps(error_result, ensure_ascii=False))

    print("\n浏览器保持开启，您可以在其中继续操作...")

if __name__ == "__main__":
    extract_jobs_safe()
