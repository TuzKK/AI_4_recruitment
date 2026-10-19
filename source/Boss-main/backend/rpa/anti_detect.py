"""Anti-detection middleware.

Applies stealth patches to make the Playwright-controlled browser
indistinguishable from a regular Chrome instance.
"""

from __future__ import annotations

import logging

from playwright.async_api import BrowserContext, Page

logger = logging.getLogger(__name__)

# JavaScript snippets to mask automation fingerprints
_STEALTH_SCRIPTS = [
    # Override navigator.webdriver — critical for Boss Zhipin
    """
    Object.defineProperty(navigator, 'webdriver', {
        get: () => false,
    });
    """,
    # Hide automation-related properties
    """
    window.chrome = { runtime: {} };
    """,
    # Override permissions query
    """
    const originalQuery = window.navigator.permissions.query;
    window.navigator.permissions.query = (parameters) =>
        parameters.name === 'notifications'
            ? Promise.resolve({ state: Notification.permission })
            : originalQuery(parameters);
    """,
    # Mask the plugins array (headless Chrome has empty plugins)
    """
    Object.defineProperty(navigator, 'plugins', {
        get: () => [1, 2, 3, 4, 5],
    });
    """,
    # Override languages
    """
    Object.defineProperty(navigator, 'languages', {
        get: () => ['zh-CN', 'zh', 'en-US', 'en'],
    });
    """,
    # Hide CDP runtime
    """
    if (window.__playwright) { delete window.__playwright; }
    if (window.__pw_manual) { delete window.__pw_manual; }
    if (window.__PW_inspect) { delete window.__PW_inspect; }
    """,
]


async def apply_stealth(context: BrowserContext) -> None:
    """Inject stealth scripts into every new page in the context."""
    for script in _STEALTH_SCRIPTS:
        await context.add_init_script(script)

    # Also try playwright_stealth if available
    try:
        import playwright_stealth
        await playwright_stealth.stealth_sync(context)
        logger.info("playwright_stealth applied")
    except Exception as e:
        logger.debug("playwright_stealth not applied: %s", e)

    logger.info("Stealth patches applied to browser context")


async def apply_stealth_to_page(page: Page) -> None:
    """Apply stealth patches to a single existing page."""
    for script in _STEALTH_SCRIPTS:
        await page.evaluate(script)
