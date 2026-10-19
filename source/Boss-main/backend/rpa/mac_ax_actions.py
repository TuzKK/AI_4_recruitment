"""BOSS直聘 macOS app actions — via Accessibility (JXA backend).

Mirrors the interface of rpa/page_actions.py exactly.
Uses OS-level AX API — not detectable as automation (no JS injection,
no browser fingerprint modification, no DOM manipulation).

Anti-detection built into the access pattern:
  - Single full scan per batch → minimal interaction footprint
  - OS-level AXPress = identical to VoiceOver accessibility clicks
  - Random delays between all actions
  - No mouse movement simulation needed (AXPress is direct)
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import subprocess
import time
from typing import Any, Callable, Awaitable, Optional

from rpa.mac_ax_utils import (
    BOSS_PROCESS_NAME,
    _run_jxa,
    build_cards_from_scan,
    click_element_at_index,
    click_element_js,
    get_element_count,
    is_app_running,
    is_dialog_visible,
    press_escape,
    press_page_down,
    press_return,
    scan_tree,
    send_key_code,
)

logger = logging.getLogger(__name__)

BOSS_RECOMMEND_URL = "https://www.zhipin.com/web/chat/recommend"
BOSS_CHAT_URL = "https://www.zhipin.com/web/chat"

_notify_callback: Optional[Callable[[str, str], Awaitable[None]]] = None


def set_notify_callback(cb: Callable[[str, str], Awaitable[None]]) -> None:
    global _notify_callback
    _notify_callback = cb


async def _notify(event: str, message: str) -> None:
    if _notify_callback:
        try:
            await _notify_callback(event, message)
        except Exception:
            pass


# ═════════════════════════════════════════════════════════════════════════
# Anti-detection: human-like delay
# ═════════════════════════════════════════════════════════════════════════

async def human_delay(
    min_sec: float = 0.8,
    max_sec: float = 2.5,
    jitter: float = 0.3,
) -> None:
    """Human-like delay with natural variance. This is the single most
    important anti-detection measure — the primary detection vector for
    desktop apps is unnatural action timing.

    Args:
        min_sec: minimum delay
        max_sec: maximum delay
        jitter: random extra variance added to max
    """
    # Gaussian-like distribution: two uniform samples summed
    # creates a natural bell curve around the midpoint
    base = random.uniform(min_sec, max_sec)
    extra = random.uniform(0, jitter)
    # Occasionally take a longer pause (human gets distracted)
    if random.random() < 0.08:  # 8% chance of "thinking pause"
        extra += random.uniform(1.0, 4.0)
    await asyncio.sleep(base + extra)


# Re-export random_delay for orchestrator compatibility
async def random_delay(min_sec: float = 2.0, max_sec: float = 8.0) -> None:
    """Compatibility wrapper — used by orchestrator for batch pauses."""
    await asyncio.sleep(random.uniform(min_sec, max_sec))


# ═════════════════════════════════════════════════════════════════════════
# Navigation & Login
# ═════════════════════════════════════════════════════════════════════════

async def ensure_logged_in(device: str = BOSS_PROCESS_NAME) -> None:
    """Navigate to the recommend page (推荐牛人). Wait for login if needed."""
    logger.info("Navigating to recommend page...")

    if not is_app_running():
        raise RuntimeError("BOSS app is not running")

    # Click "推荐" nav link with human-like timing
    await human_delay(0.5, 1.5)
    clicked = click_element_js(description_contains="推荐", timeout=30)
    if not clicked:
        # Fallback: try clicking by name
        click_element_js(name="推荐", timeout=30)

    # Wait for page load
    await asyncio.sleep(random.uniform(3.0, 5.0))

    # Verify page loaded
    n = get_element_count()
    logger.info("Recommend page: %d elements", n)

    if n < 300:
        # Might be on login page — notify user
        await _notify("login_required", "请在 BOSS直聘 APP 中登录招聘者账号")
        logger.info("Waiting for user login...")
        for i in range(60):
            await asyncio.sleep(5)
            n = get_element_count()
            if n > 500:
                logger.info("Login detected! Page loaded (%d elements)", n)
                return
        raise RuntimeError("Login timed out")

    logger.info("Recommend page ready")


async def navigate_to_recommend(device: str = BOSS_PROCESS_NAME) -> None:
    await ensure_logged_in(device)


# ═════════════════════════════════════════════════════════════════════════
# Card Operations
# ═════════════════════════════════════════════════════════════════════════

# Global cache — scan once per batch, reuse indices for clicks
_scan_cache: Optional[dict[str, Any]] = None
_cards_cache: Optional[list[dict[str, Any]]] = None
_cache_time: float = 0
_CACHE_TTL: float = 60.0  # seconds — cards shift after scrolling/paging


async def get_candidate_cards(
    device: str = BOSS_PROCESS_NAME,
    force_refresh: bool = False,
) -> list[dict[str, Any]]:
    """Get candidate cards from the recommend page.

    First call does a full ~25s AX tree scan. Subsequent calls within
    CACHE_TTL return cached results. Set force_refresh=True to re-scan.

    Returns list of card dicts in page_actions.py format.
    """
    global _scan_cache, _cards_cache, _cache_time

    now = time.monotonic()
    if not force_refresh and _cards_cache and (now - _cache_time) < _CACHE_TTL:
        logger.debug("Returning cached cards (%d)", len(_cards_cache))
        return _cards_cache

    logger.info("AX tree scan — this takes ~25s but runs once per batch...")
    scan = scan_tree(timeout=90)

    if scan.get("total", 0) < 100:
        logger.warning("AX tree appears empty (total=%d)", scan.get("total", 0))
        return []

    cards = build_cards_from_scan(scan)
    logger.info("Scan complete: %d elements → %d cards with greet buttons",
                scan["total"], len(cards))

    _scan_cache = scan
    _cards_cache = cards
    _cache_time = now

    return cards


def invalidate_cache() -> None:
    """Invalidate the card cache (call after scrolling)."""
    global _scan_cache, _cards_cache, _cache_time
    _scan_cache = None
    _cards_cache = None
    _cache_time = 0


# ═════════════════════════════════════════════════════════════════════════
# Greet Actions
# ═════════════════════════════════════════════════════════════════════════

async def click_greet_button(
    device: str = BOSS_PROCESS_NAME,
    geek_id: str = "",
    greet_btn_index: Optional[int] = None,
) -> bool:
    """Click the '打招呼' button.

    Uses the cached index from get_candidate_cards() for near-instant clicks.
    Falls back to scanning the tree if no index provided.

    Anti-detection: adds pre+post click jitter to mimic human timing.
    """
    if greet_btn_index is not None:
        # Fast path — direct index click from cached card data
        await human_delay(0.3, 0.8)  # Pre-click micro-delay
        clicked = click_element_at_index(greet_btn_index)
        await human_delay(0.3, 0.6)  # Post-click settling time
    else:
        # Slow path — full scan
        logger.warning("No greet_btn_index — doing slow scan (avoid this)")
        clicked = click_element_js(name="打招呼", timeout=60)
        await human_delay(0.3, 0.6)

    if clicked:
        logger.info("Greeted: geek_id=%s", geek_id[:30] if geek_id else "unknown")
        return True

    # Retry with progressively longer delays (avoids retry-storm detection)
    for attempt in range(4):
        wait = 1.5 + attempt * 1.3 + random.uniform(0, 2)
        await asyncio.sleep(wait)
        if greet_btn_index:
            if click_element_at_index(greet_btn_index):
                logger.info("Greeted on retry %d", attempt + 1)
                return True

    logger.warning("Failed to greet geek_id=%s after retries", geek_id[:30] if geek_id else "unknown")
    return False


async def dismiss_greet_dialog(device: str = BOSS_PROCESS_NAME) -> bool:
    """Dismiss the post-greet notification dialog.

    Uses Escape key ONLY — no AX tree access needed.
    This is the only reliable approach because modal dialogs cause
    both AppleScript and JXA entireContents() to hang indefinitely.
    Escape key bypasses the AX tree entirely.
    """
    await asyncio.sleep(random.uniform(0.5, 1.0))

    for attempt in range(5):
        # Escape key — instant, no AX scan needed, never hangs
        subprocess.run(
            ['osascript', '-e', 'tell application "System Events" to key code 53'],
            capture_output=True, timeout=5,
        )
        await asyncio.sleep(random.uniform(0.4, 0.8))

    logger.info("Dialog dismissed via Escape key")
    return True


# ═════════════════════════════════════════════════════════════════════════
# Scroll
# ═════════════════════════════════════════════════════════════════════════

async def scroll_to_load_more(device: str = BOSS_PROCESS_NAME) -> None:
    """Scroll down to load more candidate cards.

    Uses Page Down key codes with natural variation in count and timing.
    Card cache is invalidated since positions shift after scrolling.
    """
    # Randomize scroll amount (2-5 Page Downs)
    n_scrolls = random.randint(2, 5)
    for _ in range(n_scrolls):
        press_page_down()
        await asyncio.sleep(random.uniform(0.3, 0.7))

    # Wait for content to load
    await asyncio.sleep(random.uniform(2.0, 4.0))

    # Invalidate cache — cards have new positions
    invalidate_cache()


# ═════════════════════════════════════════════════════════════════════════
# Chat Helpers
# ═════════════════════════════════════════════════════════════════════════

async def navigate_to_chat(device: str = BOSS_PROCESS_NAME) -> None:
    """Navigate to the messages page."""
    logger.info("Navigating to chat...")
    await human_delay(0.5, 1.0)
    click_element_js(description_contains="消息", timeout=20)
    await asyncio.sleep(random.uniform(2.0, 3.0))
    # Fallback
    if get_element_count() < 50:
        click_element_js(description_contains="意向沟通", timeout=20)
        await asyncio.sleep(random.uniform(1.5, 2.5))


async def get_unread_messages(
    device: str = BOSS_PROCESS_NAME,
) -> list[dict[str, Any]]:
    """Get unread conversations from the message list."""
    return []  # Stub


async def send_chat_message(
    device: str = BOSS_PROCESS_NAME,
    message: str = "",
) -> bool:
    """Send a chat message — paste via clipboard + press Enter."""
    if not message:
        return False

    logger.info("Sending chat message (%d chars)", len(message))

    # Paste message via clipboard (Cmd+V)
    subprocess.run(
        ["osascript", "-e", f'set the clipboard to "{message}"'],
        capture_output=True, timeout=5,
    )
    await human_delay(0.2, 0.5)
    _run_jxa('''
    var se = Application("System Events");
    se.keystroke("v", {using: "command down"});
    ''', timeout=5)

    await human_delay(0.5, 1.0)

    # Send: try "发送" button, fallback to Enter
    if not click_element_js(name="发送", timeout=15):
        press_return()

    await asyncio.sleep(random.uniform(0.5, 1.0))
    return True


async def check_for_resume_attachment(
    device: str = BOSS_PROCESS_NAME,
) -> Optional[str]:
    """Check for resume/file attachment in chat."""
    for text in ("简历", "附件", "文件"):
        script = f'''
var se = Application("System Events");
var proc = se.processes["{BOSS_PROCESS_NAME}"];
var win = proc.windows[0];
var all = win.entireContents();
for (var i = 0; i < all.length; i++) {{
    try {{
        var n = all[i].name() || "";
        if (n.indexOf("{text}") >= 0) {{
            "found:" + i;
            break;
        }}
    }} catch(x) {{}}
}}
"none";
'''
        result = _run_jxa(script, timeout=30)
        if result and result.startswith("found:"):
            return text
    return None


async def get_candidate_profile(
    device: str = BOSS_PROCESS_NAME,
) -> dict[str, Any]:
    cards = await get_candidate_cards(device)
    return cards[0] if cards else {}
