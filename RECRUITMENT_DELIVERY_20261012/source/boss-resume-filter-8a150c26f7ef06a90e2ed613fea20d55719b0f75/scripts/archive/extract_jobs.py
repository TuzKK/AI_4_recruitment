"""
BOSS 职位提取脚本 - 从职位管理页面提取已发布职位
"""
import json
import sys
import time
from pathlib import Path
import re

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def extract_jobs():
    print("提示：请确保您已在BOSS直聘的职位管理页面。")
    print("职位管理页面的 URL 应该包含类似这样的路径: /web/geek/job/")
    print("")

    try:
        with sync_playwright() as p:
            browser = None

            # 尝试连接到系统已安装的浏览器，使用相同的用户数据目录
            storage_dir = project_root / ".storage"
            storage_dir.mkdir(parents=True, exist_ok=True)

            for channel in ["chrome", "msedge"]:
                try:
                    browser = p.chromium.launch_persistent_context(
                        user_data_dir=str(storage_dir / f"user_data_{channel}"),
                        headless=False,
                        channel=channel,
                        args=[
                            "--disable-blink-features=AutomationControlled",
                            "--disable-extensions",
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

            # 关键改进：优先查找已经存在的职位管理页面
            page = None
            target_page = None

            print("正在扫描浏览器中所有页面...")

            # 等待页面加载
            time.sleep(2)

            # 遍历所有页面，寻找符合条件的页面
            for p in browser.pages:
                try:
                    # 等待页面URL可用
                    current_url = p.url
                    print(f"检查页面 URL: {current_url}")

                    # 查找职位管理相关页面
                    if ("zhipin.com" in current_url and
                        ("/web/geek/job" in current_url or "position" in current_url.lower())):
                        target_page = p
                        print(f"找到职位管理页面: {current_url}")
                        break
                except Exception as e:
                    print(f"检查页面时出错: {e}")
                    continue

            # 如果没有找到职位管理页面，再查找包含zhipin.com的页面
            if not target_page:
                for p in browser.pages:
                    try:
                        current_url = p.url
                        if "zhipin.com" in current_url:
                            target_page = p
                            print(f"找到BOSS直聘页面: {current_url}")

                            # 尝试导航到职位管理
                            if "/web/geek/job" not in current_url:
                                print("当前页面不是职位管理页面，尝试导航...")
                                try:
                                    target_page.goto("https://www.zhipin.com/web/geek/jobs", timeout=10000)
                                    print("已尝试导航到职位管理页面")
                                    time.sleep(3)
                                except Exception:
                                    print("导航失败，继续使用当前页面")
                            break
                    except Exception:
                        continue

            # 如果仍然没有找到页面，创建新页面
            if not target_page:
                print("未找到BOSS直聘页面，创建新页面并导航...")
                target_page = browser.new_page()
                try:
                    target_page.goto("https://www.zhipin.com/web/geek/jobs", timeout=10000)
                    print("已导航到职位管理页面")
                except Exception:
                    target_page.goto("https://www.zhipin.com/", timeout=10000)
                    print("已导航到BOSS直聘主页，但不在职位管理页面")

            page = target_page
            current_url = page.url
            print(f"当前操作页面 URL: {current_url}")

            # 等待页面充分加载，特别是对于动态内容
            print("等待页面内容加载...")
            time.sleep(5)

            try:
                # 检查页面标题
                title = page.title()
                print(f"页面标题: {title}")
            except Exception:
                print("无法获取页面标题")

            # 尝试等待页面的主要内容加载
            try:
                # 等待主要容器加载
                page.wait_for_selector('div, ul, li, .job, .position', timeout=5000)
                print("页面主要内容已开始加载")
            except Exception:
                print("警告：页面主要内容可能还未加载")

            # 尝试提取职位信息
            job_data = []

            # 重要的改进：使用更灵活的方法查找职位信息
            print("开始查找职位信息...")

            # 方法1：查找页面中所有可能包含职位名称的文本
            try:
                # 获取页面所有文本 - 修正API调用
                page_content = page.content()
                page_text = page_content

                # 查找可能的职位标题模式
                import re
                job_title_patterns = [
                    r'[一-龥a-zA-Z0-9]{2,15}(?=工程师|经理|总监|主管|专员|助理|实习生|顾问|设计师|开发|技术|产品|运营|市场|销售|财务|人事|行政|客服|测试|运维|架构师|分析师|策划)',
                    r'(?<=招聘|急聘|诚聘)[一-龥a-zA-Z0-9]{2,15}(?=工程师|经理|总监|主管|专员|助理|实习生|顾问|设计师|开发|技术|产品|运营|市场|销售|财务|人事|行政|客服|测试|运维|架构师|分析师|策划)',
                ]

                for pattern in job_title_patterns:
                    matches = re.findall(pattern, page_text)
                    for match in matches:
                        if len(match.strip()) >= 2:
                            job_info = {
                                'job_id': f'pattern_{len(job_data)}',
                                'job_name': match.strip(),
                                'department': '未知部门',
                                'city': '未知城市',
                                'salary': '面议',
                                'experience': '经验不限',
                                'education': '学历不限',
                                'status': '招聘中'
                            }
                            if is_valid_job(job_info):
                                job_data.append(job_info)
                                print(f"通过模式匹配找到职位: {job_info['job_name']}")

            except Exception as e:
                print(f"模式匹配过程中出错: {e}")

            # 方法2：尝试多种常见的职位选择器
            print("尝试使用多种选择器查找职位...")

            # 扩展的选择器列表
            selectors_list = [
                # 常见的职位卡片类名
                '.job-card', '.job-item', '.position-card', '.position-item',
                '.job-info', '.job-card-wrapper',

                # BOSS直聘特有的类名
                '.info-primary', '.job-title', '.job-name', '.position-name',

                # 数据属性
                '[data-jobid]', '[data-positionid]', '[data-job]', '[data-position]',

                # 更一般的选择器
                'article', '.content', '.detail', '.card-body',

                # 链接相关
                'a[href*="/job/"]', 'a[href*="job_detail"]',

                # 列表项
                'li', '.item', '.list-item',
            ]

            # 遍历选择器，直到找到职位数据或遍历完所有选择器
            for selector in selectors_list:
                try:
                    elements = page.query_selector_all(selector)
                    print(f"选择器 '{selector}' 找到 {len(elements)} 个元素")

                    if elements:
                        for i, element in enumerate(elements[:20]):  # 只处理前20个，避免太多
                            try:
                                # 提取文本内容
                                element_text = element.inner_text().strip()

                                # 如果元素文本足够长且有意义，尝试解析
                                if len(element_text) > 5 and len(element_text) < 200:
                                    # 检查是否包含职位关键词
                                    if any(keyword in element_text for keyword in
                                          ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生',
                                           '顾问', '设计师', '开发', '技术', '产品', '运营', '市场',
                                           '销售', '财务', '人事', '行政', '客服', '测试', '运维',
                                           '架构师', '分析师', '策划', 'Java', 'Python', 'C++', '前端', '后端']):

                                        job_info = extract_job_from_element_advanced(element, len(job_data))
                                        if job_info and is_valid_job(job_info):
                                            job_data.append(job_info)
                                            print(f"提取到职位: {job_info['job_name']}")

                                            # 如果找到足够的职位就停止
                                            if len(job_data) >= 10:
                                                break

                                # 也尝试从元素属性中提取ID
                                job_id = None
                                for attr in ['data-jobid', 'data-positionid', 'data-id', 'id']:
                                    job_id = element.get_attribute(attr)
                                    if job_id:
                                        break

                                if job_id and element_text and len(element_text) > 2:
                                    # 如果我们有ID和文本，构建一个职位条目
                                    job_info = {
                                        'job_id': job_id,
                                        'job_name': element_text[:50],
                                        'department': '未知部门',
                                        'city': '未知城市',
                                        'salary': '面议',
                                        'experience': '经验不限',
                                        'education': '学历不限',
                                        'status': '招聘中'
                                    }
                                    if is_valid_job(job_info):
                                        job_data.append(job_info)
                                        print(f"提取到职位(属性): {job_info['job_name']}")

                            except Exception as elem_err:
                                continue  # 单个元素错误不影响其他元素处理

                        if job_data:  # 如果找到了职位，跳出选择器循环
                            break

                except Exception as sel_err:
                    print(f"选择器 '{selector}' 出错: {sel_err}")
                    continue

            # 方法3：如果没有找到职位，尝试直接查找页面中的链接
            if not job_data:
                print("尝试从页面链接中查找职位...")
                try:
                    # 获取所有链接
                    all_links = page.query_selector_all('a')
                    print(f"找到 {len(all_links)} 个链接")

                    for i, link in enumerate(all_links[:50]):  # 只检查前50个
                        try:
                            href = link.get_attribute('href') or ''
                            text = link.inner_text().strip()

                            # 检查链接是否指向职位详情页
                            if any(pattern in href for pattern in ['/job_detail/', '/job/', 'securityId=', '/web/geek/job']):
                                if is_meaningful_job_title(text):
                                    job_info = {
                                        'job_id': extract_job_id_from_href(href) or f'link_{i}',
                                        'job_name': text,
                                        'department': '未知部门',
                                        'city': '未知城市',
                                        'salary': '面议',
                                        'experience': '经验不限',
                                        'education': '学历不限',
                                        'status': '招聘中'
                                    }
                                    if is_valid_job(job_info):
                                        job_data.append(job_info)
                                        print(f"从链接提取职位: {job_info['job_name']}")

                                        if len(job_data) >= 5:  # 找到5个就足够了
                                            break
                        except Exception:
                            continue
                except Exception as link_err:
                    print(f"处理链接时出错: {link_err}")

            # 如果仍然没有找到职位，尝试另一种方法
            if not job_data:
                print("最后尝试：查找页面中所有的标题标签...")
                title_selectors = ['h1', 'h2', 'h3', 'h4', 'h5', '.title', '.name', '.job-title']

                for sel in title_selectors:
                    try:
                        title_elements = page.query_selector_all(sel)
                        for element in title_elements[:10]:  # 只处理前10个
                            try:
                                text = element.inner_text().strip()
                                if is_meaningful_job_title(text):
                                    job_info = {
                                        'job_id': f'title_{len(job_data)}',
                                        'job_name': text,
                                        'department': '未知部门',
                                        'city': '未知城市',
                                        'salary': '面议',
                                        'experience': '经验不限',
                                        'education': '学历不限',
                                        'status': '招聘中'
                                    }
                                    if is_valid_job(job_info):
                                        job_data.append(job_info)
                                        print(f"从标题提取职位: {job_info['job_name']}")

                                        if len(job_data) >= 3:
                                            break
                            except Exception:
                                continue
                        if job_data:
                            break
                    except Exception:
                        continue

            # 构造输出结果
            output = {
                "status": "success",
                "jobs": job_data,
                "count": len(job_data),
                "debug_info": {
                    "current_url": current_url,
                    "page_title": title if 'title' in locals() else "无法获取",
                    "selectors_tried": selectors_list,
                    "total_elements_checked": sum([len(page.query_selector_all(sel)) for sel in selectors_list[:5]]),
                    "final_job_count": len(job_data)
                }
            }

            print("RESULT:" + json.dumps(output, ensure_ascii=False, indent=2))

    except Exception as e:
        import traceback
        output = {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()[:500]
        }
        print("RESULT:" + json.dumps(output, ensure_ascii=False))

    finally:
        # 不关闭浏览器，让用户可以继续操作
        print("\n浏览器保持开启，您可以在其中继续操作...")


def extract_job_from_element_advanced(element, index):
    """从页面元素中高级提取职位信息"""
    try:
        job_info = {'job_id': f'adv_elem_{index}', 'department': '未知部门', 'city': '未知城市',
                   'salary': '面议', 'experience': '经验不限', 'education': '学历不限', 'status': '招聘中'}

        # 首先尝试获取元素文本
        element_text = element.inner_text().strip()

        # 尝试从文本中提取职位名
        potential_titles = [
            element_text[:100]  # 主文本
        ]

        # 尝试在子元素中查找特定的职位标题元素
        title_selectors = [
            '.job-title', '.job-name', '.position-name', '.job-text',
            'h3', 'h4', '.name', '.title', 'strong', 'b'
        ]

        for sel in title_selectors:
            try:
                title_elem = element.query_selector(sel)
                if title_elem:
                    title_text = title_elem.inner_text().strip()
                    if is_meaningful_job_title(title_text):
                        potential_titles.insert(0, title_text)  # 优先使用找到的标题
                        break
            except Exception:
                continue

        # 使用第一个有效的职位名称
        for title in potential_titles:
            if is_meaningful_job_title(title):
                job_info['job_name'] = title
                break

        # 尝试从元素属性获取ID
        id_attrs = ['data-jobid', 'data-positionid', 'data-id', 'id']
        for attr in id_attrs:
            try:
                attr_val = element.get_attribute(attr)
                if attr_val:
                    job_info['job_id'] = attr_val
                    break
            except Exception:
                continue

        return job_info if 'job_name' in job_info and job_info['job_name'] else None

    except Exception as e:
        print(f"高级提取职位信息出错: {e}")
        return None


def is_meaningful_job_title(text):
    """判断文本是否像是有意义的职位标题"""
    if not text:
        return False

    text = text.strip()

    if len(text) < 2 or len(text) > 50:
        return False

    # 过滤掉常见的非职位词汇
    exclude_patterns = [
        '首页', '关于我们', '联系我们', '帮助', '登录', '注册', '退出', '搜索',
        '热门', '最新', '推荐', '收藏', '分享', '举报', '编辑', '删除', '设置',
        '反馈', '招聘', '求职', '职场', '资讯', '新闻', '公告', '职位管理', '岗位管理',
        '首页', '我的', '消息', '通知', '简历', '投递', '订阅', '广告', '推广', '商务合作'
    ]

    for pattern in exclude_patterns:
        if pattern in text:
            return False

    # 检查是否包含职位特征词汇
    job_indicators = ['工程师', '经理', '总监', '主管', '专员', '助理', '实习生', '顾问',
                     '设计师', '开发', '技术', '产品', '运营', '市场', '销售', '财务',
                     '人事', '行政', '客服', '测试', '运维', '架构师', '分析师', '策划',
                     'Java', 'Python', 'C++', '前端', '后端', '算法', 'AI', '机器学习',
                     '数据', 'DBA', '运维', '测试', 'UI', 'UX', '视觉', '游戏', '安全',
                     '嵌入式', '硬件', '算法', '数学', '物理', '化学', '生物', '医学']

    for indicator in job_indicators:
        if indicator in text:
            return True

    # 如果包含较多中文字符，可能是职位名
    chinese_chars = sum(1 for c in text if '一' <= c <= '鿿')
    if chinese_chars >= 2:
        return True

    return False


def is_valid_job(job_info):
    """验证职位信息是否有效"""
    return ('job_name' in job_info and
            job_info['job_name'] and
            len(job_info['job_name'].strip()) >= 2)


def extract_job_id_from_href(href):
    """从链接中提取职位ID"""
    if not href:
        return None

    try:
        patterns = [
            r'jobid=([a-zA-Z0-9_-]+)',
            r'jid=([a-zA-Z0-9_-]+)',
            r'/job_detail/([^?&#]+)',
            r'/job/([^?&#]+)',
            r'/([a-zA-Z0-9_-]+)/?(?:\?|$)'
        ]

        for pattern in patterns:
            match = re.search(pattern, href)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None


if __name__ == "__main__":
    extract_jobs()