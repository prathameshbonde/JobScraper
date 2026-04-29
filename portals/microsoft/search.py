import logging
from urllib.parse import quote_plus

from playwright.async_api import Page

logger = logging.getLogger(__name__)

# Default search URL template
SEARCH_URL_TEMPLATE = (
    "https://microsoft.eightfold.ai/careers"
    "?domain=microsoft.com"
    "&query={query}"
    "&sort_by=timestamp"
)


async def search(page: Page, job_titles: list[str], config: dict, filters: dict) -> list[str]:
    """
    Build search URLs for each job title keyword and return them.

    Microsoft's eightfold.ai portal supports direct URL-based searching,
    so we don't need to interact with the search input — we just navigate
    to the pre-built URL.

    Args:
        page: The Playwright page object.
        job_titles: List of job title keywords to search for.
        config: Portal-specific configuration dict.
        filters: Global filters dict (containing location).

    Returns:
        List of search URLs to scrape (one per job title keyword).
    """
    template = config.get("search_url_template", SEARCH_URL_TEMPLATE)
    location = filters.get("location", "")

    search_urls = []
    for title in job_titles:
        url = template.replace("{query}", quote_plus(title))
        url = url.replace("{location}", quote_plus(location))
        search_urls.append(url)
        logger.info(f"Prepared search URL for '{title}' in '{location}': {url}")

    return search_urls


async def navigate_to_search(page: Page, url: str, config: dict):
    """
    Navigate to a search URL and wait for job cards to load.

    Args:
        page: The Playwright page object.
        url: The search URL to navigate to.
        config: Portal-specific configuration dict.
    """
    selectors = config.get("selectors", {})
    job_card_selector = selectors.get("job_card", "a[class*='card-'][id^='job-card-']")

    logger.info(f"Navigating to: {url}")
    await page.goto(url, wait_until="domcontentloaded")

    # Wait for job cards to appear (or timeout gracefully)
    try:
        await page.wait_for_selector(job_card_selector, timeout=15000)
        logger.info("Job cards loaded successfully")
    except Exception:
        logger.warning("No job cards found on this page (may have 0 results)")
