"""HTML 幻灯片转 PDF（Playwright 逐页截图 + Pillow 拼合）"""
import sys, asyncio, os
from pathlib import Path

# ── 配置 ──
HTML_FILE = Path(__file__).parent / "index.html"
OUTPUT_PDF = Path(__file__).parent / "AI智能招聘分享.pdf"
VIEWPORT_W, VIEWPORT_H = 3840, 2160
# 每页等待时间（ms），需要等 CSS transition(700ms) + 入场动画
WAIT_PER_SLIDE = 1200

async def main():
    from playwright.async_api import async_playwright

    print(f"📂 输入: {HTML_FILE}")
    print(f"📄 输出: {OUTPUT_PDF}")
    print(f"🖥️  视口: {VIEWPORT_W}x{VIEWPORT_H}")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": VIEWPORT_W, "height": VIEWPORT_H})

        # 加载 HTML（用 file:// 协议）
        file_url = HTML_FILE.as_uri()
        print(f"⏳ 加载 {file_url} ...")
        await page.goto(file_url, wait_until="networkidle", timeout=30000)
        # 额外等待字体加载和 WebGL 初始化
        await page.wait_for_timeout(3000)

        # 获取幻灯片总数
        total = await page.evaluate("document.querySelectorAll('.slide').length")
        print(f"📑 共 {total} 张幻灯片\n")

        screenshots = []
        for i in range(total):
            # 跳转到第 i 页
            await page.evaluate(f"go({i})")
            await page.wait_for_timeout(WAIT_PER_SLIDE)

            # 截图
            img_path = Path(__file__).parent / f"_slide_{i:02d}.png"
            await page.screenshot(path=str(img_path), type="png")
            screenshots.append(str(img_path))
            print(f"  ✅ 第 {i+1}/{total} 页已截图")

        await browser.close()

    # 用 Pillow 拼合为 PDF
    print(f"\n🔧 拼合 PDF ...")
    from PIL import Image

    images = []
    for path in screenshots:
        img = Image.open(path).convert("RGB")
        images.append(img)

    if images:
        images[0].save(
            str(OUTPUT_PDF),
            "PDF",
            save_all=True,
            append_images=images[1:],
            resolution=150.0,
        )
        size_mb = OUTPUT_PDF.stat().st_size / 1024 / 1024
        print(f"\n✅ PDF 已生成: {OUTPUT_PDF} ({size_mb:.1f} MB, {total} 页)")

    # 清理临时截图
    for path in screenshots:
        os.remove(path)
    print("🗑️  临时截图已清理")

if __name__ == "__main__":
    asyncio.run(main())
