"""
BOSS 职位获取脚本 - 纯手动浏览器打开
这个脚本只负责打开浏览器并显示操作指南，然后立即退出，
不会对浏览器做任何自动化操作，允许用户完全手动操作。
"""
import json
import sys
import threading
import time
import webbrowser
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from playwright.sync_api import sync_playwright


def open_manual_login_browser():
    storage_dir = project_root / ".storage"
    storage_dir.mkdir(parents=True, exist_ok=True)

    # 首先尝试使用系统默认浏览器打开
    print("正在尝试使用系统默认浏览器打开BOSS直聘...")
    boss_url = "https://www.zhipin.com/"
    webbrowser.open(boss_url)

    # 然后尝试启动Playwright浏览器以提供更多选项
    try:
        with sync_playwright() as p:
            browser = None
            channel_used = ""

            # 尝试 Chrome -> Edge
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
                    channel_used = channel
                    print(f"使用 {channel} 浏览器成功")
                    break
                except Exception as e:
                    print(f"{channel} 启动失败：{e}")
                    continue

            if not browser:
                print("注意：虽然系统默认浏览器已打开，但Playwright浏览器启动失败")
                print("您仍可在系统浏览器中完成登录操作")

                # 输出成功结果
                output = {
                    "status": "success",
                    "message": "已尝试使用系统默认浏览器打开，请手动完成登录和导航操作",
                    "browser_opened": True
                }
                print("RESULT:" + json.dumps(output, ensure_ascii=False))
                return

            # 创建新页面并显示操作指南
            page = browser.new_page()

            page.set_content("""
            <html>
            <head><title>BOSS 直聘助手 - 请手动登录</title></head>
            <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center; background: #f8f9fa;">
                <div style="max-width: 800px; margin: 0 auto; background: white; border-radius: 10px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                    <h1 style="color: #28a745;">✅ 请手动完成以下操作</h1>

                    <div style="background: #fff3cd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #ffc107;">
                        <h2 style="margin-top: 0; color: #856404;">重要提醒</h2>
                        <p style="color: #856404; font-weight: bold;">此脚本现在退出，<span style="text-decoration: underline;">不再控制浏览器</span>！</p>
                    </div>

                    <div style="background: #d4edda; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #28a745;">
                        <h2 style="margin-top: 0;">操作步骤：</h2>
                        <ol style="text-align: left; font-size: 16px; line-height: 1.8;">
                            <li>如果尚未打开，请在浏览器中访问: <strong style="color: #007bff;">https://www.zhipin.com/</strong></li>
                            <li>扫码登录 BOSS 直聘（或使用账号密码登录）</li>
                            <li>登录后点击左侧菜单的 <strong style="color: #007bff;">"职位管理"</strong></li>
                            <li>等待职位列表加载完成</li>
                        </ol>
                    </div>

                    <div style="background: #cce5ff; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #007bff;">
                        <h3 style="margin-top: 0; color: #004085;">完成操作后：</h3>
                        <p>返回到 Web 界面，点击 <strong>"第二步：提取职位信息"</strong></p>
                        <p>浏览器将保持打开状态供您使用</p>
                    </div>

                    <div style="margin-top: 30px; font-size: 14px; color: #666; background: #f1f3f4; padding: 15px; border-radius: 5px;">
                        <p><strong>💡 提示：</strong>脚本已退出，浏览器现在完全由您手动控制</p>
                    </div>
                </div>

                <script>
                    // 5秒后自动关闭此标签页，让用户专注于主页面
                    setTimeout(function() {
                        // 不关闭窗口，只提示用户
                        console.log("脚本已完成，浏览器现在完全由用户控制");
                    }, 5000);
                </script>
            </body>
            </html>
            """)

            print("浏览器已打开并显示操作指南...")
            print("脚本现在退出，浏览器完全由您手动控制。")

            # 立即输出成功结果并退出
            output = {
                "status": "success",
                "message": "浏览器已打开，请手动完成登录和导航操作",
                "browser_opened": True
            }
            print("RESULT:" + json.dumps(output, ensure_ascii=False))

            # 关闭当前页面但保留浏览器
            try:
                page.close()
            except Exception:
                pass

            # 不要关闭浏览器，让用户继续操作

    except ImportError:
        # 如果Playwright不可用，仅使用系统浏览器
        print("Playwright不可用，仅使用系统默认浏览器")

        output = {
            "status": "success",
            "message": "已使用系统默认浏览器打开，请手动完成登录和导航操作",
            "browser_opened": True
        }
        print("RESULT:" + json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    open_manual_login_browser()