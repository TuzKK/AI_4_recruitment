"""
测试用的简单浏览器打开脚本
"""
import sys
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def test_browser():
    storage_dir = project_root / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = None

        # 尝试 Chrome -> Edge
        for channel in ["chrome", "msedge"]:
            try:
                print(f"尝试启动 {channel} 浏览器...")
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=str(storage_dir / f"user_data_{channel}"),
                    headless=False,  # 设置为 False 确保可见
                    channel=channel,
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--disable-extensions",
                        "--no-sandbox",
                    ],
                )
                print(f"成功使用 {channel} 浏览器")

                # 创建一个简单的页面
                page = browser.new_page()
                page.goto("about:blank")
                page.set_content("""
                    <html>
                    <head><title>BOSS 直聘助手 - 测试</title></head>
                    <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                        <h1>✅ 浏览器已成功打开！</h1>
                        <div style="background: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0;">
                            <h2>操作指南：</h2>
                            <ol style="text-align: left; font-size: 16px; margin: 20px auto; max-width: 600px;">
                                <li>在上方地址栏输入: <strong>https://www.zhipin.com/</strong></li>
                                <li>扫码登录 BOSS 直聘</li>
                                <li>登录后点击左侧菜单的 <strong>"职位管理"</strong></li>
                                <li>等待职位列表加载完成</li>
                            </ol>
                        </div>
                        <p style="color: #666; margin-top: 30px;">此窗口将保持打开状态，请继续操作...</p>
                    </body>
                    </html>
                """)

                print("浏览器已打开并显示操作指南，请手动完成登录步骤...")
                print("请按 Ctrl+C 退出...")

                # 保持浏览器开启
                import time
                try:
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n正在退出...")
                    break

                break
            except Exception as e:
                print(f"{channel} 启动失败: {e}")
                continue

        if not browser:
            print("错误：无法启动任何浏览器，请确保安装了 Chrome 或 Edge")
            return False

    return True


if __name__ == "__main__":
    test_browser()