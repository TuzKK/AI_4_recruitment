"""macOS Accessibility API via JXA (JavaScript for Automation).

Production-ready wrapper for BOSS直聘 Electron app automation.
Optimized for speed and reliability.

Key design choices:
  - Full AX tree scan is ~28s for 1800 elements — done ONCE to build a
    card index, then all subsequent clicks use direct index (fast, ~100ms)
  - No Playwright, no JS injection, no DOM manipulation
  - Uses OS-level AXPress — same API as VoiceOver (not detectable)
  - BOSS app must be launched with --force-renderer-accessibility
"""

from __future__ import annotations

import asyncio
import json
import logging
import subprocess
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

BOSS_PROCESS_NAME = "BOSS直聘"


# ═════════════════════════════════════════════════════════════════════════
# Low-level JXA runner
# ═════════════════════════════════════════════════════════════════════════

def _run_jxa(script: str, timeout: int = 30) -> str:
    """Run a JXA script and return stdout."""
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                logger.debug("JXA stderr: %s", stderr[:300])
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("JXA timed out after %ds", timeout)
        return ""
    except Exception as exc:
        logger.warning("JXA error: %s", exc)
        return ""


# ═════════════════════════════════════════════════════════════════════════
# Fast: click element by index (single IPC call, ~100ms)
# ═════════════════════════════════════════════════════════════════════════

def click_element_at_index(
    ax_index: int,
    process: str = BOSS_PROCESS_NAME,
) -> bool:
    """Click the AX element at a specific 1-based index. Fast."""
    script = f'''
var se = Application("System Events");
var proc = se.processes["{process}"];
var win = proc.windows[0];
var elem = win.entireContents()[{ax_index - 1}];
try {{ elem.click(); "ok" }} catch(e) {{ "err: " + e }}
'''
    result = _run_jxa(script, timeout=10)
    if result == "ok":
        return True
    logger.debug("click_element_at_index(%d): %s", ax_index, result or "timeout")
    return False


def click_element_js(
    *,
    role: Optional[str] = None,
    name: Optional[str] = None,
    description_contains: Optional[str] = None,
    process: str = BOSS_PROCESS_NAME,
    timeout: int = 30,
) -> bool:
    """Click element by scanning the tree and matching criteria. Slower.

    Use click_element_at_index() when you already know the index.
    """
    conditions = []
    if role:
        conditions.append(f'(e.role() === "{role}")')
    if name:
        conditions.append(f'((e.name() || "") === "{name}")')
    if description_contains:
        conditions.append(f'((e.description() || "").indexOf("{description_contains}") >= 0)')

    cond_js = " && ".join(conditions) if conditions else "true"

    script = f'''
var se = Application("System Events");
var proc = se.processes["{process}"];
var win = proc.windows[0];
var all = win.entireContents();
for (var i = 0; i < all.length; i++) {{
    try {{
        var e = all[i];
        if ({cond_js}) {{
            e.click();
            "ok:" + (i + 1);
            break;
        }}
    }} catch(x) {{}}
}}
"not_found";
'''
    result = _run_jxa(script, timeout=timeout)
    if result and result.startswith("ok:"):
        return True
    logger.debug("click_element_js not found: role=%s name=%s", role, name)
    return False


# ═════════════════════════════════════════════════════════════════════════
# Card extraction: one full scan, return everything needed
# ═════════════════════════════════════════════════════════════════════════

def scan_tree(
    process: str = BOSS_PROCESS_NAME,
    timeout: int = 120,
    max_retries: int = 2,
) -> dict[str, Any]:
    """Full AX tree scan — returns structured data for all elements.

    With retry: if JXA hangs or times out, retry up to max_retries.

    Returns:
        {total: int, greet_indices: [int], avatar_indices: [int],
         text_indices: [(index, name), ...]}
    """
    for attempt in range(max_retries + 1):
        raw = _run_scan_jxa(process, timeout)
        if raw:
            result = _parse_scan_output(raw)
            if result.get("total", 0) > 100:
                return result
            logger.warning("Scan attempt %d returned only %d elements, retrying...",
                          attempt + 1, result.get("total", 0))
        else:
            logger.warning("Scan attempt %d timed out/hung, retrying...", attempt + 1)

        if attempt < max_retries:
            time.sleep(2)

    # All retries failed
    return {"total": 0, "greet_indices": [], "avatar_indices": [],
            "text_indices": [], "texts_by_index": {}}


def _run_scan_jxa(process: str, timeout: int) -> str:
    """Run the raw JXA scan script. Returns raw output string or '' on failure."""
    script = f'''
var se = Application("System Events");
var proc = se.processes["{process}"];
var win = proc.windows[0];
var all = win.entireContents();
var total = all.length;

var greet = [];
var avatars = [];
var texts = [];

for (var i = 0; i < total; i++) {{
    try {{
        var e = all[i];
        var role = e.role();
        if (role === "AXButton") {{
            var n = e.name() || "";
            if (n === "打招呼") greet.push((i + 1) + "");
        }}
        if (role === "AXImage") {{
            avatars.push((i + 1) + "");
        }}
        if (role === "AXStaticText") {{
            var n = e.name() || "";
            if (n.length > 0 && n.length <= 200) {{
                // Replace | and : to avoid corrupting our delimiter format
                var safe = n.replace(/\\|/g, "/").replace(/:/g, "：");
                texts.push((i + 1) + ":" + safe);
            }}
        }}
    }} catch(x) {{}}
}}

"g:" + greet.join(",") + "|a:" + avatars.join(",") + "|t:" + texts.join(";;") + "|n:" + total;
'''
    try:
        result = subprocess.run(
            ["osascript", "-l", "JavaScript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if stderr:
                logger.debug("JXA scan stderr: %s", stderr[:300])
            return ""
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning("JXA scan timed out after %ds", timeout)
        return ""
    except Exception as exc:
        logger.warning("JXA scan error: %s", exc)
        return ""


def _parse_scan_output(raw: str) -> dict[str, Any]:
    """Parse the compact delimited format from the JXA scan."""
    result: dict[str, Any] = {"total": 0, "greet_indices": [],
                                "avatar_indices": [], "text_indices": [],
                                "texts_by_index": {}}

    parts = {}
    for seg in raw.split("|"):
        if ":" in seg:
            key, val = seg.split(":", 1)
            parts[key] = val

    result["total"] = int(parts.get("n", 0))
    if result["total"] < 50:
        return result  # Too few elements — likely app needs restart

    g_val = parts.get("g", "")
    result["greet_indices"] = [int(x) for x in g_val.split(",") if x]

    a_val = parts.get("a", "")
    result["avatar_indices"] = [int(x) for x in a_val.split(",") if x]

    t_val = parts.get("t", "")
    texts_by_index: dict[int, str] = {}
    text_indices: list[int] = []
    for pair in t_val.split(";;"):
        if ":" in pair:
            try:
                idx_s, name = pair.split(":", 1)
                idx = int(idx_s)
                texts_by_index[idx] = name
                text_indices.append(idx)
            except ValueError:
                pass
    result["texts_by_index"] = texts_by_index
    result["text_indices"] = text_indices

    return result


def build_cards_from_scan(scan_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse candidate cards from AX tree scan data.

    BOSS card structure (per card, between avatar and greet button):
      salary → name → active → age/exp/edu/status → "期望" city role →
      "优势" long_self_desc → skill_tags → work_history → education

    Returns list of card dicts with all extracted fields.
    """
    greet_indices = sorted(scan_result.get("greet_indices", []))
    avatar_indices = sorted(scan_result.get("avatar_indices", []))
    texts_by_index = scan_result.get("texts_by_index", {})

    if not greet_indices:
        return []

    cards: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    # Pre-compute sorted text indices for faster range queries
    sorted_texts = sorted(texts_by_index.keys())

    for card_idx, gi in enumerate(greet_indices):
        # ── Find the correct avatar for this greet button ──
        primary_avatar = 0
        for ai in sorted(avatar_indices, reverse=True):
            if ai > gi:
                continue
            for offset in range(1, 15):
                txt = texts_by_index.get(ai + offset, "")
                if "K" in txt and "-" in txt and len(txt) < 15:
                    primary_avatar = ai
                    break
            if primary_avatar:
                break
        if not primary_avatar:
            for ai in sorted(avatar_indices, reverse=True):
                if ai < gi:
                    primary_avatar = ai
                    break
        if not primary_avatar:
            continue

        # ── Collect all texts in card range ──
        all_texts: list[str] = []
        for ti in sorted_texts:
            if primary_avatar < ti < gi:
                txt = texts_by_index[ti]
                if txt:
                    all_texts.append(txt)

        if len(all_texts) < 3:
            continue

        # ── Parse structured sections ──
        salary = all_texts[0] if all_texts else ""
        name = all_texts[1] if len(all_texts) > 1 else ""

        if not name or name in seen_names:
            continue
        seen_names.add(name)

        # Find section boundaries
        expect_idx = -1
        interest_idx = -1   # "最近关注" — same as "期望" in newer UI
        advantage_idx = -1
        for j, t in enumerate(all_texts):
            if (t == "期望" or t.startswith("期望")) and expect_idx < 0:
                expect_idx = j
            if t == "最近关注" and interest_idx < 0:
                interest_idx = j
            if t == "优势" and advantage_idx < 0:
                advantage_idx = j

        # ── base_info: texts between name and expect/interest/advantages ──
        section_start = expect_idx if expect_idx > 0 else (
            interest_idx if interest_idx > 0 else (
                advantage_idx if advantage_idx > 0 else len(all_texts)))
        base_parts: list[str] = []
        base_end = min(section_start, len(all_texts))
        for j in range(2, base_end):
            t = all_texts[j]
            if t in ("期望", "最近关注", "优势", "经历", "正在搜索", "筛选"):
                break
            # Don't add active status text to base_parts
            if "活跃" not in t and "在线" not in t:
                base_parts.append(t)

        # ── expect city/position: from "期望" or "最近关注" ──
        expect_city = ""
        expect_position = ""
        city_section = expect_idx if expect_idx > 0 else interest_idx
        if city_section > 0:
            if city_section + 1 < len(all_texts):
                expect_city = all_texts[city_section + 1]
            if city_section + 2 < len(all_texts):
                expect_position = all_texts[city_section + 2]

        # Also check if city appears anywhere near salary/header (page-level filter)
        all_text_str = " ".join(all_texts)

        # ── advantages: long text after "优势" section ──
        advantages = ""
        if advantage_idx > 0:
            for j in range(advantage_idx + 1, len(all_texts)):
                t = all_texts[j]
                # Advantage text is long + contains punctuation
                if len(t) > 40:
                    advantages = t
                    break

        # ── tags: short technical terms (not work/edu history) ──
        # Build the card into LLM-ready text directly
        skill_tags: list[str] = []
        work_experiences: list[str] = []
        education_items: list[str] = []

        # Process texts after advantages (or after base_info if no sections)
        parse_start = max(advantage_idx + 1, expect_idx + 3, base_end)
        i = parse_start

        # Skip past advantages text if present
        if advantages and i < len(all_texts) and all_texts[i] == advantages:
            i += 1

        # Collect remaining items, classify them
        remaining = all_texts[i:] if i < len(all_texts) else []

        # Build work history: date pairs → company → role
        j = 0
        while j < len(remaining):
            t = remaining[j]
            # Detect work date pattern: "YYYY.MM" or "YYYY"
            is_date = _is_date(t)
            is_school = _is_school(t)
            is_company = _is_company(t)
            is_edu_detail = _is_edu_detail(t)

            if is_date and j + 2 < len(remaining):
                # Work entry: date → date → company → role
                next_t = remaining[j + 1]
                if _is_date(next_t) and j + 3 < len(remaining):
                    company = remaining[j + 2]
                    role = remaining[j + 3] if j + 3 < len(remaining) else ""
                    work_experiences.append(f"{t}~{next_t} {company} {role}")
                    j += 4
                    continue
                # Single date followed by company+role
                elif j + 2 < len(remaining):
                    company = remaining[j + 1]
                    role = remaining[j + 2] if j + 2 < len(remaining) else ""
                    work_experiences.append(f"{t} {company} {role}")
                    j += 3
                    continue

            if is_school or is_edu_detail:
                education_items.append(t)
                j += 1
                continue

            if is_company and j + 1 < len(remaining):
                role = remaining[j + 1]
                work_experiences.append(f"{t} {role}")
                j += 2
                continue

            # Short non-date non-company text → skill tag
            if len(t) <= 25 and not is_date and not is_school and not is_company:
                skill_tags.append(t)
            j += 1

        # Build enriched card dict
        cards.append({
            "card_index": card_idx,
            "geek_id": name,
            "name": name,
            "salary": salary,
            "active": active_text(all_texts),
            "base_info": " ".join(_dedupe(base_parts)),
            "expect_city": expect_city,
            "expect_position": expect_position,
            "advantages": advantages,
            "tags": skill_tags[:12],
            "work_experience": work_experiences[:5],
            "education": education_items[:5],
            "greet_btn_index": gi,
            # Combined text for city/industry keyword matching
            "_search_text": " ".join(all_texts),
        })

    return cards


# ── Card parsing helpers ─────────────────────────────────────────────

def active_text(texts: list[str]) -> str:
    for t in texts:
        if "活跃" in t or "在线" in t:
            return t
    return ""

def _is_date(t: str) -> bool:
    """Check if text looks like a date: '2024.09', '2023', '至今'"""
    if t == "至今":
        return True
    clean = t.replace(".", "").replace("-", "")
    if clean.isdigit() and len(clean) in (4, 6, 8):
        return True
    return False

def _is_school(t: str) -> bool:
    """Check if text looks like a school name."""
    return any(kw in t for kw in ("大学", "学院", "学校", "职业技术学院", "专科"))

def _is_company(t: str) -> bool:
    """Check if text looks like a company name (not a skill)."""
    return any(kw in t for kw in ("科技", "集团", "有限", "汽车", "技术", "信息"))

def _is_edu_detail(t: str) -> bool:
    """Check if text is an education detail."""
    return t in ("本科", "硕士", "博士", "大专", "中专", "高中") or \
           ("专业" in t and len(t) < 20) or \
           (any(kw in t for kw in ("工程", "管理", "设计", "制造")) and len(t) < 20)

def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ═════════════════════════════════════════════════════════════════════════
# Convenience wrappers
# ═════════════════════════════════════════════════════════════════════════

def find_button(name: str, process: str = BOSS_PROCESS_NAME) -> bool:
    """Check if a button with given name exists in the tree."""
    script = f'''
var se = Application("System Events");
var proc = se.processes["{process}"];
var win = proc.windows[0];
var all = win.entireContents();
for (var i = 0; i < all.length; i++) {{
    try {{
        var e = all[i];
        if (e.role() === "AXButton" && (e.name() || "") === "{name}") {{
            "found:" + (i + 1);
            break;
        }}
    }} catch(x) {{}}
}}
"not_found";
'''
    result = _run_jxa(script, timeout=30)
    return result.startswith("found:") if result else False


def is_dialog_visible() -> bool:
    """Check if '知道了' dialog is visible."""
    return find_button("知道了")


# ═════════════════════════════════════════════════════════════════════════
# Keyboard
# ═════════════════════════════════════════════════════════════════════════

def send_key_code(code: int) -> bool:
    script = f'Application("System Events").keyCode({code}); "ok"'
    return _run_jxa(script, timeout=5) == "ok"


def press_return() -> bool:
    return send_key_code(36)


def press_escape() -> bool:
    return send_key_code(53)


def press_page_down() -> bool:
    return send_key_code(121)


# ═════════════════════════════════════════════════════════════════════════
# App info
# ═════════════════════════════════════════════════════════════════════════

def is_app_running(process: str = BOSS_PROCESS_NAME) -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", process],
            capture_output=True, text=True, timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


def get_element_count(process: str = BOSS_PROCESS_NAME) -> int:
    script = f'''
var se = Application("System Events");
pro = se.processes["{process}"];
pro.windows[0].entireContents().length;
'''
    try:
        return int(_run_jxa(script, timeout=10))
    except (ValueError, TypeError):
        return 0
