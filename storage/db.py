import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from models.job import Job

logger = logging.getLogger(__name__)


class JobDatabase:
    """
    SQLite-based storage for tracking scraped job IDs.
    Prevents duplicate jobs from being sent in subsequent runs.
    """

    def __init__(self, db_path: str = "jobs.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Initialize the database connection and create tables if needed."""
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._create_tables()
        logger.info(f"Connected to database: {self.db_path}")

    def _create_tables(self):
        """Create the scraped_jobs table if it doesn't exist."""
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS scraped_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                portal_name TEXT NOT NULL,
                job_id TEXT NOT NULL,
                title TEXT,
                url TEXT,
                location TEXT,
                posted_date TEXT,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(portal_name, job_id)
            )
        """)
        self._conn.commit()

    def is_seen(self, portal_name: str, job_id: str) -> bool:
        """Check if a job has already been scraped."""
        cursor = self._conn.execute(
            "SELECT 1 FROM scraped_jobs WHERE portal_name = ? AND job_id = ?",
            (portal_name, job_id),
        )
        return cursor.fetchone() is not None

    def mark_seen(self, job: Job):
        """Record a job as scraped. Silently ignores duplicates."""
        try:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO scraped_jobs
                    (portal_name, job_id, title, url, location, posted_date, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job.portal_name,
                    job.job_id,
                    job.title,
                    job.url,
                    job.location,
                    job.posted_date.isoformat() if job.posted_date else None,
                    job.scraped_at.isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to mark job as seen: {e}")

    def mark_seen_batch(self, jobs: list[Job]):
        """Record multiple jobs as scraped in a single transaction."""
        try:
            self._conn.executemany(
                """
                INSERT OR IGNORE INTO scraped_jobs
                    (portal_name, job_id, title, url, location, posted_date, scraped_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        job.portal_name,
                        job.job_id,
                        job.title,
                        job.url,
                        job.location,
                        job.posted_date.isoformat() if job.posted_date else None,
                        job.scraped_at.isoformat(),
                    )
                    for job in jobs
                ],
            )
            self._conn.commit()
            logger.info(f"Marked {len(jobs)} jobs as seen")
        except sqlite3.Error as e:
            logger.error(f"Failed to mark jobs as seen: {e}")

    def filter_unseen(self, jobs: list[Job]) -> list[Job]:
        """Filter a list of jobs to only include ones not previously scraped."""
        return [job for job in jobs if not self.is_seen(job.portal_name, job.job_id)]

    def get_stats(self) -> dict:
        """Get summary statistics about scraped jobs."""
        cursor = self._conn.execute(
            "SELECT portal_name, COUNT(*) as count FROM scraped_jobs GROUP BY portal_name"
        )
        stats = {row["portal_name"]: row["count"] for row in cursor.fetchall()}

        cursor = self._conn.execute("SELECT COUNT(*) as total FROM scraped_jobs")
        stats["_total"] = cursor.fetchone()["total"]

        return stats

    def cleanup_old(self, days: int = 90):
        """Remove job records older than the specified number of days."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        cursor = self._conn.execute(
            "DELETE FROM scraped_jobs WHERE scraped_at < ?", (cutoff,)
        )
        self._conn.commit()
        logger.info(f"Cleaned up {cursor.rowcount} old job records (older than {days} days)")

    def clear(self):
        """Remove all job records from the database."""
        try:
            self._conn.execute("DELETE FROM scraped_jobs")
            self._conn.commit()
            logger.info("Cleared all job records from the database")
        except sqlite3.Error as e:
            logger.error(f"Failed to clear database: {e}")

    def close(self):
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            logger.info("Database connection closed")
