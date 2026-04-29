import logging
from typing import Optional

from playwright.async_api import Page, BrowserContext

logger = logging.getLogger(__name__)


async def login(page: Page, context: BrowserContext, credentials: Optional[dict] = None) -> bool:
    """
    Handle Microsoft portal authentication.

    Microsoft's eightfold.ai career portal is publicly accessible —
    no login is required to browse and scrape job listings.

    If future authentication is needed (e.g., for personalized
    recommendations or saved jobs), this module can be extended
    to handle Google OAuth, Microsoft SSO, etc.

    Args:
        page: The Playwright page object.
        context: The browser context.
        credentials: Not used for Microsoft portal.

    Returns:
        True (always — no auth needed).
    """
    logger.info("Microsoft portal does not require authentication. Skipping login.")
    return True


async def is_logged_in(page: Page) -> bool:
    """
    Check if the user is logged in to the Microsoft portal.

    Since auth is not required, this always returns True.
    """
    return True


async def setup_auth(page: Page, context: BrowserContext, auth_dir: str = "auth"):
    """
    Interactive auth setup for Microsoft portal.

    Opens the portal in a headed browser and waits for the user
    to complete Google OAuth login manually. Saves the session
    state for future use.

    This is optional — only needed if you want personalized features.
    """
    logger.info("Opening Microsoft portal for manual login...")
    await page.goto("https://microsoft.eightfold.ai/careers?domain=microsoft.com")

    # Click "Sign in" button
    sign_in = page.locator("text=Sign in")
    if await sign_in.is_visible():
        await sign_in.click()
        logger.info("Sign-in modal opened. Please complete login in the browser...")
        logger.info("Waiting up to 120 seconds for login to complete...")

        # Wait for the modal to close (indicates successful login)
        try:
            await page.wait_for_selector("text=Sign in", state="hidden", timeout=120000)
            logger.info("Login completed successfully!")

            # Save session state
            from pathlib import Path
            state_path = Path(auth_dir) / "microsoft_state.json"
            state_path.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(state_path))
            logger.info(f"Session saved to {state_path}")
        except Exception as e:
            logger.warning(f"Login was not completed within timeout: {e}")
    else:
        logger.info("Already logged in or Sign in button not found.")
