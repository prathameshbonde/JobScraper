from abc import ABC, abstractmethod
from typing import Optional
from playwright.async_api import Page, BrowserContext

from models.job import Job


class PortalBase(ABC):
    """
    Abstract base class for career portal plugins.

    Each portal implements its own login, search, and scrape logic
    in separate methods, allowing completely different page structures
    and authentication flows per portal.
    """

    def __init__(self, name: str, portal_config: dict, global_config: dict):
        self.name = name
        self.portal_config = portal_config
        self.global_config = global_config

    @abstractmethod
    async def login(self, page: Page, context: BrowserContext, credentials: Optional[dict] = None) -> bool:
        """
        Handle portal-specific authentication.

        Args:
            page: The Playwright page object.
            context: The browser context (for saving session state).
            credentials: Optional dict with 'username' and 'password' keys.

        Returns:
            True if login was successful or not needed, False otherwise.
        """
        pass

    @abstractmethod
    async def is_logged_in(self, page: Page) -> bool:
        """
        Check if the current session is authenticated.

        Args:
            page: The Playwright page object (should be on the portal).

        Returns:
            True if the user is logged in.
        """
        pass

    @abstractmethod
    async def search(self, page: Page, job_titles: list[str], filters: dict) -> None:
        """
        Navigate to job listings and apply search filters.

        This method should leave the page in a state where job cards
        are visible and ready to be scraped.

        Args:
            page: The Playwright page object.
            job_titles: List of job title keywords to search for.
            filters: Additional filter settings from config.
        """
        pass

    @abstractmethod
    async def scrape(self, page: Page, max_pages: int = 5) -> list[Job]:
        """
        Extract job listings from the current page, handling pagination.

        Args:
            page: The Playwright page object (should be on job listings).
            max_pages: Maximum number of pages to scrape.

        Returns:
            List of Job objects extracted from the portal.
        """
        pass

    def requires_auth(self) -> bool:
        """Check if this portal requires authentication based on config."""
        auth_config = self.portal_config.get("auth", {})
        if not auth_config:
            return False
        auth_type = auth_config.get("type", "none")
        return auth_type != "none"
