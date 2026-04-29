import re
import logging
from datetime import datetime

from playwright.async_api import Page

from models.job import Job
from core.date_parser import parse_relative_date, is_within_days

logger = logging.getLogger(__name__)

# Default selectors (based on live DOM inspection of eightfold.ai)
DEFAULT_SELECTORS = {
    "job_card": "a[id^='job-card-']",
    "next_button": "button[aria-label='Next jobs']",
    "job_title_attribute": "aria-label",
    "job_title_prefix": "View job: ",
    "job_id_regex": r"job-card-(\d+)-job-list",
}

BASE_URL = "https://microsoft.eightfold.ai"


async def scrape(
    page: Page,
    config: dict,
    max_pages: int = 5,
    max_days_old: int = 7,
) -> list[Job]:
    """
    Extract job listings from the Microsoft eightfold.ai portal.

    Scrapes all visible job cards on the current page, then paginates
    through additional pages up to `max_pages`. Stops early if jobs
    become older than `max_days_old`.

    Args:
        page: Playwright page (should already be on a search results page).
        config: Portal-specific configuration dict.
        max_pages: Maximum number of pages to scrape.
        max_days_old: Stop scraping when jobs are older than this many days.

    Returns:
        List of Job objects extracted from the portal.
    """
    selectors = {**DEFAULT_SELECTORS, **(config.get("selectors", {}))}
    portal_name = config.get("name", "Microsoft")
    all_jobs: list[Job] = []
    seen_ids: set[str] = set()

    for page_num in range(1, max_pages + 1):
        logger.info(f"Scraping page {page_num}...")

        # Wait for any loading skeletons to disappear
        await _wait_for_cards_loaded(page)

        jobs_on_page = await _extract_jobs_from_page(page, selectors, portal_name)

        if not jobs_on_page:
            logger.info(f"No jobs found on page {page_num}. Stopping pagination.")
            break

        # Check for duplicates within this run (cross-page)
        new_jobs = []
        for job in jobs_on_page:
            if job.job_id not in seen_ids:
                seen_ids.add(job.job_id)
                new_jobs.append(job)

        if not new_jobs:
            logger.info(f"All jobs on page {page_num} are duplicates. Stopping.")
            break

        # Check if we've hit jobs that are too old
        recent_jobs = [j for j in new_jobs if is_within_days(j.posted_date, max_days_old)]
        all_jobs.extend(recent_jobs)

        if len(recent_jobs) < len(new_jobs):
            logger.info(
                f"Found {len(new_jobs) - len(recent_jobs)} jobs older than "
                f"{max_days_old} days. Stopping pagination."
            )
            break

        # Try to go to next page
        if page_num < max_pages:
            has_next = await _go_to_next_page(page, selectors)
            if not has_next:
                logger.info("No more pages available.")
                break

    logger.info(f"Total jobs scraped from {portal_name}: {len(all_jobs)}")
    return all_jobs


async def _wait_for_cards_loaded(page: Page, timeout: int = 10000):
    """Wait for any loading skeleton cards to disappear."""
    try:
        # Wait for skeleton/loading elements to disappear
        await page.wait_for_function(
            """() => {
                const skeletons = document.querySelectorAll('[class*="skeleton"], [class*="loading"]');
                return skeletons.length === 0;
            }""",
            timeout=timeout,
        )
    except Exception:
        # Not critical — just continue even if skeletons persist
        pass

    # Small additional wait to ensure DOM is stable
    await page.wait_for_timeout(500)


async def _extract_jobs_from_page(
    page: Page,
    selectors: dict,
    portal_name: str,
) -> list[Job]:
    """Extract all job cards from the current page."""
    card_selector = selectors["job_card"]
    title_attr = selectors.get("job_title_attribute", "aria-label")
    title_prefix = selectors.get("job_title_prefix", "View job: ")
    id_regex = selectors.get("job_id_regex", r"job-card-(\d+)-job-list")

    cards = await page.query_selector_all(card_selector)
    logger.info(f"Found {len(cards)} job cards on current page")

    jobs = []
    for card in cards:
        try:
            # Extract job ID from the card's id attribute
            card_id = await card.get_attribute("id") or ""
            id_match = re.search(id_regex, card_id)
            if not id_match:
                logger.debug(f"Could not extract job ID from: {card_id}")
                continue
            job_id = id_match.group(1)

            # Extract title from aria-label
            aria_label = await card.get_attribute(title_attr) or ""
            title = aria_label.replace(title_prefix, "").strip() if title_prefix in aria_label else aria_label
            if not title:
                # Fallback: get text from first nested div
                title_el = await card.query_selector("div > div:first-child > div")
                title = (await title_el.inner_text()).strip() if title_el else "Unknown"

            # Extract URL
            href = await card.get_attribute("href") or ""
            url = f"{BASE_URL}{href}" if href.startswith("/") else href

            # Extract location and posted date from the card's full text.
            # The card's inner_text() gives lines like:
            #   "Senior Software Engineer - Xbox Video"
            #   "United States, Multiple Locations"
            #   "Posted 13 hours ago"
            location = ""
            posted_date = None
            try:
                full_text = (await card.inner_text()).strip()
                lines = [l.strip() for l in full_text.split("\n") if l.strip()]

                # The last line is typically "Posted X ago"
                # The middle line(s) contain the location
                # The first line is the title (already extracted via aria-label)
                for line in lines:
                    if line.lower().startswith("posted"):
                        posted_date = parse_relative_date(line)
                    elif line != title and not line.lower().startswith("posted"):
                        location = line  # Last non-title, non-date line is location
            except Exception as e:
                logger.debug(f"Text extraction error: {e}")

            job = Job(
                portal_name=portal_name,
                job_id=job_id,
                title=title,
                url=url,
                location=location,
                posted_date=posted_date,
            )
            jobs.append(job)
            logger.debug(f"Extracted: {job}")

        except Exception as e:
            logger.warning(f"Failed to extract job card: {e}")
            continue

    return jobs


async def _go_to_next_page(page: Page, selectors: dict) -> bool:
    """
    Click the 'Next' pagination button.

    Returns True if successfully navigated to next page, False if
    no next button exists or it's disabled.
    """
    next_selector = selectors.get("next_button", "button[aria-label='Next jobs']")

    try:
        next_btn = page.locator(next_selector)

        if not await next_btn.is_visible():
            return False

        is_disabled = await next_btn.get_attribute("disabled")
        if is_disabled is not None:
            return False

        # Remember current first card ID to detect when page changes
        first_card = await page.query_selector(selectors.get("job_card", "a[id^='job-card-']"))
        old_first_id = await first_card.get_attribute("id") if first_card else None

        await next_btn.click()

        # Wait for the page to actually change — detect new cards replacing old ones
        try:
            await page.wait_for_function(
                f"""(oldId) => {{
                    const cards = document.querySelectorAll("a[id^='job-card-']");
                    if (cards.length === 0) return false;
                    return cards[0].id !== oldId;
                }}""",
                arg=old_first_id,
                timeout=10000,
            )
        except Exception:
            # Fallback: just wait a bit
            await page.wait_for_timeout(3000)

        return True

    except Exception as e:
        logger.debug(f"Could not navigate to next page: {e}")
        return False
