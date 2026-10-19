"""
BOSS直聘职位信息提取 - API接口方式
尝试通过BOSS直聘的API接口获取职位信息，而非直接解析页面DOM
"""
import json
import sys
import time
import requests
from pathlib import Path
from urllib.parse import urlparse, parse_qs

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def extract_jobs_via_api():
    """
    通过API接口提取职位信息
    这种方式比解析DOM更可靠，也更不容易被检测为爬虫
    """
    print("提示：请确保您已在BOSS直聘的职位管理页面。")
    print("此脚本将尝试从浏览器上下文获取API接口数据。")
    print("")

    storage_dir = project_root / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = None

        # 尝试连接到浏览器
        for channel in ["chrome", "msedge"]:
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(storage_dir / f"user_data_{channel}"),
                    headless=False,
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
            print("正在导航到职位管理页面...")
            page = browser.new_page()
            page.goto("https://www.zhipin.com/web/geek/jobs", timeout=10000)
            time.sleep(5)

        # 等待页面加载完成
        time.sleep(3)

        try:
            print("正在监控网络请求以捕获API调用...")

            # 通过浏览器上下文获取网络请求
            # 我们要监听API请求，获取真实的职位数据
            captured_requests = []

            # 监听页面请求
            def capture_request(request):
                if 'api' in request.url.lower() and ('job' in request.url.lower() or 'position' in request.url.lower()):
                    captured_requests.append({
                        'url': request.url,
                        'method': request.method,
                        'headers': dict(request.headers),
                        'postData': getattr(request, 'post_data', None)
                    })

            page.on("request", capture_request)

            # 刷新页面以触发API请求
            page.reload()
            time.sleep(5)

            # 检查捕获的请求
            api_urls = []
            for req in captured_requests:
                if 'position' in req['url'] or 'job' in req['url'] or 'api' in req['url']:
                    api_urls.append(req['url'])

            print(f"捕获到 {len(api_urls)} 个潜在API请求")

            # 现在尝试直接从页面执行JavaScript获取可能的API端点或数据
            js_data_extraction = r"""
            (function() {
                // 查找页面中可能存储职位数据的全局变量
                const dataSources = [];

                // 检查全局对象中是否有职位数据
                if (window.__INITIAL_STATE__) {
                    dataSources.push({
                        source: '__INITIAL_STATE__',
                        data: window.__INITIAL_STATE__
                    });
                }

                if (window.INITIAL_JSONP_DATA) {
                    dataSources.push({
                        source: 'INITIAL_JSONP_DATA',
                        data: window.INITIAL_JSONP_DATA
                    });
                }

                // 检查可能的数据容器
                const potentialContainers = ['appData', 'initialData', 'pageData', 'jobData'];
                for (const container of potentialContainers) {
                    if (window[container]) {
                        dataSources.push({
                            source: container,
                            data: window[container]
                        });
                    }
                }

                // 查找页面中的script标签，可能包含JSON数据
                const scripts = Array.from(document.querySelectorAll('script'));
                for (const script of scripts) {
                    const text = script.textContent;
                    if (text && text.includes('job') && text.includes('{')) {
                        try {
                            // 尝试提取JSON对象
                            const jsonMatch = text.match(/\{[\s\S]*\}/);
                            if (jsonMatch) {
                                const jsonObj = JSON.parse(jsonMatch[0]);
                                dataSources.push({
                                    source: 'inline-json',
                                    data: jsonObj
                                });
                            }
                        } catch (e) {
                            // 忽略解析错误
                        }
                    }
                }

                return dataSources;
            })();
            """

            try:
                data_sources = page.evaluate(js_data_extraction)
                print(f"从页面发现了 {len(data_sources)} 个数据源")

                # 处理数据源
                jobs = []
                for source in data_sources:
                    data = source.get('data', {})

                    # 尝试查找职位相关数据
                    positions = find_positions_in_data(data)
                    jobs.extend(positions)

                    if jobs:
                        print(f"从 {source['source']} 找到了 {len(positions)} 个职位")

                if jobs:
                    result = {
                        "status": "success",
                        "jobs": jobs,
                        "count": len(jobs),
                        "source": "page_data_extraction"
                    }
                    print("RESULT:" + json.dumps(result, ensure_ascii=False))
                    return
            except Exception as js_error:
                print(f"执行页面JS时出错: {js_error}")

            # 如果直接数据获取失败，尝试模拟用户交互来加载数据
            print("尝试通过用户交互加载数据...")

            # 滚动页面以加载更多职位
            try:
                for i in range(5):  # 滚动5次
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(2)
            except Exception:
                pass

            # 再次尝试获取数据
            try:
                data_sources_after_scroll = page.evaluate(js_data_extraction)
                jobs_after_scroll = []

                for source in data_sources_after_scroll:
                    data = source.get('data', {})
                    positions = find_positions_in_data(data)
                    jobs_after_scroll.extend(positions)

                if jobs_after_scroll:
                    result = {
                        "status": "success",
                        "jobs": jobs_after_scroll,
                        "count": len(jobs_after_scroll),
                        "source": "page_data_extraction_after_scroll"
                    }
                    print("RESULT:" + json.dumps(result, ensure_ascii=False))
                    return
            except Exception as scroll_error:
                print(f"滚动后获取数据失败: {scroll_error}")

            # 如果以上都失败，返回空结果
            result = {
                "status": "success",
                "jobs": [],
                "count": 0,
                "message": "未能从页面获取到职位数据，请确保页面已完全加载"
            }
            print("RESULT:" + json.dumps(result, ensure_ascii=False))

        except Exception as e:
            import traceback
            error_result = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()[:500]
            }
            print("RESULT:" + json.dumps(error_result, ensure_ascii=False))


def find_positions_in_data(data, depth=0, max_depth=5):
    """
    递归查找数据结构中的职位信息
    """
    if depth > max_depth:
        return []

    jobs = []

    if isinstance(data, dict):
        # 检查当前层级是否包含职位信息
        if contains_job_keys(data):
            positions = extract_positions_from_dict(data)
            if positions:
                jobs.extend(positions)

        # 递归检查所有值
        for value in data.values():
            jobs.extend(find_positions_in_data(value, depth + 1, max_depth))

    elif isinstance(data, list):
        # 检查列表中的每一项
        for item in data:
            jobs.extend(find_positions_in_data(item, depth + 1, max_depth))

    return jobs


def contains_job_keys(data):
    """
    检查字典是否包含职位相关的关键字
    """
    if not isinstance(data, dict):
        return False

    job_indicators = [
        'job', 'position', 'title', 'name', 'salary', 'city', 'exp', 'degree',
        'job_name', 'job_title', 'position_name', 'salary_range', 'work_city',
        'work_exp', 'edu_level', 'recruit', 'vacancy', 'posting'
    ]

    keys_str = ' '.join(str(k).lower() for k in data.keys())
    return any(indicator in keys_str for indicator in job_indicators)


def extract_positions_from_dict(data):
    """
    从字典中提取职位信息
    """
    jobs = []

    # 如果这是一个职位对象
    if is_position_object(data):
        job = transform_to_job_format(data)
        if job:
            jobs.append(job)

    # 如果包含职位列表
    if 'list' in data or 'data' in data or 'items' in data:
        potential_list = data.get('list') or data.get('data') or data.get('items')
        if isinstance(potential_list, list):
            for item in potential_list:
                if is_position_object(item):
                    job = transform_to_job_format(item)
                    if job:
                        jobs.append(job)

    return jobs


def is_position_object(obj):
    """
    判断对象是否为职位对象
    """
    if not isinstance(obj, dict):
        return False

    required_fields = ['job_name', 'title', 'position', 'name']
    possible_title_fields = ['job_name', 'job_title', 'position_name', 'title', 'name']

    # 检查是否有职位名称相关字段
    has_title = any(field in obj and obj[field] for field in possible_title_fields)

    # 检查是否有其他职位相关字段
    other_job_fields = ['salary', 'city', 'experience', 'exp', 'education', 'degree', 'company']
    has_other = any(field in obj for field in other_job_fields)

    return has_title or has_other


def transform_to_job_format(data):
    """
    将数据转换为统一的职位格式
    """
    # 确定职位名称字段
    title_fields = ['job_name', 'job_title', 'position_name', 'title', 'name']
    job_name = None
    for field in title_fields:
        if field in data and data[field]:
            job_name = str(data[field])
            break

    if not job_name or len(job_name.strip()) < 2:
        return None

    # 提取其他字段
    job_id = str(data.get('job_id', data.get('id', data.get('positionId', f"unknown_{hash(job_name)}"))))
    department = str(data.get('department', data.get('dept', data.get('company', '未知部门'))))
    city = str(data.get('city', data.get('work_city', data.get('areaDistrict', '未知城市'))))
    salary = str(data.get('salary', data.get('salary_range', data.get('salaryDesc', '面议'))))
    experience = str(data.get('experience', data.get('work_exp', data.get('exp', '经验不限'))))
    education = str(data.get('education', data.get('edu_level', data.get('degree', '学历不限'))))

    return {
        'job_id': job_id,
        'job_name': job_name.strip(),
        'department': department.strip(),
        'city': city.strip(),
        'salary': salary.strip(),
        'experience': experience.strip(),
        'education': education.strip(),
        'status': '招聘中'
    }


if __name__ == "__main__":
    extract_jobs_via_api()
