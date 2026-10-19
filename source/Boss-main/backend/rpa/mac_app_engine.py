"""macOS BOSS直聘 App Engine.

Launches the BOSS直聘 Electron desktop app with accessibility enabled,
waits for it to be ready, and manages its lifecycle.

Replaces browser_engine.py — same interface, different target.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import subprocess
import time
from typing import Optional

from rpa.mac_ax_utils import (
    BOSS_PROCESS_NAME,
    get_element_count,
    is_app_running,
    press_return,
    send_key_code,
)

logger = logging.getLogger(__name__)

BOSS_EXECUTABLE = "/Applications/BOSS直聘.app/Contents/MacOS/BOSS直聘"


class MacAppEngine:
    """Manages the lifecycle of the BOSS直聘 macOS app.

    Usage:
        engine = MacAppEngine()
        device = await engine.launch()  # returns process name string
        await engine.close()
    """

    def __init__(self) -> None:
        self._proc: Optional[subprocess.Popen] = None  # type: ignore[type-arg]
        self._ready = False

    async def launch(self) -> str:
        """Launch BOSS直聘 and wait for it to be ready.

        Returns the process name used as 'device' identifier.
        """
        # Kill any existing instance
        if is_app_running():
            logger.info("BOSS app already running, killing first...")
            self._kill_existing()
            await asyncio.sleep(2)

        logger.info("Launching BOSS直聘 with accessibility enabled...")
        self._proc = subprocess.Popen(
            [BOSS_EXECUTABLE, "--force-renderer-accessibility"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )

        await self._wait_until_ready(timeout=120)
        self._ready = True
        logger.info("BOSS直聘 app ready")
        return BOSS_PROCESS_NAME

    async def _wait_until_ready(self, timeout: float = 120.0) -> None:
        """Wait for the app to be fully loaded with AX tree populated."""
        start = time.monotonic()

        # Step 1: Wait for process
        while time.monotonic() - start < timeout:
            if is_app_running():
                break
            await asyncio.sleep(1)
        else:
            raise RuntimeError("BOSS app did not start")

        # Step 2: Wait for AX tree to grow (webview loads)
        # Window appears quickly but content loads over 10-30s
        logger.info("Waiting for webview content to load...")
        min_elements = 200
        while time.monotonic() - start < timeout:
            try:
                n = get_element_count()
                if n > min_elements:
                    logger.info("AX tree populated: %d elements", n)
                    return
            except Exception:
                pass
            await asyncio.sleep(3)

        # If timeout with partial content, log a warning but continue
        try:
            n = get_element_count()
            logger.warning("AX tree partial: %d elements after %.0fs", n, timeout)
        except Exception:
            raise RuntimeError("BOSS app AX tree not accessible")

    def _count_elements(self) -> int:
        try:
            return get_element_count()
        except Exception:
            return -1

    def _kill_existing(self) -> None:
        for name in ("BOSS直聘", "boss-zhipin-daemon"):
            try:
                subprocess.run(
                    ["pkill", "-9", "-f", name],
                    capture_output=True, timeout=10,
                )
            except Exception:
                pass

    async def close(self) -> None:
        if not self._ready and self._proc is None:
            return
        logger.info("Shutting down BOSS app...")
        if self._proc and self._proc.pid:
            try:
                os.killpg(os.getpgid(self._proc.pid), signal.SIGTERM)
                self._proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                try:
                    os.killpg(os.getpgid(self._proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self._kill_existing()
        self._ready = False
        logger.info("BOSS app shut down")

    @property
    def is_ready(self) -> bool:
        return self._ready
