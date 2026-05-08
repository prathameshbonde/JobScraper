"""
JobScraper — Daily Career Portal Job Scraper
=============================================

Automates daily scraping of career portals, deduplicates results,
and sends email notifications with new job listings.

Usage:
    python main.py --run-now              Run a single scrape cycle
    python main.py --run-now --headful    Run with visible browser (for debugging)
    python main.py --run-now --dry-run    Scrape but don't send email
    python main.py --test-email           Send a test email to verify SMTP config
    python main.py --setup-auth <portal>  Open browser for manual OAuth login
    python main.py --scheduler            Start APScheduler for continuous mode
    python main.py --list-portals         List available portal plugins
    python main.py --reset-db             Clear the database of all scraped jobs
"""

import sys
import os
import asyncio
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path

import yaml
from dotenv import load_dotenv

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from core.orchestrator import run_scrape
from core.browser import BrowserManager
from notifier.email_sender import EmailSender
from portals.loader import list_available_portals


def setup_logging(level: str = "INFO"):
    """Configure logging with console and file output."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # File handler (rotating by date would be nice, but keep it simple)
    log_file = log_dir / f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file


def cleanup_old_logs(days: int = 5):
    """Delete old scrape log files that are older than the given number of days."""
    log_dir = Path("logs")
    if not log_dir.exists():
        return

    cutoff = datetime.now() - timedelta(days=days)
    logger = logging.getLogger(__name__)
    logger.info(f"Cleaning up log files older than {days} days...")

    for path in log_dir.glob("scrape_*.log"):
        try:
            if path.is_file():
                try:
                    # Extract datetime from filename (scrape_YYYYMMDD_HHMMSS.log)
                    date_str = path.stem.replace("scrape_", "")
                    log_date = datetime.strptime(date_str, "%Y%m%d_%H%M%S")
                except ValueError:
                    # Fallback to modification time
                    log_date = datetime.fromtimestamp(path.stat().st_mtime)

                if log_date < cutoff:
                    path.unlink()
                    logger.info(f"Deleted old log file: {path.name}")
        except Exception as e:
            logger.warning(f"Could not delete old log file '{path.name}': {e}")


def load_config(config_path: str = "config.yaml") -> dict:
    """Load the global configuration file."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Configuration file not found: {config_path}")
        print("Create a config.yaml file (see config.yaml.example or README.md)")
        sys.exit(1)

    with open(path, "r") as f:
        config = yaml.safe_load(f)

    return config


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="JobScraper — Daily Career Portal Job Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Run modes
    mode_group = parser.add_argument_group("Run Modes")
    mode_group.add_argument(
        "--run-now",
        action="store_true",
        help="Execute a single scrape run immediately",
    )
    mode_group.add_argument(
        "--scheduler",
        action="store_true",
        help="Start APScheduler for continuous daily runs",
    )
    mode_group.add_argument(
        "--test-email",
        action="store_true",
        help="Send a test email to verify SMTP configuration",
    )
    mode_group.add_argument(
        "--setup-auth",
        type=str,
        metavar="PORTAL",
        help="Open headed browser for manual login to a portal",
    )
    mode_group.add_argument(
        "--reset-db",
        action="store_true",
        help="Clear the database of all scraped job records",
    )
    mode_group.add_argument(
        "--list-portals",
        action="store_true",
        help="List all available portal plugins",
    )

    # Options
    options_group = parser.add_argument_group("Options")
    options_group.add_argument(
        "--dry-run",
        action="store_true",
        help="Scrape but don't send email (print results only)",
    )
    options_group.add_argument(
        "--headful",
        action="store_true",
        help="Run with visible browser window (overrides config)",
    )
    options_group.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)",
    )

    return parser.parse_args()


async def cmd_run_now(config: dict, dry_run: bool, headful: bool):
    """Execute a single scrape run."""
    logger = logging.getLogger(__name__)
    logger.info("Starting scrape run...")
    cleanup_old_logs()

    jobs = await run_scrape(config, dry_run=dry_run, headful=headful)

    if jobs:
        logger.info(f"\nFound {len(jobs)} new jobs:")
        for job in jobs:
            logger.info(f"  → {job}")
    else:
        logger.info("\nNo new jobs found.")


def cmd_test_email(config: dict):
    """Send a test email."""
    logger = logging.getLogger(__name__)
    email_config = config.get("email", {})

    if not email_config:
        logger.error("No email configuration found in config.yaml")
        return

    emailer = EmailSender(email_config)
    emailer.send_test()
    logger.info("Test email sent! Check your inbox.")


async def cmd_setup_auth(config: dict, portal_name: str):
    """Open a headed browser for manual portal authentication."""
    logger = logging.getLogger(__name__)
    logger.info(f"Setting up authentication for portal: {portal_name}")

    browser = BrowserManager(headless=False, timeout=120000)
    await browser.start()

    context = await browser.get_context(portal_name)
    page = await context.new_page()

    try:
        # Dynamically import the portal's login module
        import importlib

        login_module = importlib.import_module(f"portals.{portal_name}.login")
        if hasattr(login_module, "setup_auth"):
            await login_module.setup_auth(page, context, auth_dir="auth")
        else:
            logger.error(
                f"Portal '{portal_name}' does not have a setup_auth function."
            )
    except ModuleNotFoundError:
        logger.error(f"Portal plugin '{portal_name}' not found.")
    except Exception as e:
        logger.error(f"Auth setup failed: {e}", exc_info=True)
    finally:
        await context.close()
        await browser.stop()


def cmd_scheduler(config: dict, dry_run: bool, headful: bool):
    """Start APScheduler for continuous daily runs."""
    logger = logging.getLogger(__name__)

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        logger.error("APScheduler not installed. Run: pip install apscheduler")
        return

    schedule = config.get("schedule", {})
    hour = schedule.get("hour", 10)
    minute = schedule.get("minute", 0)

    scheduler = BlockingScheduler()

    def scheduled_run():
        """Wrapper to run async scrape from sync scheduler."""
        cleanup_old_logs()
        asyncio.run(run_scrape(config, dry_run=dry_run, headful=headful))

    scheduler.add_job(
        scheduled_run,
        CronTrigger(hour=hour, minute=minute),
        id="daily_scrape",
        name=f"Daily job scrape at {hour:02d}:{minute:02d}",
    )

    logger.info(f"Scheduler started. Will run daily at {hour:02d}:{minute:02d}")
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Scheduler stopped.")


def cmd_list_portals():
    """List available portal plugins."""
    portals = list_available_portals()
    if portals:
        print(f"\nAvailable portal plugins ({len(portals)}):")
        for name in portals:
            print(f"  • {name}")
    else:
        print("\nNo portal plugins found.")
    print(f"\nPortal plugins are located in: portals/")
    print("To add a new portal, create a new folder with login.py, search.py, and scrape.py")


def cmd_reset_db(config: dict):
    """Clear the database."""
    logger = logging.getLogger(__name__)
    db_path = config.get("general", {}).get("db_path", "jobs.db")
    
    from storage.db import JobDatabase
    db = JobDatabase(db_path)
    db.connect()
    
    confirm = input(f"Are you sure you want to clear all records from '{db_path}'? (y/N): ")
    if confirm.lower() == 'y':
        db.clear()
        print("Database cleared.")
    else:
        print("Operation cancelled.")
    
    db.close()


def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()

    # Parse arguments
    args = parse_args()

    # Load config
    config = load_config(args.config)

    # Setup logging
    log_level = config.get("general", {}).get("log_level", "INFO")
    log_file = setup_logging(log_level)

    logger = logging.getLogger(__name__)
    logger.info(f"Log file: {log_file}")

    # Route to the appropriate command
    if args.list_portals:
        cmd_list_portals()

    elif args.reset_db:
        cmd_reset_db(config)

    elif args.test_email:
        cmd_test_email(config)

    elif args.setup_auth:
        asyncio.run(cmd_setup_auth(config, args.setup_auth))

    elif args.scheduler:
        cmd_scheduler(config, dry_run=args.dry_run, headful=args.headful)

    elif args.run_now:
        asyncio.run(cmd_run_now(config, dry_run=args.dry_run, headful=args.headful))

    else:
        print("No run mode specified. Use --help for usage information.")
        print("\nQuick start:")
        print("  python main.py --run-now --dry-run    # Test scrape without email")
        print("  python main.py --run-now              # Full scrape + email")
        print("  python main.py --test-email           # Verify email config")


if __name__ == "__main__":
    main()
