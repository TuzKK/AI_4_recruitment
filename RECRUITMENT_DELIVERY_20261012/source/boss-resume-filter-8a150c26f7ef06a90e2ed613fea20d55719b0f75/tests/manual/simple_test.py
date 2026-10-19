"""
简化版浏览器测试脚本
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def test_simple_browser():
    storage_dir = project_root / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = None

        # 只尝试 Chrome
        try:
            print("尝试启动 Chrome 浏览器...")
            browser = p.chromium.launch_persistent_context(
                user_data_dir=str(storage_dir / "user_data_chrome_test"),
                headless=False,  # 设置为 False 确保可见
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-extensions",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            print("成功使用 Chrome 浏览器")

            # 创建一个页面并直接导航到BOSS直聘
            page = browser.new_page()
            print("正在导航到 https://www.zhipin.com...")

            # 设置页面加载超时
            page.set_default_timeout(30000)  # 30秒

            try:
                response = page.goto("https://www.zhipin.com/", wait_until="domcontentloaded")
                print(f"页面状态码: {response.status if response else 'Unknown'}")
                print("页面已加载完成")
            except Exception as e:
                print(f"页面加载可能超时，但继续执行... {e}")

            print("浏览器已打开并导航到BOSS直聘，请手动完成登录...")
            print("请按 Ctrl+C 退出...")

            # 保持浏览器开启
            import time
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n正在退出...")

        except Exception as e:
            print(f"Chrome 启动失败: {e}")
            return False

    return True


if __name__ == "__main__":
    test_simple_browser()