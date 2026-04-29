"""
Microsoft Career Portal Plugin
===============================

Scrapes job listings from Microsoft's eightfold.ai career portal.
Portal URL: https://microsoft.eightfold.ai/careers?domain=microsoft.com

This portal is publicly accessible — no authentication is required.
Jobs are sorted by timestamp (newest first) and dates are relative
("Posted X hours/days ago").
"""

from typing import Optional
from playwright.async_api import Page, BrowserContext

from portals.base import PortalBase
from models.job import Job

from . import login as login_module
from . import search as search_module
from . import scrape as scrape_module


class Portal(PortalBase):
    """Microsoft eightfold.ai career portal implementation."""

    async def login(self, page: Page, context: BrowserContext, credentials: Optional[dict] = None) -> bool:
        """Microsoft portal doesn't require login for browsing jobs."""
        return await login_module.login(page, context, credentials)

    async def is_logged_in(self, page: Page) -> bool:
        """Always returns True — no auth needed."""
        return await login_module.is_logged_in(page)

    async def search(self, page: Page, job_titles: list[str], filters: dict) -> None:
        """
        Search for jobs by title keywords.

        Builds URL-based searches and navigates to the first one.
        The orchestrator will call scrape() after each search.
        Returns the list of search URLs for the orchestrator to iterate over.
        """
        self._search_urls = await search_module.search(page, job_titles, self.portal_config, filters)
        # Navigate to the first search URL
        if self._search_urls:
            await search_module.navigate_to_search(
                page, self._search_urls[0], self.portal_config
            )

    async def scrape(self, page: Page, max_pages: int = 5) -> list[Job]:
        """Scrape job listings from all search URLs."""
        max_days = self.global_config.get("filters", {}).get("max_days_old", 7)
        all_jobs: list[Job] = []
        seen_ids: set[str] = set()

        urls = getattr(self, "_search_urls", [])
        if not urls:
            # If search wasn't called, use current page
            return await scrape_module.scrape(
                page, self.portal_config, max_pages, max_days
            )

        for i, url in enumerate(urls):
            if i > 0:
                # Navigate to subsequent search URLs
                await search_module.navigate_to_search(
                    page, url, self.portal_config
                )

            jobs = await scrape_module.scrape(
                page, self.portal_config, max_pages, max_days
            )

            # Deduplicate across search keywords
            for job in jobs:
                if job.job_id not in seen_ids:
                    seen_ids.add(job.job_id)
                    all_jobs.append(job)

        return all_jobs
