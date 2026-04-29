import os
import logging
from pathlib import Path
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Manages Playwright browser lifecycle.
    Handles launching, creating contexts with saved sessions, and cleanup.
    """

    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def start(self):
        """Launch the Playwright browser."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        logger.info(f"Browser launched (headless={self.headless})")

    async def get_context(
        self,
        portal_name: str,
        auth_dir: str = "auth",
    ) -> BrowserContext:
        """
        Create a browser context for a portal.
        Loads saved session state if available.
        """
        if not self._browser:
            raise RuntimeError("Browser not started. Call start() first.")

        state_path = Path(auth_dir) / f"{portal_name}_state.json"

        context_options = {
            "viewport": {"width": 1920, "height": 1080},
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }

        # Load saved session state if it exists
        if state_path.exists():
            context_options["storage_state"] = str(state_path)
            logger.info(f"Loading saved session for '{portal_name}' from {state_path}")
        else:
            logger.info(f"No saved session found for '{portal_name}', starting fresh")

        context = await self._browser.new_context(**context_options)
        context.set_default_timeout(self.timeout)

        return context

    async def save_session(
        self,
        context: BrowserContext,
        portal_name: str,
        auth_dir: str = "auth",
    ):
        """Save the current browser context's session state to disk."""
        state_path = Path(auth_dir) / f"{portal_name}_state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(state_path))
        logger.info(f"Session saved for '{portal_name}' at {state_path}")

    async def stop(self):
        """Close the browser and cleanup Playwright."""
        if self._browser:
            await self._browser.close()
            logger.info("Browser closed")
        if self._playwright:
            await self._playwright.stop()
            logger.info("Playwright stopped")
