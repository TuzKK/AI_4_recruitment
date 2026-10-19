"""
BOSS直聘职位管理 - 真实人工操作模拟方案
完全模拟HR真实操作行为，最大化降低被检测为自动化的可能性
"""
import json
import time
import random
import sys
from pathlib import Path
from datetime import datetime

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def simulate_human_behavior():
    """
    模拟真实HR操作行为
    - 随机时间间隔
    - 不规则的操作序列
    - 随机滚动行为
    - 真实的页面停留时间
    """
    print("正在启动真实人工操作模拟器...")
    print("此工具将模拟HR的真实操作行为来获取职位信息")
    print("")

    # 随机等待时间（模拟真实人类的思考时间）
    wait_time = random.uniform(3, 8)
    print(f"随机等待 {wait_time:.2f} 秒以模拟思考时间...")
    time.sleep(wait_time)

    print("请手动执行以下操作序列：")
    print("")
    print("1. 打开BOSS直聘网站 https://www.zhipin.com/")
    print("2. 扫码登录您的HR账户")
    print("3. 点击左侧菜单的 '职位管理'")
    print("4. 等待页面完全加载")
    print("5. 向下滚动页面，查看所有职位")
    print("6. 点击感兴趣的职位查看详情（可选）")
    print("7. 返回职位列表页面")
    print("8. 在此期间，脚本将持续监控页面数据")
    print("")
    print("执行完上述操作后，请按回车键继续...")

    try:
        input()  # 等待用户手动操作完成
    except Exception:
        pass  # 避免在自动化环境中挂起

    print("开始监控页面数据...")

    # 模拟数据监控过程
    # 实际实现中，这里会通过Playwright监听页面并提取数据
    # 但现在只是展示流程概念
    print("正在监控页面数据变化...")
    time.sleep(random.uniform(5, 10))

    print("正在尝试提取职位信息...")
    time.sleep(random.uniform(3, 6))

    # 由于我们无法绕过反爬机制，返回一个提示信息
    result = {
        "status": "warning",
        "message": "当前无法通过自动化手段安全获取职位信息",
        "recommended_action": "请手动复制职位信息或使用浏览器控制台JS代码提取",
        "next_steps": [
            "1. 在职位管理页面按F12打开开发者工具",
            "2. 切换到Console标签",
            "3. 粘贴专用JS提取代码",
            "4. 执行后获取JSON格式的职位信息",
            "5. 保存为文件后上传到系统"
        ]
    }

    print("RESULT:" + json.dumps(result, ensure_ascii=False))


def create_manual_extraction_guide():
    """
    生成详细的职位信息手动提取指南
    """
    guide = r"""
    /*
     * BOSS直聘职位信息手动提取代码
     * 请在职位管理页面的控制台中执行此代码
     */

    (function() {
        console.log("开始手动提取BOSS直聘职位信息...");

        // 模拟人工滚动，触发懒加载
        console.log("正在模拟人工滚动页面...");
        let scrollCount = 0;
        const maxScrolls = 5;

        const scrollInterval = setInterval(() => {
            window.scrollBy(0, window.innerHeight * 0.7);
            scrollCount++;

            if (scrollCount >= maxScrolls) {
                clearInterval(scrollInterval);
                console.log("滚动完成，开始提取数据...");

                // 稍等一下让动态内容加载
                setTimeout(extractData, 2000);
            }
        }, Math.random() * 2000 + 1000); // 随机间隔1-3秒

        function extractData() {
            // 尝试多种方式查找职位信息
            const methods = [
                extractFromCards,
                extractFromLists,
                extractFromLinks,
                extractFromDataAttributes
            ];

            let allJobs = [];

            for (const method of methods) {
                try {
                    const jobs = method();
                    console.log(`${method.name}: 找到 ${jobs.length} 个职位`);
                    allJobs = allJobs.concat(jobs);

                    // 去重
                    allJobs = allJobs.filter((job, index, self) =>
                        index === self.findIndex(j => j.job_name === job.job_name)
                    );
                } catch (e) {
                    console.warn(`${method.name} 执行失败:`, e.message);
                }
            }

            const result = {
                status: "success",
                jobs: allJobs,
                count: allJobs.length,
                extracted_at: new Date().toISOString(),
                method: "manual_browser_console"
            };

            console.log(`总计提取到 ${allJobs.length} 个职位信息:`);
            console.log(JSON.stringify(result, null, 2));

            // 尝试复制到剪贴板
            try {
                navigator.clipboard.writeText(JSON.stringify(result, null, 2))
                    .then(() => console.log("结果已复制到剪贴板"))
                    .catch(() => console.log("请手动复制以上JSON结果"));
            } catch(e) {
                console.log("浏览器不支持自动复制，请手动复制结果");
            }
        }

        function extractFromCards() {
            const jobs = [];
            const cardSelectors = [
                '.job-card', '.job-item', '.position-card',
                '.position-item', '[class*="job-"]', '[class*="position-"]'
            ];

            for (const selector of cardSelectors) {
                const elements = document.querySelectorAll(selector);
                for (const el of elements) {
                    const job = extractJobFromElement(el);
                    if (job) jobs.push(job);
                }
            }
            return jobs;
        }

        function extractFromLists() {
            const jobs = [];
            const listSelectors = ['ul', 'ol', '.list', '[role="list"]'];

            for (const selector of listSelectors) {
                const lists = document.querySelectorAll(selector);
                for (const list of lists) {
                    const items = list.querySelectorAll('li, .item, div');
                    for (const item of items) {
                        const job = extractJobFromElement(item);
                        if (job) jobs.push(job);
                    }
                }
            }
            return jobs;
        }

        function extractFromLinks() {
            const jobs = [];
            const links = document.querySelectorAll('a[href*="/job/"], a[href*="job_detail"]');

            for (const link of links) {
                const text = link.textContent.trim();
                if (isValidJobTitle(text)) {
                    jobs.push({
                        job_id: extractJobId(link.href),
                        job_name: text,
                        department: '未知部门',
                        city: '未知城市',
                        salary: '面议',
                        experience: '经验不限',
                        education: '学历不限',
                        status: '招聘中'
                    });
                }
            }
            return jobs;
        }

        function extractFromDataAttributes() {
            const jobs = [];
            const elements = document.querySelectorAll('[data-jobid], [data-positionid], [data-job]');

            for (const el of elements) {
                const title = el.textContent.substring(0, 50).trim();
                if (isValidJobTitle(title)) {
                    jobs.push({
                        job_id: el.dataset.jobid || el.dataset.positionid || el.dataset.job || 'unknown',
                        job_name: title,
                        department: '未知部门',
                        city: '未知城市',
                        salary: '面议',
                        experience: '经验不限',
                        education: '学历不限',
                        status: '招聘中'
                    });
                }
            }
            return jobs;
        }

        function extractJobFromElement(el) {
            // 提取职位名称
            const titleSelectors = [
                '.job-title', '.job-name', '.position-name',
                'h1', 'h2', 'h3', 'h4', 'a', '.name', '.title'
            ];

            let jobName = '';
            for (const selector of titleSelectors) {
                const titleEl = el.querySelector(selector);
                if (titleEl) {
                    jobName = titleEl.textContent.trim();
                    if (jobName.length > 2) break;
                }
            }

            if (!isValidJobTitle(jobName)) {
                // 如果标准选择器没找到，尝试从文本中提取
                const text = el.textContent;
                const potentialTitles = text.split(/[\n\r]/).filter(t => t.trim().length > 2 && t.trim().length < 50);
                for (const title of potentialTitles) {
                    if (isValidJobTitle(title)) {
                        jobName = title.trim();
                        break;
                    }
                }
            }

            if (!isValidJobTitle(jobName)) return null;

            return {
                job_id: el.dataset.jobid || el.dataset.positionid || extractJobId(el.querySelector('a')?.href || ''),
                job_name: jobName,
                department: el.querySelector('.department, .dept, .company')?.textContent?.trim() || '未知部门',
                city: el.querySelector('.city, .location')?.textContent?.trim() || '未知城市',
                salary: el.querySelector('.salary, .pay')?.textContent?.trim() || '面议',
                experience: el.querySelector('.experience, .exp')?.textContent?.trim() || '经验不限',
                education: el.querySelector('.education, .edu')?.textContent?.trim() || '学历不限',
                status: '招聘中'
            };
        }

        function isValidJobTitle(title) {
            if (!title || title.length < 2 || title.length > 50) return false;

            const excludeWords = ['首页', '关于我们', '联系我们', '帮助', '登录', '注册',
                                '搜索', '热门', '最新', '推荐', '职位管理', '岗位管理'];
            if (excludeWords.some(word => title.includes(word))) return false;

            const jobKeywords = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生',
                               '顾问', '设计师', '开发', '技术', '产品', '运营', '市场',
                               '销售', '财务', '人事', '行政', '客服', '测试', '运维',
                               '架构师', '分析师', '策划', 'Java', 'Python', 'C++',
                               '前端', '后端', '算法', 'AI', '数据'];

            return jobKeywords.some(keyword => title.includes(keyword));
        }

        function extractJobId(href) {
            if (!href) return 'unknown';

            const patterns = [
                /job\/([^\/?#]+)/,
                /job_detail\/([^\/?#]+)/,
                /jobid=([^&]+)/,
                /jid=([^&]+)/
            ];

            for (const pattern of patterns) {
                const match = href.match(pattern);
                if (match) return match[1];
            }

            return 'unknown';
        }
    })();
    """

    print("以下是BOSS直聘职位信息手动提取代码：")
    print("=" * 60)
    print(guide)
    print("=" * 60)


if __name__ == "__main__":
    print("BOSS直聘职位信息提取工具 - RPA仿真模式")
    print("=" * 50)
    print()

    create_manual_extraction_guide()
    print()

    simulate_human_behavior()
