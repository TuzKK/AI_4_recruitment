"""Resume download / collection logic.

Downloads resume attachments from Boss Zhipin chat and saves them locally.
Supports both web (Playwright Page) and macOS app (accessibility) modes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

RESUME_DIR = Path(__file__).parent.parent / "data" / "resumes"


async def collect_resume(
    device: Any,
    candidate_name: str,
    position_title: str,
) -> Optional[str]:
    """Check for and download a resume attachment from the current chat.

    Works with both:
    - Playwright Page (web mode): uses page.context.cookies() + httpx
    - macOS app (app mode): uses AX tree to detect attachments + screenshots

    Returns the local file path if successful, None otherwise.
    """
    # ── Detect mode ──
    is_playwright = False
    try:
        from playwright.async_api import Page
        if isinstance(device, Page):
            is_playwright = True
    except ImportError:
        pass

    if is_playwright:
        return await _collect_via_web(device, candidate_name, position_title)
    else:
        return await _collect_via_app(device, candidate_name, position_title)


async def _collect_via_web(page: Any, candidate_name: str, position_title: str) -> Optional[str]:
    """Download resume via Playwright browser context (original web approach)."""
    from rpa.page_actions import check_for_resume_attachment

    url = await check_for_resume_attachment(page)
    if not url:
        logger.info("No resume attachment found for %s", candidate_name)
        return None

    return await _download_file(url, page, candidate_name, position_title)


async def _collect_via_app(device: str, candidate_name: str, position_title: str) -> Optional[str]:
    """Check for resume in the macOS app via Accessibility API.

    In the app, resumes appear as file attachments in chat. We detect them
    via the AX tree and attempt to download them.
    """
    from rpa.mac_ax_actions import check_for_resume_attachment

    attachment = await check_for_resume_attachment(device)
    if not attachment:
        logger.info("No resume attachment found for %s", candidate_name)
        return None

    # For the app, we can't easily get the download URL or cookies.
    # Log the detection and create a placeholder.
    logger.info("Resume attachment detected: %s for %s (app mode - manual download needed)",
                attachment, candidate_name)

    # Create a placeholder file to indicate a resume was detected
    safe_position = position_title.replace(" ", "_").replace("/", "_")
    save_dir = RESUME_DIR / safe_position
    save_dir.mkdir(parents=True, exist_ok=True)
    safe_name = candidate_name.replace(" ", "_").replace("/", "_")
    filepath = save_dir / f"{safe_name}_detected.txt"

    filepath.write_text(
        f"Resume attachment detected: {attachment}\n"
        f"Candidate: {candidate_name}\n"
        f"Position: {position_title}\n"
        f"(Automatic download not yet supported in macOS app mode)\n"
    )

    return str(filepath)


async def _download_file(
    url: str,
    page: Any,
    candidate_name: str,
    position_title: str,
) -> Optional[str]:
    """Common download logic using browser cookies."""
    safe_position = position_title.replace(" ", "_").replace("/", "_")
    save_dir = RESUME_DIR / safe_position
    save_dir.mkdir(parents=True, exist_ok=True)

    safe_name = candidate_name.replace(" ", "_").replace("/", "_")
    ext = ".pdf"
    if ".doc" in url.lower():
        ext = ".docx"
    filename = f"{safe_name}{ext}"
    filepath = save_dir / filename

    try:
        cookies = await page.context.cookies()
        cookie_header = "; ".join(f"{c['name']}={c['value']}" for c in cookies)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                url if url.startswith("http") else f"https://www.zhipin.com{url}",
                headers={
                    "Cookie": cookie_header,
                    "Referer": "https://www.zhipin.com/",
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                },
                follow_redirects=True,
                timeout=30.0,
            )
            resp.raise_for_status()

        filepath.write_bytes(resp.content)
        logger.info("Resume downloaded: %s (%d bytes)", filepath, len(resp.content))
        return str(filepath)

    except Exception as e:
        logger.error("Failed to download resume for %s: %s", candidate_name, e)
        return None
