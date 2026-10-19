"""
调试工具 - 检查BOSS直聘职位管理页面的实际HTML结构
"""
import json
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def inspect_page():
    print("开始检查BOSS直聘职位管理页面的HTML结构...")

    with sync_playwright() as p:
        browser = None

        # 尝试连接到系统已安装的浏览器
        for channel in ["chrome", "msedge"]:
            try:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(project_root / f".storage/user_data_{channel}"),
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
            return

        # 寻找职位管理页面
        target_page = None

        # 等待页面加载
        time.sleep(2)

        for p in browser.pages:
            try:
                current_url = p.url
                print(f"检查页面: {current_url}")

                if "zhipin.com/web/geek/jobs" in current_url or "zhipin.com/web/geek/job" in current_url:
                    target_page = p
                    print(f"找到职位管理页面")
                    break
            except Exception:
                continue

        if not target_page:
            print("未找到职位管理页面")
            return

        page = target_page

        # 等待页面充分加载
        print("等待页面加载...")
        time.sleep(5)

        try:
            # 获取页面的完整HTML内容
            html_content = page.content()
            print(f"页面HTML长度: {len(html_content)} 字符")

            # 尝试查找常见职位相关元素
            selectors_to_test = [
                '*',  # 所有元素
                '[class*=""]',  # 所有带class的元素
                'a',  # 所有链接
                'div',  # 所有div
                'li',  # 列表项
                '.job', '.position', '.vacancy', '.recruit',
                '[data-job]', '[data-position]', '[data-v-job]'
            ]

            print("\n--- 各选择器找到的元素数量 ---")
            for selector in selectors_to_test[:10]:  # 只测试前10个，避免过多输出
                try:
                    elements = page.query_selector_all(selector)
                    print(f"选择器 '{selector}': {len(elements)} 个元素")

                    # 如果元素数量合理（不多不少），打印前几个元素的信息
                    if 0 < len(elements) <= 20:
                        for i, elem in enumerate(elements[:3]):  # 只打印前3个
                            try:
                                text = elem.inner_text().strip()[:100]  # 只取前100个字符
                                classes = elem.get_attribute('class')
                                print(f"  [{i}] 类: {classes}, 文本: {text}")
                            except Exception:
                                continue

                except Exception as e:
                    print(f"选择器 '{selector}' 错误: {e}")

            # 特别检查职位相关关键词
            print("\n--- 搜索职位相关关键词 ---")
            job_related_texts = [
                "java", "python", "工程师", "开发", "前端", "后端", "算法",
                "产品经理", "设计师", "运营", "市场", "销售", "HR", "财务",
                "职位", "岗位", "招聘", "job", "position"
            ]

            for keyword in job_related_texts:
                try:
                    # 查找包含关键词的元素
                    elements = page.query_selector_all(f"text={keyword}")
                    if elements:
                        print(f"关键词 '{keyword}': 找到 {len(elements)} 个元素")
                except Exception:
                    # 如果text选择器不支持，尝试其他方式
                    try:
                        all_elements = page.query_selector_all('*')
                        count = 0
                        for elem in all_elements[:50]:  # 检查前50个元素
                            try:
                                text = elem.inner_text().lower()
                                if keyword.lower() in text:
                                    count += 1
                            except Exception:
                                continue
                        if count > 0:
                            print(f"关键词 '{keyword}': 在页面中出现约 {count} 次")
                    except Exception:
                        continue

        except Exception as e:
            print(f"检查页面时出错: {e}")
            import traceback
            traceback.print_exc()

    print("\n检查完成")


if __name__ == "__main__":
    inspect_page()