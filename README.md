# JobScraper 🔍

A Python application that automatically scrapes career portals daily, deduplicates job listings, and sends you email notifications with new postings.

## Features

- **Multi-Portal Support** — Plugin architecture with per-portal login/search/scrape logic
- **Daily Scheduling** — Windows Task Scheduler (primary) or APScheduler (fallback)
- **Smart Deduplication** — SQLite-based tracking prevents duplicate notifications
- **Configurable Filters** — Job title keywords, max days old, portal-specific settings
- **Email Notifications** — Beautiful HTML emails with jobs grouped by portal
- **Flexible Auth** — Supports OAuth, credential-based, or no-auth portals
- **Headless/Headful Toggle** — Debug by watching the browser work

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure

Copy `.env.example` to `.env` and fill in your SMTP credentials:
```bash
copy .env.example .env
```

Edit `config.yaml` to set your:
- Job title keywords
- Max days old filter
- Email recipients
- Portal list

### 3. Test Run

```bash
# Dry run (scrape without emailing)
python main.py --run-now --dry-run

# With visible browser
python main.py --run-now --dry-run --headful

# Test email configuration
python main.py --test-email

# Full run (scrape + email)
python main.py --run-now

# Reset database (clear all scraped jobs)
python main.py --reset-db
```

### 4. Schedule Daily Runs

```bash
# Auto-create Windows Task Scheduler entry (run as admin)
setup_scheduler.bat

# OR use built-in scheduler (must keep running)
python main.py --scheduler
```

## CLI Reference

| Command | Description |
|---|---|
| `--run-now` | Execute a single scrape cycle |
| `--run-now --dry-run` | Scrape without sending email |
| `--run-now --headful` | Run with visible browser |
| `--test-email` | Send test email to verify SMTP |
| `--setup-auth <portal>` | Manual OAuth login for a portal |
| `--scheduler` | Start APScheduler (continuous) |
| `--list-portals` | List available portal plugins |
| `--reset-db` | Clear database of all scraped jobs |
| `--config <path>` | Use custom config file |

## Adding a New Portal

1. Create a new folder under `portals/`:
   ```
   portals/
   └── myportal/
       ├── __init__.py    # Portal class (implements PortalBase)
       ├── config.yaml    # Portal-specific selectors & URLs
       ├── login.py       # Authentication logic
       ├── search.py      # Job search & filtering
       └── scrape.py      # Job card extraction
   ```

2. Implement the `PortalBase` interface in `__init__.py`
3. Add the portal to `config.yaml`:
   ```yaml
   portals:
     - name: "myportal"
       enabled: true
       auth:
         type: "none"  # or "oauth" or "credentials"
   ```

## Project Structure

```
JobScrapper/
├── main.py              # CLI entry point
├── config.yaml          # Global configuration
├── core/
│   ├── browser.py       # Playwright browser management
│   ├── orchestrator.py  # Main run orchestration
│   └── date_parser.py   # Date parsing utilities
├── portals/
│   ├── base.py          # Abstract portal interface
│   ├── loader.py        # Dynamic plugin loader
│   └── microsoft/       # Microsoft portal plugin
├── models/
│   └── job.py           # Job data model
├── storage/
│   └── db.py            # SQLite dedup store
├── notifier/
│   └── email_sender.py  # SMTP email sender
├── auth/                # Session storage (gitignored)
└── logs/                # Run logs
```

## Currently Supported Portals

| Portal | Auth Required | URL |
|---|---|---|
| Microsoft (eightfold.ai) | No | https://microsoft.eightfold.ai/careers |
