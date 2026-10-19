# -*- coding: utf-8 -*-
"""BOSS 直聘 geekCard 原始字段侦察

用途：dump 推荐列表 API 返回的 geekCard 原始对象的全部键，
     确认是否有 geekProject / certificate / skillList 等未提取字段。

不需要发现新接口——直接用已调通的推荐列表 API。

使用方法：
1. 启动 BOSS 简历筛选器，确保 Chrome 已连接
2. 在浏览器中打开推荐页面 https://www.zhipin.com/web/chat/recommend
3. 运行本脚本：python tests/manual/recon_detail_api.py
4. 脚本监听推荐列表 API，翻页或切换岗位触发请求即可
5. 输出每个 geekCard 的全部键名 + 嵌套结构

按 Ctrl+C 停止。
"""
import json
import re
from datetime import datetime
from pathlib import Path

try:
    from DrissionPage import ChromiumPage
except ImportError:
    print("请先安装 DrissionPage: pip install DrissionPage")
    exit(1)


OUTPUT_DIR = Path(__file__).parent / "recon_output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 关注的键名（如果 geekCard 中出现，高亮标记）
INTERESTING_KEYS = {
    "geekproject", "projectlist", "project", "projectexperience",
    "certificate", "certlist", "certification", "qualification",
    "geekskill", "skilllist", "skilltag", "geektag", "taglist",
    "geekdetail", "geekinfo", "geekprofile", "geekresume",
    "fullresume", "resumedetail", "resumeattachment",
    "geekcert", "geekcertificate", "geekproject",
    "welfare", "benefit", "salarydetail",
    "evaluation", "portfolio", "works_show",
}


def _find_geek_cards(obj, path=""):
    """递归查找 JSON 中所有 geekCard 对象。"""
    cards = []
    if isinstance(obj, dict):
        if "geekCard" in obj:
            gc = obj["geekCard"]
            if isinstance(gc, dict):
                cards.append((path + ".geekCard", gc))
        # 也检查自身是否是 geekCard（某些结构直接返回）
        if any(k in obj for k in ("geekName", "geekEdus", "geekWorks", "encryptGeekId")):
            cards.append((path, obj))
        for k, v in obj.items():
            if k != "geekCard":
                cards.extend(_find_geek_cards(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            cards.extend(_find_geek_cards(item, f"{path}[{i}]"))
    return cards


def _dump_keys(obj, indent=0, max_depth=3):
    """递归打印对象的全部键和值类型，限制深度。"""
    prefix = "  " * indent
    if not isinstance(obj, dict):
        return
    for key in sorted(obj.keys()):
        val = obj[key]
        tag = "🔥" if key.lower() in INTERESTING_KEYS else "  "
        if isinstance(val, dict):
            print(f"{prefix}{tag} {key}: dict({len(val)} keys)")
            if indent < max_depth:
                _dump_keys(val, indent + 1, max_depth)
        elif isinstance(val, list):
            print(f"{prefix}{tag} {key}: list({len(val)} items)")
            if val and indent < max_depth and isinstance(val[0], dict):
                print(f"{prefix}    [0] keys: {sorted(val[0].keys())}")
                if indent + 1 < max_depth:
                    _dump_keys(val[0], indent + 2, max_depth)
        else:
            val_str = str(val)
            if len(val_str) > 80:
                val_str = val_str[:80] + "..."
            print(f"{prefix}{tag} {key}: {type(val).__name__} = {val_str}")


def main():
    print("=" * 80)
    print("BOSS geekCard 原始字段侦察")
    print("=" * 80)

    try:
        page = ChromiumPage()
    except Exception as e:
        print(f"无法连接浏览器: {e}")
        return

    print(f"✅ 已连接浏览器 — {page.url}")
    print()
    print("📡 监听推荐列表 API (zpjob/rec/geek/list)...")
    print("   翻页或切换岗位即可触发请求")
    print("   按 Ctrl+C 停止")
    print()

    try:
        listener = page.listen
        listener.start("zpjob/rec/geek/list", method=("GET", "POST"),
                        res_type=("XHR", "Fetch"))
    except Exception as e:
        print(f"监听启动失败: {e}")
        return

    card_count = 0
    all_keys_seen = set()

    try:
        while True:
            packet = listener.wait(timeout=1)
            if not packet:
                continue

            body = ""
            try:
                body = packet.response.body or ""
            except Exception:
                continue
            if not body:
                continue

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                continue

            cards = _find_geek_cards(data)
            if not cards:
                continue

            print(f"\n{'='*80}")
            print(f"📦 本次响应：{len(body)} chars，找到 {len(cards)} 个 geekCard")
            print(f"{'='*80}")

            # 保存完整响应
            ts = datetime.now().strftime("%H%M%S")
            outfile = OUTPUT_DIR / f"raw_response_{ts}.json"
            outfile.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"💾 完整响应已保存: {outfile}")

            for path, card in cards:
                card_count += 1
                keys = sorted(card.keys())
                all_keys_seen.update(keys)
                interesting = [k for k in keys if k.lower() in INTERESTING_KEYS]

                print(f"\n--- geekCard #{card_count} ({path}) ---")
                print(f"  总键数: {len(keys)}")
                print(f"  全部键: {keys}")
                if interesting:
                    print(f"  🔥 命中关注键: {interesting}")
                else:
                    print(f"  ⚪ 无关注键命中")

                # 第一个 card 做完整展开
                if card_count <= 3:
                    print(f"\n  详细结构:")
                    _dump_keys(card, indent=2, max_depth=2)

            # 汇总所有见过的键
            print(f"\n{'='*80}")
            print(f"📊 累计 {card_count} 个 geekCard，全部键名并集：")
            for k in sorted(all_keys_seen):
                tag = " 🔥" if k.lower() in INTERESTING_KEYS else ""
                print(f"  • {k}{tag}")

    except KeyboardInterrupt:
        print("\n\n⏹ 停止监听")
    finally:
        try:
            listener.stop()
        except Exception:
            pass

    print(f"\n{'='*80}")
    print(f"侦察完成：共分析 {card_count} 个 geekCard")
    print(f"输出目录：{OUTPUT_DIR}")
    if all_keys_seen:
        interesting_found = [k for k in sorted(all_keys_seen) if k.lower() in INTERESTING_KEYS]
        if interesting_found:
            print(f"\n✅ 找到关注字段: {', '.join(interesting_found)}")
            print("   下一步：修改 _build_api_profile() 提取这些字段")
        else:
            print("\n❌ 未找到项目经历/证书/完整技能等字段")
            print("   推荐列表 API 返回的数据已经是我们能拿到的全部了")


if __name__ == "__main__":
    main()
