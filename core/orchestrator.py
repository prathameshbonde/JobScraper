import logging
from datetime import datetime

from core.browser import BrowserManager
from core.date_parser import is_within_days
from portals.loader import load_portal
from storage.db import JobDatabase
from notifier.email_sender import EmailSender
from models.job import Job

logger = logging.getLogger(__name__)


async def run_scrape(config: dict, dry_run: bool = False, headful: bool = False):
    """
    Main orchestration function that runs a full scrape cycle.

    1. Loads each enabled portal plugin
    2. Launches browser and creates per-portal contexts
    3. Authenticates (if needed)
    4. Searches and scrapes jobs
    5. Filters by date and title keywords
    6. Deduplicates against SQLite DB
    7. Sends email with new jobs (unless dry_run)

    Args:
        config: The full global configuration dict.
        dry_run: If True, scrape but don't send email (print results instead).
        headful: If True, override headless setting to show the browser.
    """
    general = config.get("general", {})
    filters = config.get("filters", {})
    portal_configs = config.get("portals", [])
    email_config = config.get("email", {})

    headless = not headful and general.get("headless", True)
    timeout = general.get("timeout", 30000)
    db_path = general.get("db_path", "jobs.db")
    max_days = filters.get("max_days_old", 7)
    job_titles = filters.get("job_titles", [])

    if not portal_configs:
        logger.error("No portals configured. Add portals to config.yaml.")
        return

    if not job_titles:
        logger.warning("No job titles configured. Will scrape all available jobs.")

    # Initialize database
    db = JobDatabase(db_path)
    db.connect()

    # Initialize browser
    browser = BrowserManager(headless=headless, timeout=timeout)
    await browser.start()

    all_new_jobs: list[Job] = []

    try:
        for portal_cfg in portal_configs:
            portal_name = portal_cfg.get("name", "unknown")
            enabled = portal_cfg.get("enabled", True)

            if not enabled:
                logger.info(f"Skipping disabled portal: {portal_name}")
                continue

            logger.info(f"\n{'='*60}")
            logger.info(f"Scraping portal: {portal_name}")
            logger.info(f"{'='*60}")

            try:
                # Load portal plugin
                portal = load_portal(portal_name, portal_cfg, config)

                # Create browser context with saved session
                context = await browser.get_context(portal_name)
                page = await context.new_page()

                # Authenticate if needed
                if portal.requires_auth():
                    logger.info(f"Portal '{portal_name}' requires auth. Checking session...")
                    if not await portal.is_logged_in(page):
                        logger.info("Not logged in. Attempting login...")
                        success = await portal.login(page, context)
                        if not success:
                            logger.error(f"Login failed for '{portal_name}'. Skipping.")
                            await context.close()
                            continue
                        # Save session after successful login
                        await browser.save_session(context, portal_name)
                else:
                    logger.info(f"Portal '{portal_name}' does not require auth.")

                # Search for jobs
                pagination = portal_cfg.get("pagination") or {}
                max_pages = pagination.get("max_pages", 5) if isinstance(pagination, dict) else 5

                await portal.search(page, job_titles, filters)

                # Scrape jobs
                scraped_jobs = await portal.scrape(page, max_pages=max_pages)
                logger.info(f"Scraped {len(scraped_jobs)} jobs from '{portal_name}'")

                # Filter by job title keywords (case-insensitive partial match)
                if job_titles:
                    title_filtered = [
                        job for job in scraped_jobs
                        if any(
                            keyword.lower() in job.title.lower()
                            for keyword in job_titles
                        )
                    ]
                    logger.info(
                        f"After title filtering: {len(title_filtered)} jobs "
                        f"(from {len(scraped_jobs)} scraped)"
                    )
                    scraped_jobs = title_filtered

                # Deduplicate against database
                new_jobs = db.filter_unseen(scraped_jobs)
                logger.info(
                    f"New jobs (not previously seen): {len(new_jobs)} "
                    f"(out of {len(scraped_jobs)} filtered)"
                )

                # Mark new jobs as seen
                if new_jobs:
                    db.mark_seen_batch(new_jobs)

                all_new_jobs.extend(new_jobs)

                # Cleanup
                await context.close()

            except Exception as e:
                logger.error(f"Error scraping portal '{portal_name}': {e}", exc_info=True)
                continue

    finally:
        await browser.stop()
        db_stats = db.get_stats()
        db.close()

    # Summary
    logger.info(f"\n{'='*60}")
    logger.info(f"SCRAPE COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total new jobs found: {len(all_new_jobs)}")
    logger.info(f"Database stats: {db_stats}")

    if dry_run:
        logger.info("\n[DRY RUN] Jobs that would be emailed:")
        for job in all_new_jobs:
            logger.info(f"  → {job}")
        return all_new_jobs

    # Send email notification
    if all_new_jobs or email_config.get("send_empty_report", False):
        try:
            emailer = EmailSender(email_config)
            emailer.send_jobs(all_new_jobs)
        except Exception as e:
            logger.error(f"Failed to send email: {e}", exc_info=True)
    else:
        logger.info("No new jobs to report. Skipping email.")

    return all_new_jobs
